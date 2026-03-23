"""Provider-agnostic agent for the Harvest CLI, powered by LiteLLM."""

from __future__ import annotations

import datetime as dt
import getpass
import json
import logging
import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import litellm
from litellm import completion

from harvest.agent import Agent
from harvest.agent_sandbox.chat_client import ChatRouterClient
from harvest.agent_sandbox.agent_manager_client import AgentManagerClient

DEFAULT_MODEL = "anthropic/claude-haiku-4-5-20251001"
DEFAULT_SYSTEM_PROMPT = (
    "You are the first Harvest CLI proof-of-concept agent. "
    "Answer clearly, stay grounded in the user request, and avoid inventing facts."
)

_TOOL_CALL_LOOP_CAP = 25

_SUMMARIZATION_SYSTEM_PROMPT = (
    "Summarize the following conversation history. Preserve:\n"
    "- All decisions made and their reasoning\n"
    "- Current goals and task progress\n"
    "- Key facts, file paths, variable values, and user preferences\n"
    "- Unresolved questions or pending action items\n"
    "- Tool results that produced important information\n"
    "\n"
    "Be concise but do not omit information the agent will need to continue the conversation."
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Message hierarchy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolCallRecord:
    """Single tool call from the model."""

    id: str
    function_name: str
    arguments: str  # JSON string

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": "function",
            "function": {"name": self.function_name, "arguments": self.arguments},
        }


@dataclass(frozen=True)
class Message:
    """Base for all conversation messages."""

    role: str
    timestamp: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))

    def to_model_message(self) -> dict[str, Any]:
        raise NotImplementedError


@dataclass(frozen=True)
class TextMessage(Message):
    """User or assistant text message."""

    content: str = ""

    def to_model_message(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass(frozen=True)
class ToolCallMessage(Message):
    """Assistant message that requests tool calls."""

    content: str | None = None
    tool_calls: tuple[ToolCallRecord, ...] = ()

    def to_model_message(self) -> dict[str, Any]:
        return {
            "role": "assistant",
            "content": self.content,
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
        }


@dataclass(frozen=True)
class ToolResultMessage(Message):
    """Result from executing a tool."""

    tool_call_id: str = ""
    content: str = ""

    def to_model_message(self) -> dict[str, str]:
        return {"role": "tool", "tool_call_id": self.tool_call_id, "content": self.content}


@dataclass(frozen=True)
class SummaryMessage(Message):
    """Injected summary that replaces compacted older messages."""

    content: str = ""
    summarized_turn_count: int = 0
    summary_generation: int = 1  # increments on each re-summarization

    def to_model_message(self) -> dict[str, str]:
        return {
            "role": "user",
            "content": (
                f"[Conversation summary — {self.summarized_turn_count} earlier messages compacted]"
                f"\n\n{self.content}"
            ),
        }


# Backward-compatible alias
ConversationMessage = TextMessage


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HarvestAgentConfig:
    """Provider-agnostic configuration for a Harvest agent."""

    model: str = DEFAULT_MODEL
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    max_tokens: int = 1024
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    context_limit: int = 128_000
    compaction_threshold: float = 0.75
    recent_turns_to_keep: int = 10
    summary_model: str | None = None
    summary_max_tokens: int = 1024
    api_base: str | None = None
    api_key_env: str | None = None

    @classmethod
    def from_env(
        cls,
        model: str | None = None,
        system_prompt: str | None = None,
        max_tokens: int = 1024,
        session_id: str | None = None,
        context_limit: int | None = None,
        compaction_threshold: float | None = None,
        **kwargs: Any,
    ) -> HarvestAgentConfig:
        """Build config from environment variables.

        LiteLLM reads provider API keys (ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.)
        from the environment automatically — no custom key handling needed.
        """

        resolved_model = model or os.environ.get("HARVEST_AGENT_MODEL") or DEFAULT_MODEL
        resolved_prompt = (
            system_prompt or os.environ.get("HARVEST_AGENT_SYSTEM_PROMPT") or DEFAULT_SYSTEM_PROMPT
        )

        resolved_context_limit = context_limit
        if resolved_context_limit is None:
            env_val = os.environ.get("HARVEST_AGENT_CONTEXT_LIMIT")
            resolved_context_limit = int(env_val) if env_val else 128_000

        resolved_compaction_threshold = compaction_threshold
        if resolved_compaction_threshold is None:
            env_val = os.environ.get("HARVEST_AGENT_COMPACTION_THRESHOLD")
            resolved_compaction_threshold = float(env_val) if env_val else 0.75

        return cls(
            model=resolved_model,
            system_prompt=resolved_prompt,
            max_tokens=max_tokens,
            session_id=session_id or uuid.uuid4().hex,
            context_limit=resolved_context_limit,
            compaction_threshold=resolved_compaction_threshold,
            **kwargs,
        )


# ---------------------------------------------------------------------------
# Built-in tools
# ---------------------------------------------------------------------------

_GET_USERNAME_TOOL = {
    "type": "function",
    "function": {
        "name": "get_username",
        "description": "Return the operating system username",
        "parameters": {"type": "object", "properties": {}},
    },
}


def _get_username() -> str:
    return getpass.getuser()


def _tool_spec(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str] | None = None,
) -> dict[str, Any]:
    """Build an OpenAI-style tool specification dict."""
    params: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        params["required"] = required
    return {"type": "function", "function": {"name": name, "description": description, "parameters": params}}


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class HarvestAgent(Agent):
    """Provider-agnostic conversational agent powered by LiteLLM."""

    def __init__(
        self,
        config: HarvestAgentConfig,
        completion_func: Callable[..., Any] | None = None,
        conversation_store: Any | None = None,
        token_counter_func: Callable[..., int] | None = None,
        agent_id: str = "",
        chat_router: Any | None = None,
        policy: Any | None = None,
    ) -> None:
        self.config = config
        self.agent_id = agent_id or config.session_id
        self._completion_func = completion_func or completion
        self._history: list[Message] = []
        self._tools: list[dict] = [_GET_USERNAME_TOOL]
        self._tool_map: dict[str, Callable[..., str]] = {"get_username": _get_username}
        self._conversation_store = conversation_store
        self._turn_index = 0
        self._token_counter_func = token_counter_func
        self._chat_router = chat_router
        self._policy = policy
        self._sandbox: Any | None = None  # set by BasicSandbox when hosting
        self._chat_client: ChatRouterClient | None = None
        self._agent_manager: AgentManagerClient | None = None
        # Optional callable injected by BasicSandbox: returns the current system
        # prompt (base + dynamic sections).  When set, _build_messages() uses
        # this instead of self.config.system_prompt so that injected tool specs
        # and event notifications are included on every LLM call.
        self._system_prompt_fn: Callable[[], str] | None = None

        if chat_router is not None:
            self._wire_chat_router(chat_router, policy)

    def _wire_chat_router(self, chat_router: Any, policy: Any | None) -> None:
        """Wire this agent to the chat router with channel tools.

        Args:
            chat_router: The ChatRouter instance.
            policy: Optional AgentPolicy for permission checks.
        """
        chat_router.register_agent(self.agent_id)

        # Register channel tools based on policy
        can_send = True
        can_create = False
        if policy is not None:
            can_send = getattr(policy, "can_send_messages", True)
            can_create = getattr(policy, "can_create_channel", False)

        if can_send:
            self._register_send_message_tool(chat_router)

        self._register_read_messages_tool(chat_router)
        self._register_list_channels_tool(chat_router)
        self._register_leave_channel_tool(chat_router)

        if can_create:
            self._register_create_channel_tool(chat_router)

        can_create_agents = False
        if policy is not None:
            can_create_agents = getattr(policy, "can_create_agents", False)
        if can_create_agents:
            self._register_create_agent_tool()

    def _wire_service_router(self, service_router: Any) -> None:
        """Wire the sandbox service router's generic tools to this agent.

        Registers ``fetch_data``, ``execute_action``, and
        ``read_event_notifications`` based on the agent's current policy.
        Called by :class:`~harvest.agent_sandbox.basic_sandbox.BasicSandbox`
        after ``_wire_chat_router``.

        Args:
            service_router: A
                :class:`~harvest.agent_sandbox.service_router.SandboxServiceRouter`
                instance.
        """
        tool_specs, tool_map = service_router.make_service_tools(
            self.agent_id, self._policy
        )
        self._tools.extend(tool_specs)
        self._tool_map.update(tool_map)

    def _wire_chat_client(self, sandbox_bus: Any, policy: Any) -> None:
        """Wire this agent to the ChatRouter via event-driven clients.

        This is the event-bus counterpart of :meth:`_wire_chat_router`.  It
        creates thin tool wrappers that delegate to :class:`ChatRouterClient`
        and :class:`AgentManagerClient` instead of calling ChatRouter methods
        directly.

        Args:
            sandbox_bus: A :class:`~harvest.agent_sandbox.event_helpers.SyncEventBus`.
            policy: An :class:`~harvest.policy.AgentPolicy` instance.
        """
        self._chat_client = ChatRouterClient(self.agent_id, sandbox_bus)

        # -- Permission flags -------------------------------------------------
        can_send = True
        can_create_channel = False
        can_create_agents = False
        if policy is not None:
            can_send = getattr(policy, "can_send_messages", True)
            can_create_channel = getattr(policy, "can_create_channel", False)
            can_create_agents = getattr(policy, "can_create_agents", False)

        # -- send_message (event-driven) --------------------------------------
        if can_send:
            self._tools.append(_tool_spec(
                "send_message",
                "Send a message to a channel. For group channels, if another "
                "agent is currently writing, your call will wait until they "
                "finish. If new messages appeared while waiting, you get "
                "status='channel_updated' — your message was NOT sent. "
                "DISCARD your previous message, read the new messages, and "
                "call send_message again with a completely fresh response. "
                "Each incoming message has a short ID like [msg:abcd1234]. "
                "Use reply_to to indicate which message(s) you are responding to.",
                {"channel_id": {"type": "string", "description": "Target channel ID"},
                 "content": {"type": "string", "description": "Message text"},
                 "reply_to": {"type": "string", "description": (
                     "Comma-separated short message IDs (from [msg:...] tags) "
                     "that this message is responding to. Example: 'abcd1234' "
                     "or 'abcd1234,ef567890'")}},
                required=["channel_id", "content"],
            ))

            def _send_message_ev(channel_id: str = "", content: str = "", reply_to: str = "", **kwargs: Any) -> str:
                logger.info("[tool] %s send_message(%s, %.40s...)", self.agent_id, channel_id, content)
                result = self._chat_client.send_message(channel_id, content, reply_to=reply_to)  # type: ignore[union-attr]
                return json.dumps(result)

            self._tool_map["send_message"] = _send_message_ev

        # -- read_messages (event-driven) -------------------------------------
        self._tools.append(_tool_spec(
            "read_messages",
            "Read messages. No args = inbox overview. With channel_id = read from channel.",
            {"channel_id": {"type": "string", "description": "Optional channel ID to read from"},
             "history": {"type": "boolean", "description": "If true, load full channel history"}},
        ))

        def _read_messages_ev(channel_id: str = "", history: bool = False, **kwargs: Any) -> str:
            logger.info("[tool] %s read_messages(%s, history=%s)", self.agent_id, channel_id, history)
            result = self._chat_client.read_messages(channel_id=channel_id, history=history)  # type: ignore[union-attr]
            return json.dumps(result)

        self._tool_map["read_messages"] = _read_messages_ev

        # -- list_channels (event-driven) -------------------------------------
        self._tools.append(_tool_spec(
            "list_channels", "List channels you belong to.",
            {"channel_type": {"type": "string", "description": "Optional filter by type"}},
        ))

        def _list_channels_ev(channel_type: str = "", **kwargs: Any) -> str:
            logger.info("[tool] %s list_channels(%s)", self.agent_id, channel_type)
            return json.dumps(self._chat_client.list_channels(channel_type=channel_type))  # type: ignore[union-attr]

        self._tool_map["list_channels"] = _list_channels_ev

        # -- leave_channel (direct ChatRouter — migrate later) ----------------
        if self._chat_router is not None:
            self._register_leave_channel_tool(self._chat_router)

        # -- create_channel (direct ChatRouter — migrate later) ---------------
        if can_create_channel and self._chat_router is not None:
            self._register_create_channel_tool(self._chat_router)

        # -- add_agent_to_channel (event-driven) ------------------------------
        if can_create_agents:
            self._tools.append(_tool_spec(
                "add_agent_to_channel", "Add an agent to a channel.",
                {"agent_id": {"type": "string"}, "channel_id": {"type": "string"}},
                required=["agent_id", "channel_id"],
            ))

            def _add_agent_to_channel_ev(agent_id: str = "", channel_id: str = "", **kwargs: Any) -> str:
                logger.info("[tool] %s add_agent_to_channel(%s, %s)", self.agent_id, agent_id, channel_id)
                result = self._chat_client.add_agent_to_channel(agent_id, channel_id)  # type: ignore[union-attr]
                return json.dumps(result)

            self._tool_map["add_agent_to_channel"] = _add_agent_to_channel_ev

        # -- create_agent / shutdown_agent (event-driven) ---------------------
        if can_create_agents:
            self._agent_manager = AgentManagerClient(self.agent_id, sandbox_bus)

            self._tools.append(_tool_spec(
                "create_agent", "Spawn a child agent with a policy.",
                {"agent_id": {"type": "string", "description": "Unique ID for the new agent"},
                 "policy_name": {"type": "string", "description": "Named policy (for PREDEFINED mode)"},
                 "policy": {"type": "object", "description": "Custom policy definition (for DEFINE mode)"}},
                required=["agent_id"],
            ))

            def _create_agent_ev(
                agent_id: str = "",
                policy_name: str = "",
                policy: dict[str, Any] | None = None,
                **kwargs: Any,
            ) -> str:
                logger.info("[tool] %s create_agent(%s, policy_name=%s)", self.agent_id, agent_id, policy_name)
                result = self._agent_manager.create_agent(  # type: ignore[union-attr]
                    agent_id=agent_id,
                    policy_name=policy_name,
                    policy_dict=policy,
                )
                return json.dumps(result)

            self._tool_map["create_agent"] = _create_agent_ev

            self._tools.append(_tool_spec(
                "shutdown_agent", "Stop a child agent. Only agents you created can be shut down.",
                {"agent_id": {"type": "string"}},
                required=["agent_id"],
            ))

            def _shutdown_agent_ev(agent_id: str = "", **kwargs: Any) -> str:
                logger.info("[tool] %s shutdown_agent(%s)", self.agent_id, agent_id)
                result = self._agent_manager.shutdown_agent(agent_id)  # type: ignore[union-attr]
                return json.dumps(result)

            self._tool_map["shutdown_agent"] = _shutdown_agent_ev

        # -- complete_task (event-driven) -------------------------------------
        allowed_tools = getattr(policy, "allowed_tools", frozenset()) if policy else frozenset()
        if "complete_task" in allowed_tools:
            if self._agent_manager is None:
                self._agent_manager = AgentManagerClient(self.agent_id, sandbox_bus)

            self._tools.append(_tool_spec(
                "complete_task", "Declare your task done and shut yourself down.", {},
            ))

            def _complete_task_ev(**kwargs: Any) -> str:
                logger.info("[tool] %s complete_task()", self.agent_id)
                self._agent_manager.shutdown_agent(self.agent_id)  # type: ignore[union-attr]
                return json.dumps({"status": "task_complete"})

            self._tool_map["complete_task"] = _complete_task_ev

    def _register_send_message_tool(self, chat_router: Any) -> None:
        """Register the send_message tool."""
        self._tools.append(_tool_spec(
            "send_message",
            "Send a message to a channel. For group channels, if another "
            "agent is currently writing, your call will wait until they "
            "finish. If new messages appeared while waiting, you get "
            "status='channel_updated' — your message was NOT sent. "
            "DISCARD your previous message, read the new messages, and "
            "call send_message again with a completely fresh response. "
            "Each incoming message has a short ID like [msg:abcd1234]. "
            "Use reply_to to indicate which message(s) you are responding to.",
            {"channel_id": {"type": "string", "description": "Target channel ID"},
             "content": {"type": "string", "description": "Message text"},
             "reply_to": {"type": "string", "description": (
                 "Comma-separated short message IDs (from [msg:...] tags) "
                 "that this message is responding to. Example: 'abcd1234' "
                 "or 'abcd1234,ef567890'")}},
            required=["channel_id", "content"],
        ))

        def _send_message(channel_id: str = "", content: str = "", reply_to: str = "", **kwargs: Any) -> str:
            msg_id = uuid.uuid4().hex
            logger.info("[tool] %s send_message(%s, %.40s...)", self.agent_id, channel_id, content)
            if reply_to:
                logger.debug("[reply] %s msg %s replies to: %s", self.agent_id, msg_id[:8], reply_to)

            # Pre-flight: check if new messages arrived in our inbox since
            # the agent woke up.  If any are for the TARGET channel, the
            # agent's context is stale — return them instead of sending.
            # We drain the target-channel messages from the inbox so that
            # repeated send attempts don't keep returning the same stale
            # messages (which pollutes the LLM context window).
            pending = chat_router.peek_inbox(self.agent_id)
            target_count = sum(
                1 for m in pending
                if (m.recipient.endpoint_id if m.recipient else "") == channel_id
            )
            if target_count:
                # Drain the target-channel messages so they don't repeat
                chat_router.drain_channel_messages(self.agent_id, channel_id)
                logger.info(
                    "[pre-send] %s has %d new message(s) in target channel %s — "
                    "returning inbox_updated instead of sending",
                    self.agent_id, target_count, channel_id,
                )
                return json.dumps({
                    "status": "inbox_updated",
                    "unread_in_channel": target_count,
                    "hint": (
                        f"IMPORTANT: Your message was NOT sent. {target_count} new "
                        f"message(s) arrived in #{channel_id} while you were "
                        "composing. Call read_messages with "
                        f'channel_id="{channel_id}" and history=true to see '
                        "the full conversation, then compose a fresh response."
                    ),
                })

            result = chat_router.send_message(
                self.agent_id, channel_id, content, msg_id, reply_to=reply_to,
            )
            logger.info("[tool] %s send_message result: %s", self.agent_id, result.get("status"))
            if result.get("error"):
                return json.dumps({"error": result["error"]})
            if result.get("status") == "channel_updated":
                logger.info(
                    "[channel_updated] %s message to %s discarded, new context available",
                    self.agent_id, channel_id,
                )
                return json.dumps({
                    "status": "channel_updated",
                    "new_messages": result.get("new_messages", []),
                    "hint": result.get("hint", ""),
                })
            # After a successful send, check if new messages arrived while
            # the send was in progress (e.g. waiting for a stake).
            resp: dict[str, Any] = {"status": "sent", "channel_id": channel_id}
            post_pending = chat_router.peek_inbox(self.agent_id)
            if post_pending:
                # Summarise by channel rather than dumping full content —
                # cross-channel content in tool results confuses the LLM.
                from collections import Counter
                ch_counts: Counter[str] = Counter()
                for m in post_pending:
                    ch = m.recipient.endpoint_id if m.recipient else "unknown"
                    ch_counts[ch] += 1
                resp["new_messages_waiting"] = {
                    ch: count for ch, count in ch_counts.items()
                }
                resp["hint"] = (
                    "Your message was sent successfully, but new messages "
                    "arrived while you were composing. Use read_messages "
                    "to check the channels listed in new_messages_waiting."
                )
                logger.info(
                    "[inbox-peek] %s has %d new message(s) after send",
                    self.agent_id, len(post_pending),
                )
            return json.dumps(resp)

        self._tool_map["send_message"] = _send_message

    def _register_read_messages_tool(self, chat_router: Any) -> None:
        """Register the read_messages tool."""
        self._tools.append(_tool_spec(
            "read_messages", "Read messages. No args = inbox overview. With channel_id = read from channel.",
            {
                "channel_id": {"type": "string", "description": "Optional channel ID to read from"},
                "history": {"type": "boolean", "description": "If true, load full channel history"},
            },
        ))

        def _sender_label(m: Any) -> str:
            """Return a display label for the message sender."""
            from harvest.agent_sandbox.chat import ChatRouter
            sid = m.sender.endpoint_id
            return "scenario-prompt" if sid == ChatRouter.SEED_SENDER_ID else sid

        def _read_messages(channel_id: str = "", history: bool = False, **kwargs: Any) -> str:
            if channel_id and history:
                msgs = chat_router.load_channel_history(channel_id)
                return json.dumps({"channel_id": channel_id, "history": msgs})
            if channel_id:
                inbox = chat_router.read_inbox(self.agent_id)
                filtered = [m for m in inbox if m.recipient.endpoint_id == channel_id]
                return json.dumps({
                    "channel_id": channel_id,
                    "messages": [
                        {
                            "channel_id": m.recipient.endpoint_id if m.recipient else "",
                            "sender": _sender_label(m),
                            "content": m.content,
                        }
                        for m in filtered
                    ],
                })
            # Overview — include channel per message so the agent knows where
            # each message came from without needing a follow-up call.
            inbox = chat_router.peek_inbox(self.agent_id)
            if not inbox:
                return json.dumps({"unread": 0})
            from collections import Counter
            ch_counts: Counter[str] = Counter()
            for m in inbox:
                ch = m.recipient.endpoint_id if m.recipient else "unknown"
                ch_counts[ch] += 1
            return json.dumps({
                "unread": len(inbox),
                "channels": {ch: count for ch, count in ch_counts.items()},
                "hint": "Call read_messages with a specific channel_id to read messages from that channel.",
            })

        self._tool_map["read_messages"] = _read_messages

    def _register_list_channels_tool(self, chat_router: Any) -> None:
        """Register the list_channels tool."""
        self._tools.append(_tool_spec(
            "list_channels", "List channels you belong to.",
            {
                "channel_type": {"type": "string", "description": "Optional filter by type"},
            },
        ))

        def _list_channels(channel_type: str = "", **kwargs: Any) -> str:
            channels = chat_router.list_channels_for_agent(self.agent_id)
            if channel_type:
                channels = [c for c in channels if c.channel_type.value == channel_type]
            result = []
            for ch in channels:
                info: dict[str, Any] = {
                    "channel_id": ch.channel_id,
                    "type": ch.channel_type.value,
                    "title": ch.title,
                    "description": ch.description,
                }
                if hasattr(ch, "member_ids"):
                    info["member_ids"] = ch.member_ids
                if hasattr(ch, "publisher_ids"):
                    info["publisher_ids"] = ch.publisher_ids
                    info["subscriber_ids"] = ch.subscriber_ids
                result.append(info)
            return json.dumps(result)

        self._tool_map["list_channels"] = _list_channels

    def _register_leave_channel_tool(self, chat_router: Any) -> None:
        """Register the leave_channel tool."""
        self._tools.append(_tool_spec(
            "leave_channel", "Leave a channel.",
            {
                "channel_id": {"type": "string", "description": "Channel to leave"},
            },
            required=["channel_id"],
        ))

        def _leave_channel(channel_id: str = "", **kwargs: Any) -> str:
            chat_router.leave_channel(self.agent_id, channel_id)
            return json.dumps({"status": "left", "channel_id": channel_id})

        self._tool_map["leave_channel"] = _leave_channel

    def _register_create_channel_tool(self, chat_router: Any) -> None:
        """Register the create_channel tool."""
        self._tools.append(_tool_spec(
            "create_channel", "Create a new channel.",
            {
                "channel_id": {"type": "string"},
                "channel_type": {"type": "string", "enum": ["dm", "group", "gated", "aggregation"]},
                "member_ids": {"type": "array", "items": {"type": "string"}},
                "publisher_ids": {"type": "array", "items": {"type": "string"}},
                "subscriber_ids": {"type": "array", "items": {"type": "string"}},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "batch_threshold": {"type": "integer"},
            },
            required=["channel_id", "channel_type"],
        ))

        def _create_channel(**kwargs: Any) -> str:
            from harvest.agent_sandbox.channels import (
                AggregationProcessorChannel,
                DMChannel,
                GatedProcessorChannel,
                GroupChannel,
            )

            ch_type = kwargs.get("channel_type", "group")
            ch_id = kwargs.get("channel_id", "")
            title = kwargs.get("title", "")
            desc = kwargs.get("description", "")

            if ch_type == "dm":
                channel = DMChannel(
                    channel_id=ch_id,
                    member_ids=kwargs.get("member_ids", []),
                    title=title,
                    description=desc,
                    created_by=self.agent_id,
                )
            elif ch_type == "group":
                channel = GroupChannel(
                    channel_id=ch_id,
                    member_ids=kwargs.get("member_ids", []),
                    title=title,
                    description=desc,
                    created_by=self.agent_id,
                )
            elif ch_type == "gated":
                channel = GatedProcessorChannel(
                    channel_id=ch_id,
                    publisher_ids=kwargs.get("publisher_ids", []),
                    subscriber_ids=kwargs.get("subscriber_ids", []),
                    title=title,
                    description=desc,
                    created_by=self.agent_id,
                )
            elif ch_type == "aggregation":
                channel = AggregationProcessorChannel(
                    channel_id=ch_id,
                    publisher_ids=kwargs.get("publisher_ids", []),
                    subscriber_ids=kwargs.get("subscriber_ids", []),
                    batch_threshold=kwargs.get("batch_threshold", 1),
                    title=title,
                    description=desc,
                    created_by=self.agent_id,
                )
            else:
                return json.dumps({"error": f"Unknown channel type: {ch_type}"})

            try:
                chat_router.create_channel(channel)
            except ValueError as e:
                return json.dumps({"error": str(e)})
            return json.dumps({"status": "created", "channel_id": ch_id})

        self._tool_map["create_channel"] = _create_channel

    def _register_create_agent_tool(self) -> None:
        """Register the create_agent tool for spawning child agents."""
        self._tools.append(_tool_spec(
            "create_agent", "Spawn a child agent with a policy.",
            {
                "agent_id": {"type": "string", "description": "Unique ID for the new agent"},
                "policy_name": {"type": "string", "description": "Named policy (for PREDEFINED mode)"},
                "policy": {
                    "type": "object",
                    "description": "Custom policy definition (for DEFINE mode)",
                },
            },
            required=["agent_id"],
        ))

        def _create_agent(
            agent_id: str = "",
            policy_name: str = "",
            policy: dict[str, Any] | None = None,
            **kwargs: Any,
        ) -> str:
            if self._sandbox is None:
                return json.dumps({"error": "Agent not hosted in a sandbox"})

            parent_policy = self._policy
            if parent_policy is None:
                return json.dumps({"error": "No parent policy"})

            from harvest.policy import AgentPolicy, ChildPolicyMode

            mode = parent_policy.child_policy_mode
            if mode == ChildPolicyMode.NONE:
                return json.dumps({"error": "Policy does not allow creating agents"})

            child_policy: AgentPolicy | None = None
            if mode == ChildPolicyMode.CLONE:
                # Child gets a copy of parent's policy with a new name
                child_policy = AgentPolicy(
                    name=f"{parent_policy.name}-clone-{agent_id}",
                    allowed_tools=parent_policy.allowed_tools,
                    can_send_messages=parent_policy.can_send_messages,
                    can_create_channel=parent_policy.can_create_channel,
                    can_create_agents=parent_policy.can_create_agents,
                    child_policy_mode=parent_policy.child_policy_mode,
                    allowed_child_policies=parent_policy.allowed_child_policies,
                )
            elif mode == ChildPolicyMode.PREDEFINED:
                if not policy_name:
                    return json.dumps({"error": "PREDEFINED mode requires policy_name"})
                if policy_name not in parent_policy.allowed_child_policies:
                    return json.dumps({"error": f"Policy '{policy_name}' not in allowed_child_policies"})
                pr = self._sandbox._policy_registry
                if pr is None:
                    return json.dumps({"error": "No policy registry available"})
                try:
                    child_policy = pr.get(policy_name)
                except KeyError:
                    return json.dumps({"error": f"Policy '{policy_name}' not found in registry"})
            elif mode == ChildPolicyMode.DEFINE:
                if policy is None:
                    return json.dumps({"error": "DEFINE mode requires policy dict"})
                child_policy = AgentPolicy(
                    name=policy.get("name", f"custom-{agent_id}"),
                    allowed_tools=frozenset(policy.get("allowed_tools", [])),
                    can_send_messages=policy.get("can_send_messages", True),
                    can_create_channel=policy.get("can_create_channel", False),
                    can_create_agents=policy.get("can_create_agents", False),
                    child_policy_mode=ChildPolicyMode(policy.get("child_policy_mode", "none")),
                    allowed_child_policies=tuple(policy.get("allowed_child_policies", [])),
                )

            if child_policy is None:
                return json.dumps({"error": "Could not resolve child policy"})

            # Create a minimal child agent
            child_config = HarvestAgentConfig(
                model=self.config.model,
                system_prompt=f"You are child agent {agent_id}.",
            )
            child_agent = HarvestAgent(
                config=child_config,
                agent_id=agent_id,
                chat_router=self._chat_router,
                policy=child_policy,
                completion_func=self._completion_func,
            )

            try:
                self._sandbox.register_agent(agent_id, child_agent, policy=child_policy)
            except ValueError as e:
                return json.dumps({"error": str(e)})

            return json.dumps({"status": "created", "agent_id": agent_id})

        self._tool_map["create_agent"] = _create_agent

    def shutdown(self) -> None:
        """Clean up agent resources.

        Called by the sandbox before removal. Unregisters from the ChatRouter
        and clears conversation history.
        """
        if self._chat_router is not None:
            self._chat_router.unregister_agent(self.agent_id)
        if self._chat_client is not None:
            self._chat_client.close()
        if self._agent_manager is not None:
            self._agent_manager.close()
        self._history.clear()
        logger.info("Agent %s session ended", self.agent_id)

    # ------------------------------------------------------------------
    # Token counting
    # ------------------------------------------------------------------

    def _count_tokens(self) -> int:
        """Estimate the token count of the current working history."""
        messages = self._build_messages()
        if self._token_counter_func is not None:
            return self._token_counter_func(model=self.config.model, messages=messages)
        try:
            return litellm.token_counter(model=self.config.model, messages=messages)
        except Exception:
            # Fallback: rough char-based heuristic
            return sum(len(str(m)) for m in messages) // 4

    # ------------------------------------------------------------------
    # Compaction
    # ------------------------------------------------------------------

    def _find_split_index(self) -> int:
        """Return the index that splits old (to compact) from recent (to keep).

        Keeps at least ``recent_turns_to_keep`` messages, extending the recent
        window backward to avoid splitting tool-call/result groups.
        """
        n = len(self._history)
        keep = self.config.recent_turns_to_keep
        if keep >= n:
            return n  # nothing to compact

        split = n - keep

        # Walk backward to ensure we don't split a tool-call/result group.
        # A group is a ToolCallMessage followed by consecutive ToolResultMessages.
        # If split lands on a ToolResultMessage, move it back past sibling results.
        while split > 0 and isinstance(self._history[split], ToolResultMessage):
            split -= 1
        # After the loop, split points to the ToolCallMessage (or a non-tool msg).
        # history[:split] is "old", history[split:] is "recent".
        # The ToolCallMessage at split is included in "recent" — correct.

        # Edge case: if split is still on a ToolResultMessage (split == 0),
        # there's nothing safe to compact.
        if split > 0 and isinstance(self._history[split], ToolResultMessage):
            return n

        return split

    def _maybe_compact(self) -> None:
        """Compact older history into a summary if approaching the context limit."""
        threshold = self.config.context_limit * self.config.compaction_threshold
        token_count = self._count_tokens()
        if token_count < threshold:
            return

        split = self._find_split_index()
        if split <= 0 or split >= len(self._history):
            return  # nothing to compact

        old_messages = self._history[:split]
        if not old_messages:
            return

        # Build the summarization user content
        old_summary: str | None = None
        old_generation = 0
        formatted_parts: list[str] = []

        for msg in old_messages:
            if isinstance(msg, SummaryMessage):
                old_summary = msg.content
                old_generation = msg.summary_generation
            else:
                formatted_parts.append(self._format_message_for_summary(msg))

        user_content = ""
        if old_summary:
            user_content += f"Previous summary (generation {old_generation}):\n{old_summary}\n\nSubsequent messages:\n"
        user_content += "\n".join(formatted_parts)

        # Call the model for summarization (internal — not persisted)
        summary_model = self.config.summary_model or self.config.model
        try:
            response = self._completion_func(
                model=summary_model,
                messages=[
                    {"role": "system", "content": _SUMMARIZATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=self.config.summary_max_tokens,
            )
            summary_text = response.choices[0].message.content or ""
        except Exception:
            logger.warning("Compaction summarization call failed; skipping compaction.")
            return

        generation = old_generation + 1 if old_summary else 1
        summary_msg = SummaryMessage(
            role="user",
            content=summary_text,
            summarized_turn_count=len(old_messages),
            summary_generation=generation,
        )

        # Replace old messages in working history
        self._history = [summary_msg] + self._history[split:]

        # Persist the summary message
        if self._conversation_store is not None:
            self._conversation_store.append_message(
                session_id=self.config.session_id,
                turn_index=self._turn_index,
                message=summary_msg,
            )
            self._turn_index += 1

    @staticmethod
    def _format_message_for_summary(msg: Message) -> str:
        """Format a single message for inclusion in the summarization prompt."""
        if isinstance(msg, TextMessage):
            return f"{msg.role}: {msg.content}"
        if isinstance(msg, ToolCallMessage):
            calls = ", ".join(tc.function_name for tc in msg.tool_calls)
            return f"assistant: [tool calls: {calls}]"
        if isinstance(msg, ToolResultMessage):
            content_preview = msg.content[:500] if len(msg.content) > 500 else msg.content
            return f"tool result ({msg.tool_call_id}): {content_preview}"
        return f"{msg.role}: (unknown message type)"

    def step(self, input_data: Any) -> str:
        """Send a user message and return the assistant text reply.

        Handles tool-call loops transparently.
        """

        if not isinstance(input_data, str):
            raise TypeError("HarvestAgent.step expects a string user message.")

        logger.debug("[context] %s step() input prompt:\n%s", self.agent_id, input_data)

        user_msg = TextMessage(role="user", content=input_data)
        self._append(user_msg)

        self._maybe_compact()  # pre-turn compaction

        for loop_idx in range(_TOOL_CALL_LOOP_CAP):
            messages = self._build_messages()
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "[context] %s LLM call #%d — %d messages, system prompt %d chars",
                    self.agent_id, loop_idx, len(messages),
                    len(messages[0]["content"]) if messages else 0,
                )
                for i, m in enumerate(messages):
                    role = m.get("role", "?")
                    content = m.get("content", "")
                    preview = (content[:300] + "…") if isinstance(content, str) and len(content) > 300 else content
                    logger.debug("[context] %s   msg[%d] role=%s: %s", self.agent_id, i, role, preview)
            completion_kwargs: dict[str, Any] = {
                "model": self.config.model,
                "messages": messages,
                "max_tokens": self.config.max_tokens,
                "tools": self._tools,
            }
            if self.config.api_base:
                completion_kwargs["api_base"] = self.config.api_base
            if self.config.api_key_env:
                import os as _os
                api_key_val = _os.environ.get(self.config.api_key_env)
                if api_key_val:
                    completion_kwargs["api_key"] = api_key_val
            response = self._completion_func(**completion_kwargs)

            choice = response.choices[0].message
            tool_calls = getattr(choice, "tool_calls", None)

            if tool_calls:
                # Log tool calls at INFO so they are visible without --debug.
                for tc in tool_calls:
                    logger.info(
                        "[tool-call] %s → %s(%s)",
                        self.agent_id,
                        tc.function.name,
                        tc.function.arguments[:120] if tc.function.arguments else "",
                    )
                if logger.isEnabledFor(logging.DEBUG):
                    thinking = getattr(choice, "content", None)
                    if thinking:
                        logger.debug("[response] %s thinking: %s", self.agent_id, thinking[:300])

                records = tuple(
                    ToolCallRecord(
                        id=tc.id,
                        function_name=tc.function.name,
                        arguments=tc.function.arguments,
                    )
                    for tc in tool_calls
                )
                tc_msg = ToolCallMessage(
                    role="assistant",
                    content=getattr(choice, "content", None),
                    tool_calls=records,
                )
                self._append(tc_msg)

                for tc in tool_calls:
                    fn = self._tool_map.get(tc.function.name)
                    if fn is None:
                        result = json.dumps({"error": f"Unknown tool: {tc.function.name}"})
                    else:
                        try:
                            args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                        except (json.JSONDecodeError, TypeError):
                            args = {}
                        try:
                            result = fn(**args) if args else fn()
                        except Exception as tool_exc:
                            logger.exception(
                                "[tool-error] %s %s raised: %s",
                                self.agent_id, tc.function.name, tool_exc,
                            )
                            result = json.dumps({"error": f"Tool execution failed: {tool_exc}"})
                    logger.debug(
                        "[tool-result] %s %s → %s",
                        self.agent_id, tc.function.name,
                        (result[:300] + "…") if isinstance(result, str) and len(result) > 300 else result,
                    )
                    self._append(
                        ToolResultMessage(role="tool", tool_call_id=tc.id, content=result)
                    )

                self._maybe_compact()  # post-tool-result compaction
                continue

            # Text response — done
            try:
                content = self._extract_response_text(response)
            except RuntimeError:
                # Model returned no text after tool calls — valid when the
                # agent communicated through tools (e.g. send_message).
                content = ""
            logger.debug("[response] %s text reply (%d chars): %s", self.agent_id, len(content), content[:300])
            assistant_msg = TextMessage(role="assistant", content=content)
            self._append(assistant_msg)
            return content

        raise RuntimeError("Tool-call loop exceeded the safety cap.")

    def reset(self) -> None:
        self._history.clear()

    def get_reasoning_history(self) -> list[Message]:
        return list(self._history)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _append(self, msg: Message) -> None:
        """Append a message to the working history and optionally persist."""
        self._history.append(msg)
        if self._conversation_store is not None:
            self._conversation_store.append_message(
                session_id=self.config.session_id,
                turn_index=self._turn_index,
                message=msg,
            )
        self._turn_index += 1

    @property
    def base_system_prompt(self) -> str:
        """Return the agent's base system prompt from its configuration."""
        return self.config.system_prompt

    def _build_messages(self) -> list[dict[str, Any]]:
        # Use the dynamic system prompt provider if wired (BasicSandbox injects
        # this to include SystemPromptBuilder sections such as tool specs and
        # event notifications).  Fall back to the static config prompt.
        if self._system_prompt_fn is not None:
            system_prompt = self._system_prompt_fn()
        else:
            system_prompt = self.config.system_prompt
        model_messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]
        model_messages.extend(m.to_model_message() for m in self._history)
        return model_messages

    def _extract_response_text(self, response: Any) -> str:
        try:
            message = response.choices[0].message
        except (AttributeError, IndexError, KeyError, TypeError) as exc:
            raise RuntimeError("HarvestAgent received an invalid response from the model.") from exc

        content = getattr(message, "content", None)
        if isinstance(content, str) and content.strip():
            return content

        if isinstance(content, list):
            text_parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text_value = item.get("text")
                else:
                    text_value = getattr(item, "text", None)
                if text_value:
                    text_parts.append(str(text_value))
            if text_parts:
                return "".join(text_parts)

        raise RuntimeError("HarvestAgent response did not contain assistant text.")
