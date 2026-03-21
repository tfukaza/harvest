"""Concrete Anthropic-backed agent for the first Harvest CLI proof of concept."""

from __future__ import annotations

import datetime as dt
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from litellm import completion

from harvest.agent import Agent

DEFAULT_CLAUDE_MODEL = "anthropic/claude-sonnet-4-20250514"
DEFAULT_SYSTEM_PROMPT = (
    "You are the first Harvest CLI proof-of-concept agent. "
    "Answer clearly, stay grounded in the user request, and avoid inventing facts."
)


def load_env_file(env_path: str | Path) -> dict[str, str]:
    """Load simple key-value pairs from an env file.

    Args:
        env_path: Path to the env file.

    Returns:
        A mapping of keys loaded from the file.
    """

    file_path = Path(env_path)
    if not file_path.exists():
        return {}

    loaded_values: dict[str, str] = {}
    for raw_line in file_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line.removeprefix("export ").strip()

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        normalized_key = key.strip()
        normalized_value = value.strip()
        if not normalized_key:
            continue

        if len(normalized_value) >= 2 and normalized_value[0] == normalized_value[-1]:
            if normalized_value[0] in {"\"", "'"}:
                normalized_value = normalized_value[1:-1]

        os.environ.setdefault(normalized_key, normalized_value)
        loaded_values[normalized_key] = normalized_value

    return loaded_values


@dataclass(frozen=True)
class ClaudeAgentConfig:
    """Configuration for the first concrete Harvest Claude agent."""

    api_key: str
    model: str = DEFAULT_CLAUDE_MODEL
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    max_tokens: int = 1024

    @staticmethod
    def validate_model(model: str) -> str:
        """Validate the configured Anthropic model for the Phase 4 CLI slice.

        Args:
            model: Candidate model name.

        Returns:
            The validated model name.

        Raises:
            ValueError: If the model is not supported for this slice.
        """

        if model.startswith("anthropic/claude-3"):
            raise ValueError(
                "Claude 3 models are not supported for this CLI slice. "
                "Use a Claude 4 model such as 'anthropic/claude-sonnet-4-20250514'."
            )

        return model

    @classmethod
    def from_env(
        cls,
        env_file: str | Path = ".env",
        model: str | None = None,
        system_prompt: str | None = None,
        max_tokens: int = 1024,
    ) -> ClaudeAgentConfig:
        """Build Claude agent config from process env and an optional env file.

        Args:
            env_file: Path to a dotenv-style file.
            model: Optional explicit model override.
            system_prompt: Optional explicit system prompt override.
            max_tokens: Maximum tokens for each completion.

        Returns:
            A resolved Claude agent configuration.

        Raises:
            ValueError: If the Anthropic API key is not configured.
        """

        load_env_file(env_file)

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "Missing ANTHROPIC_API_KEY. Add it to your environment or to the selected .env file."
            )

        resolved_model = cls.validate_model(
            model or os.environ.get("HARVEST_AGENT_MODEL") or DEFAULT_CLAUDE_MODEL
        )
        resolved_prompt = system_prompt or os.environ.get("HARVEST_AGENT_SYSTEM_PROMPT") or DEFAULT_SYSTEM_PROMPT
        return cls(
            api_key=api_key,
            model=resolved_model,
            system_prompt=resolved_prompt,
            max_tokens=max_tokens,
        )


@dataclass(frozen=True)
class ConversationMessage:
    """Represents a single conversation message in UTC."""

    role: str
    content: str
    timestamp: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))

    def to_model_message(self) -> dict[str, str]:
        """Convert the message to the LLM wire format."""

        return {"role": self.role, "content": self.content}


class ClaudeAgent(Agent):
    """Anthropic-backed conversational agent for the Phase 4 CLI slice."""

    def __init__(
        self,
        config: ClaudeAgentConfig,
        completion_func: Callable[..., Any] | None = None,
    ) -> None:
        """Initialize the agent.

        Args:
            config: Resolved Claude configuration.
            completion_func: Optional completion function override for testing.
        """

        self.config = config
        self._completion_func = completion_func or completion
        self._history: list[ConversationMessage] = []

    @classmethod
    def from_env(
        cls,
        env_file: str | Path = ".env",
        model: str | None = None,
        system_prompt: str | None = None,
        max_tokens: int = 1024,
        completion_func: Callable[..., Any] | None = None,
    ) -> ClaudeAgent:
        """Create an agent from env-backed configuration."""

        config = ClaudeAgentConfig.from_env(
            env_file=env_file,
            model=model,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
        )
        return cls(config=config, completion_func=completion_func)

    def step(self, input_data: Any) -> str:
        """Send a user message to the Anthropic model and return the reply.

        Args:
            input_data: User input for the conversation turn.

        Returns:
            The assistant reply text.

        Raises:
            TypeError: If the input is not a string.
            RuntimeError: If the model response cannot be parsed.
        """

        if not isinstance(input_data, str):
            raise TypeError("ClaudeAgent.step expects a string user message.")

        user_message = ConversationMessage(role="user", content=input_data)
        self._history.append(user_message)

        response = self._completion_func(
            model=self.config.model,
            api_key=self.config.api_key,
            messages=self._build_messages(),
            max_tokens=self.config.max_tokens,
        )
        assistant_content = self._extract_response_text(response)
        self._history.append(ConversationMessage(role="assistant", content=assistant_content))
        return assistant_content

    def reset(self) -> None:
        """Reset the conversation history."""

        self._history.clear()

    def get_reasoning_history(self) -> list[ConversationMessage]:
        """Return the current conversation history."""

        return list(self._history)

    def _build_messages(self) -> list[dict[str, str]]:
        """Build the message list for the upstream completion call."""

        model_messages = [{"role": "system", "content": self.config.system_prompt}]
        model_messages.extend(message.to_model_message() for message in self._history)
        return model_messages

    def _extract_response_text(self, response: Any) -> str:
        """Extract text from a LiteLLM response object.

        Args:
            response: Response returned by LiteLLM.

        Returns:
            The assistant reply text.

        Raises:
            RuntimeError: If the response does not contain assistant text.
        """

        try:
            message = response.choices[0].message
        except (AttributeError, IndexError, KeyError, TypeError) as exc:
            raise RuntimeError("ClaudeAgent received an invalid response from the model.") from exc

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

        raise RuntimeError("ClaudeAgent response did not contain assistant text.")
