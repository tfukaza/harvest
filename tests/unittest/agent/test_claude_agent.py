"""Tests for the first concrete Claude-backed Harvest agent."""

from __future__ import annotations

from pathlib import Path

import pytest

from harvest.claude_agent import ClaudeAgent, ClaudeAgentConfig, ConversationMessage


class _FakeMessage:
    """Minimal fake response message for completion tests."""

    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    """Minimal fake response choice for completion tests."""

    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeResponse:
    """Minimal fake response envelope for completion tests."""

    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


def test_claude_agent_config_reads_env_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("HARVEST_AGENT_MODEL", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ANTHROPIC_API_KEY=test-key\nHARVEST_AGENT_MODEL=anthropic/test-model\n",
        encoding="utf-8",
    )

    config = ClaudeAgentConfig.from_env(env_file=env_file)

    assert config.api_key == "test-key"
    assert config.model == "anthropic/test-model"


def test_claude_agent_config_defaults_to_claude_4_model(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("HARVEST_AGENT_MODEL", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("ANTHROPIC_API_KEY=test-key\n", encoding="utf-8")

    config = ClaudeAgentConfig.from_env(env_file=env_file)

    assert config.model == "anthropic/claude-sonnet-4-20250514"


def test_claude_agent_config_rejects_claude_3_models(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("HARVEST_AGENT_MODEL", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ANTHROPIC_API_KEY=test-key\nHARVEST_AGENT_MODEL=anthropic/claude-3-7-sonnet-latest\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Claude 3 models are not supported"):
        ClaudeAgentConfig.from_env(env_file=env_file)


def test_claude_agent_step_returns_model_reply() -> None:
    recorded_payloads: list[dict[str, object]] = []

    def fake_completion(**kwargs: object) -> _FakeResponse:
        recorded_payloads.append(dict(kwargs))
        return _FakeResponse("hello back")

    agent = ClaudeAgent(
        config=ClaudeAgentConfig(api_key="test-key", model="anthropic/test-model"),
        completion_func=fake_completion,
    )

    response = agent.step("hello")

    assert response == "hello back"
    assert recorded_payloads[0]["model"] == "anthropic/test-model"
    assert recorded_payloads[0]["api_key"] == "test-key"
    assert recorded_payloads[0]["messages"] == [
        {"role": "system", "content": agent.config.system_prompt},
        {"role": "user", "content": "hello"},
    ]
    assert agent.get_reasoning_history() == [
        ConversationMessage(role="user", content="hello", timestamp=agent.get_reasoning_history()[0].timestamp),
        ConversationMessage(
            role="assistant",
            content="hello back",
            timestamp=agent.get_reasoning_history()[1].timestamp,
        ),
    ]


def test_claude_agent_reset_clears_history() -> None:
    agent = ClaudeAgent(
        config=ClaudeAgentConfig(api_key="test-key"),
        completion_func=lambda **kwargs: _FakeResponse("done"),
    )

    agent.step("hello")
    agent.reset()

    assert agent.get_reasoning_history() == []


def test_claude_agent_requires_string_input() -> None:
    agent = ClaudeAgent(
        config=ClaudeAgentConfig(api_key="test-key"),
        completion_func=lambda **kwargs: _FakeResponse("done"),
    )

    with pytest.raises(TypeError, match="expects a string"):
        agent.step({"message": "hello"})
