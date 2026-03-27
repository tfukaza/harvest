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
_MAX_INBOX_UPDATED = 2

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
    tokens_before: int = 0  # token count before compaction
    tokens_after: int = 0   # token count after compaction

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
    max_tokens: int = 4096
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    context_limit: int = 128_000
    compaction_threshold: float = 0.75
    recent_turns_to_keep: int = 10
    summary_model: str | None = None
    summary_max_tokens: int = 1024
    api_base: str | None = None
    api_key_env: str | None = None
    tool_call_loop_cap: int = 25

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
        self._policy = policy
        self._sandbox: Any | None = None  # set by BasicSandbox when hosting
        self._chat_client: ChatRouterClient | None = None
        self._agent_manager: AgentManagerClient | None = None
        # Cognitive tool state (populated when _wire_cognitive_tools is called)
        self._memories: dict[str, dict[str, str]] = {}
        self._todos: list[dict[str, Any]] = []
        # Track how many times each channel has returned inbox_updated
        # within a step, to avoid infinite retry loops.
        self._inbox_updated_counts: dict[str, int] = {}

        # Result buffering for large service results
        from harvest.result_buffer import ResultBuffer
        self._result_buffer = ResultBuffer()
        self._register_browse_results_tool()
        # Optional callable injected by BasicSandbox: returns the current system
        # prompt (base + dynamic sections).  When set, _build_messages() uses
        # this instead of self.config.system_prompt so that injected tool specs
        # and event notifications are included on every LLM call.
        self._system_prompt_fn: Callable[[], str] | None = None
        # Last known token count — updated each time _count_tokens() is called.
        self._last_token_count: int = 0

    def _register_browse_results_tool(self) -> None:
        """Register the browse_results tool for navigating large buffered results."""
        spec = _tool_spec(
            "browse_results",
            (
                "Navigate a large service result that was buffered. "
                "Supports three modes: page (retrieve a specific page), "
                "grep (search for matching entries), and "
                "slice (retrieve a range by offset and count)."
            ),
            {
                "tool_call_id": {
                    "type": "string",
                    "description": "ID of the tool call whose results to browse.",
                },
                "mode": {
                    "type": "string",
                    "enum": ["page", "grep", "slice"],
                    "description": "Navigation mode.",
                },
                "page": {
                    "type": "integer",
                    "description": "Page number (0-indexed). For mode=page.",
                },
                "query": {
                    "type": "string",
                    "description": "Search query. For mode=grep.",
                },
                "offset": {
                    "type": "integer",
                    "description": "Start index. For mode=slice.",
                },
                "count": {
                    "type": "integer",
                    "description": "Number of items/lines to return. For mode=slice.",
                },
            },
            required=["tool_call_id", "mode"],
        )

        buf = self._result_buffer

        def _browse_handler(
            tool_call_id: str = "",
            mode: str = "",
            page: int | None = None,
            query: str | None = None,
            offset: int | None = None,
            count: int | None = None,
            **_kwargs: Any,
        ) -> str:
            return buf.browse(
                tool_call_id=tool_call_id,
                mode=mode,
                page=page,
                query=query,
                offset=offset,
                count=count,
            )

        self._tools.append(spec)
        self._tool_map["browse_results"] = _browse_handler

    def _wire_cognitive_tools(self, enabled: frozenset[str]) -> None:
        """Wire cognitive tools (think, memory, todo) based on policy.

        Args:
            enabled: Set of cognitive tool group names to activate.
        """
        from harvest.cognitive_tools import get_cognitive_tools

        for spec, handler in get_cognitive_tools(self, enabled):
            self._tools.append(spec)
            self._tool_map[spec["function"]["name"]] = handler

    def _wire_service_router(self, service_router: Any) -> None:
        """Wire the sandbox service router's generic tools to this agent.

        Registers ``fetch_data``, ``execute_action``, and
        ``read_event_notifications`` based on the agent's current policy.
        Called by :class:`~harvest.agent_sandbox.basic_sandbox.BasicSandbox`
        after chat-client wiring.

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
        """Register event-driven chat and agent-management tools on the sandbox bus.

        Creates thin tool wrappers that delegate to :class:`ChatRouterClient`
        and :class:`AgentManagerClient` instead of calling ChatRouter methods
        directly.  Each wrapper communicates with the sandbox via the
        ``dispatch_and_wait`` pattern on *sandbox_bus*.

        The following tools may be wired depending on the agent's policy
        permissions:

        - **send_message** – send a chat message (requires ``can_send``)
        - **acquire_channel_lock** / **release_channel_lock** – explicit
          write-stake management for group channels (requires ``can_send``)
        - **read_messages** – read inbox overview or channel history
        - **list_channels** – enumerate channels the agent belongs to
        - **leave_channel** – leave a channel (event-driven)
        - **create_channel** – create a new channel (requires
          ``can_create_channel``, event-driven)
        - **add_agent_to_channel** – add another agent to a channel
          (requires ``can_create_agents``)
        - **create_agent** / **shutdown_agent** – spawn or stop child agents
          (requires ``can_create_agents``)
        - **complete_task** – self-shutdown tool (requires ``complete_task``
          in ``allowed_tools``)

        Side effects:
            Appends tool spec dicts to :attr:`self._tools` and registers the
            corresponding callables in :attr:`self._tool_map`.  Also
            initialises :attr:`self._chat_client` and, when agent-management
            tools are enabled, :attr:`self._agent_manager`.

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

        if can_send:
            self._register_send_message_tool_ev()
            self._register_channel_lock_tools_ev()

        self._register_read_messages_tool_ev()
        self._register_list_channels_tool_ev()

        self._register_leave_channel_tool_ev()

        if can_create_channel:
            self._register_create_channel_tool_ev()

        if can_create_agents:
            self._register_add_agent_to_channel_tool_ev()
            self._register_agent_lifecycle_tools_ev(sandbox_bus)

        # -- complete_task (event-driven) -------------------------------------
        allowed_tools = getattr(policy, "allowed_tools", frozenset()) if policy else frozenset()
        if "complete_task" in allowed_tools:
            self._register_complete_task_tool_ev(sandbox_bus)

    def _register_send_message_tool_ev(self) -> None:
        """Register the event-driven send_message tool."""
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
            if not content or not content.strip():
                logger.warning(
                    "[empty-send] %s called send_message to %s with no content — "
                    "rejected. The LLM likely hit a token limit and dropped "
                    "the content parameter.",
                    self.agent_id, channel_id,
                )
                return json.dumps({
                    "error": "Message content is empty. You must provide "
                    "a non-empty 'content' parameter. Try again with your "
                    "message text in the content field.",
                })
            result = self._chat_client.send_message(channel_id, content, reply_to=reply_to)  # type: ignore[union-attr]
            return json.dumps(result)

        self._tool_map["send_message"] = _send_message_ev

    def _register_channel_lock_tools_ev(self) -> None:
        """Register the event-driven acquire_channel_lock and release_channel_lock tools."""
        self._tools.append(_tool_spec(
            "acquire_channel_lock",
            "Reserve the write lock on a group channel BEFORE composing "
            "a long message. This prevents another agent from taking the "
            "channel while you spend tokens composing. After acquiring, "
            "call send_message to deliver your message (the lock is "
            "auto-released on send). If you decide not to send, call "
            "release_channel_lock. For short messages (1-3 sentences), "
            "just use send_message directly — it acquires the lock "
            "automatically.",
            {"channel_id": {"type": "string", "description": "Channel ID to lock"}},
            required=["channel_id"],
        ))

        def _acquire_channel_lock_ev(channel_id: str = "", **kwargs: Any) -> str:
            logger.info("[tool] %s acquire_channel_lock(%s)", self.agent_id, channel_id)
            result = self._chat_client.acquire_channel_lock(channel_id)  # type: ignore[union-attr]
            return json.dumps(result)

        self._tool_map["acquire_channel_lock"] = _acquire_channel_lock_ev

        self._tools.append(_tool_spec(
            "release_channel_lock",
            "Release a channel lock you acquired with acquire_channel_lock "
            "without sending a message. Use this if you changed your mind "
            "or need to abort.",
            {"channel_id": {"type": "string", "description": "Channel ID to unlock"}},
            required=["channel_id"],
        ))

        def _release_channel_lock_ev(channel_id: str = "", **kwargs: Any) -> str:
            logger.info("[tool] %s release_channel_lock(%s)", self.agent_id, channel_id)
            result = self._chat_client.release_channel_lock(channel_id)  # type: ignore[union-attr]
            return json.dumps(result)

        self._tool_map["release_channel_lock"] = _release_channel_lock_ev

    def _register_read_messages_tool_ev(self) -> None:
        """Register the event-driven read_messages tool."""
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

    def _register_list_channels_tool_ev(self) -> None:
        """Register the event-driven list_channels tool."""
        self._tools.append(_tool_spec(
            "list_channels", "List channels you belong to.",
            {"channel_type": {"type": "string", "description": "Optional filter by type"}},
        ))

        def _list_channels_ev(channel_type: str = "", **kwargs: Any) -> str:
            logger.info("[tool] %s list_channels(%s)", self.agent_id, channel_type)
            return json.dumps(self._chat_client.list_channels(channel_type=channel_type))  # type: ignore[union-attr]

        self._tool_map["list_channels"] = _list_channels_ev

    def _register_add_agent_to_channel_tool_ev(self) -> None:
        """Register the event-driven add_agent_to_channel tool."""
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

    def _register_create_channel_tool_ev(self) -> None:
        """Register the event-driven create_channel tool."""
        self._tools.append(_tool_spec(
            "create_channel", "Create a new channel.",
            {
                "channel_id": {"type": "string"},
                "channel_type": {"type": "string", "enum": ["dm", "group"]},
                "member_ids": {"type": "array", "items": {"type": "string"}},
                "description": {"type": "string"},
            },
            required=["channel_id", "channel_type"],
        ))

        def _create_channel_ev(
            channel_id: str = "",
            channel_type: str = "group",
            member_ids: list[str] | None = None,
            description: str = "",
            **kwargs: Any,
        ) -> str:
            logger.info("[tool] %s create_channel(%s, %s)", self.agent_id, channel_id, channel_type)
            result = self._chat_client.create_channel(  # type: ignore[union-attr]
                channel_id=channel_id, channel_type=channel_type,
                member_ids=member_ids or [], description=description,
            )
            return json.dumps(result)

        self._tool_map["create_channel"] = _create_channel_ev

    def _register_leave_channel_tool_ev(self) -> None:
        """Register the event-driven leave_channel tool."""
        self._tools.append(_tool_spec(
            "leave_channel", "Leave a channel.",
            {
                "channel_id": {"type": "string", "description": "Channel to leave"},
            },
            required=["channel_id"],
        ))

        def _leave_channel_ev(channel_id: str = "", **kwargs: Any) -> str:
            logger.info("[tool] %s leave_channel(%s)", self.agent_id, channel_id)
            result = self._chat_client.leave_channel(channel_id)  # type: ignore[union-attr]
            return json.dumps(result)

        self._tool_map["leave_channel"] = _leave_channel_ev

    def _register_agent_lifecycle_tools_ev(self, sandbox_bus: Any) -> None:
        """Register the event-driven create_agent and shutdown_agent tools."""
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

    def _register_complete_task_tool_ev(self, sandbox_bus: Any) -> None:
        """Register the event-driven complete_task tool."""
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

    def shutdown(self) -> None:
        """Clean up agent resources and release external connections.

        Called by the sandbox before agent removal.  Performs the following
        cleanup steps:

        1. Closes the event-driven :class:`ChatRouterClient` (if wired).
        2. Closes the :class:`AgentManagerClient` (if wired).
        3. Clears the in-memory conversation history.

        This method is idempotent: calling it multiple times is safe because
        each resource check is guarded by a ``None`` test, and
        ``_history.clear()`` on an already-empty list is a no-op.
        """
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
            count = self._token_counter_func(model=self.config.model, messages=messages)
        else:
            try:
                count = litellm.token_counter(model=self.config.model, messages=messages)
            except Exception:
                # Fallback: rough char-based heuristic
                count = sum(len(str(m)) for m in messages) // 4
        self._last_token_count = count
        return count

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
        """Compact older conversation history into a summary when nearing the context limit.

        Checks whether the current token count exceeds
        ``config.context_limit * config.compaction_threshold``.  If so, it
        splits ``self._history`` into an *old* prefix and a *recent* suffix
        (preserving tool-call/result group boundaries), summarises the old
        messages via an LLM call using ``config.summary_model``, and replaces
        them with a single :class:`SummaryMessage` at the front of the
        history.  If a prior summary already exists among the old messages,
        it is incorporated into the summarisation prompt and its generation
        counter is incremented.

        Side effects:
            - Mutates ``self._history`` by removing old entries and prepending
              a :class:`SummaryMessage`.
            - Makes a blocking LLM completion call for summarisation (using
              ``self._completion_func``).
            - Updates ``self._last_token_count`` via :meth:`_count_tokens`.

        If the summarisation LLM call fails, compaction is skipped and the
        history is left unchanged.
        """
        threshold = self.config.context_limit * self.config.compaction_threshold
        token_count = self._count_tokens()
        if token_count < threshold:
            return

        tokens_before = token_count

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

        # Replace old messages in working history
        self._history = self._history[split:]

        # Count tokens after compaction (before inserting summary) to get
        # an accurate after-count that includes the summary itself.
        # We temporarily prepend the summary to measure.
        temp_summary = SummaryMessage(
            role="user",
            content=summary_text,
            summarized_turn_count=len(old_messages),
            summary_generation=generation,
        )
        self._history.insert(0, temp_summary)
        tokens_after = self._count_tokens()

        # Now replace with the final summary that includes token stats
        self._history[0] = SummaryMessage(
            role="user",
            content=summary_text,
            summarized_turn_count=len(old_messages),
            summary_generation=generation,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
        )

        logger.info(
            "Agent %s compacted: %d → %d tokens (saved %d, gen %d, %d messages summarized)",
            self.agent_id, tokens_before, tokens_after,
            tokens_before - tokens_after, generation, len(old_messages),
        )

        # Persist the summary message
        if self._conversation_store is not None:
            self._conversation_store.append_message(
                session_id=self.config.session_id,
                turn_index=self._turn_index,
                message=self._history[0],
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

    def _execute_tool_calls(self, tool_calls: list[Any], choice: Any) -> bool:
        """Execute a batch of tool calls from the LLM response.

        Creates :class:`ToolCallRecord` entries, appends a
        :class:`ToolCallMessage` to history, invokes each tool handler, runs
        results through the result buffer, and appends
        :class:`ToolResultMessage` entries to history.

        Args:
            tool_calls: The ``tool_calls`` list from
                ``response.choices[0].message.tool_calls``.
            choice: The ``response.choices[0].message`` object (used to
                extract assistant thinking content).

        Returns:
            ``True`` if ``send_message`` was called during this batch.
        """
        sent_message = False

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
            if tc.function.name == "send_message":
                sent_message = True
            fn = self._tool_map.get(tc.function.name)
            if fn is None:
                result = json.dumps({"error": f"Unknown tool: {tc.function.name}"})
            else:
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except (json.JSONDecodeError, TypeError):
                    args = {}
                try:
                    raw_result = fn(**args) if args else fn()
                except Exception as tool_exc:
                    logger.exception(
                        "[tool-error] %s %s raised: %s",
                        self.agent_id, tc.function.name, tool_exc,
                    )
                    raw_result = json.dumps({"error": f"Tool execution failed: {tool_exc}"})
                # Run through result buffer (handles ServiceResult and strings)
                from harvest.result_buffer import ServiceResult  # noqa: F811
                result = self._result_buffer.process(tc.id, raw_result)
            logger.debug(
                "[tool-result] %s %s → %s",
                self.agent_id, tc.function.name,
                (result[:300] + "…") if isinstance(result, str) and len(result) > 300 else result,
            )
            self._append(
                ToolResultMessage(role="tool", tool_call_id=tc.id, content=result)
            )

        return sent_message

    def step(self, input_data: str) -> str:
        """Send a user message and return the assistant text reply.

        Processes the input through the LLM and handles tool-call loops
        transparently, up to ``config.tool_call_loop_cap`` iterations.
        May trigger conversation compaction if the context approaches
        ``config.context_limit``.

        Side effects:
            - Appends messages to ``_history`` (user, assistant, tool results).
            - Advances the result buffer turn counter.
            - May compact ``_history`` via summarization.
            - Persists messages to ``_conversation_store`` if configured.

        Args:
            input_data: The user message string.

        Returns:
            The assistant's final text reply (empty string if only tool calls).

        Raises:
            TypeError: If input_data is not a string.
        """

        if not isinstance(input_data, str):
            raise TypeError("HarvestAgent.step expects a string user message.")

        logger.debug("[context] %s step() input prompt:\n%s", self.agent_id, input_data)

        user_msg = TextMessage(role="user", content=input_data)
        self._append(user_msg)

        self._result_buffer.advance_turn()
        self._maybe_compact()  # pre-turn compaction

        _sent_message_this_step = False
        for loop_idx in range(self.config.tool_call_loop_cap):
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
                sent = self._execute_tool_calls(tool_calls, choice)
                if sent:
                    _sent_message_this_step = True
                self._maybe_compact()  # post-tool-result compaction
                continue

            # Text response — done (or model stalled)
            try:
                content = self._extract_response_text(response)
            except RuntimeError:
                # Model returned no text after tool calls — valid when the
                # agent communicated through tools (e.g. send_message).
                content = ""

            # Guard against models that return empty responses mid-task.
            # If the response is empty and we've made tool calls this turn,
            # nudge the model to continue by injecting a follow-up prompt.
            if not content.strip() and loop_idx > 0 and not _sent_message_this_step and loop_idx < self.config.tool_call_loop_cap - 2:
                # Check if the agent has pending work (e.g. todo items not completed)
                logger.info(
                    "[recovery] %s returned empty response at loop %d, nudging to continue",
                    self.agent_id, loop_idx,
                )
                nudge = "[system: continue — you have not posted results yet]"
                self._append(TextMessage(role="assistant", content=""))
                self._append(TextMessage(role="user", content=nudge))
                continue

            logger.debug("[response] %s text reply (%d chars): %s", self.agent_id, len(content), content[:300])
            assistant_msg = TextMessage(role="assistant", content=content)
            self._append(assistant_msg)
            return content

        # TODO: Instead of raising, inject a user message into the context
        # warning the agent that it exceeded the tool-call loop cap. The
        # message should list which tool calls were requested in the last
        # iteration but not executed, and instruct the agent to slow down
        # (e.g. "You have exceeded the tool-call limit. The following tool
        # calls were NOT executed: [...]. Please reduce the number of tool
        # calls per turn and use `think` to reflect between batches.").
        # Then allow one more LLM call so the agent can recover gracefully
        # rather than crashing the entire agent loop.
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
