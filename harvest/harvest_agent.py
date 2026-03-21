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

DEFAULT_MODEL = "anthropic/claude-sonnet-4-20250514"
DEFAULT_SYSTEM_PROMPT = (
    "You are the first Harvest CLI proof-of-concept agent. "
    "Answer clearly, stay grounded in the user request, and avoid inventing facts."
)

_TOOL_CALL_LOOP_CAP = 10

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
    ) -> None:
        self.config = config
        self._completion_func = completion_func or completion
        self._history: list[Message] = []
        self._tools: list[dict] = [_GET_USERNAME_TOOL]
        self._tool_map: dict[str, Callable[[], str]] = {"get_username": _get_username}
        self._conversation_store = conversation_store
        self._turn_index = 0
        self._token_counter_func = token_counter_func

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

        user_msg = TextMessage(role="user", content=input_data)
        self._append(user_msg)

        self._maybe_compact()  # pre-turn compaction

        for _ in range(_TOOL_CALL_LOOP_CAP):
            response = self._completion_func(
                model=self.config.model,
                messages=self._build_messages(),
                max_tokens=self.config.max_tokens,
                tools=self._tools,
            )

            choice = response.choices[0].message
            tool_calls = getattr(choice, "tool_calls", None)

            if tool_calls:
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
                        result = fn()
                    self._append(
                        ToolResultMessage(role="tool", tool_call_id=tc.id, content=result)
                    )

                self._maybe_compact()  # post-tool-result compaction
                continue

            # Text response — done
            content = self._extract_response_text(response)
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

    def _build_messages(self) -> list[dict[str, Any]]:
        model_messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.config.system_prompt}
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
