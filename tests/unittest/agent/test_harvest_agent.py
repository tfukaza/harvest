"""Tests for the provider-agnostic HarvestAgent."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from harvest.harvest_agent import (
    HarvestAgent,
    HarvestAgentConfig,
    TextMessage,
    ToolCallMessage,
    ToolResultMessage,
)


# ---------------------------------------------------------------------------
# Fake LiteLLM response helpers
# ---------------------------------------------------------------------------


class _FakeFunction:
    def __init__(self, name: str, arguments: str = "{}") -> None:
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, id: str, function: _FakeFunction) -> None:
        self.id = id
        self.function = function


class _FakeMessage:
    def __init__(
        self,
        content: str | None = None,
        tool_calls: list[_FakeToolCall] | None = None,
    ) -> None:
        self.content = content
        self.tool_calls = tool_calls


class _FakeChoice:
    def __init__(self, message: _FakeMessage) -> None:
        self.message = message


class _FakeResponse:
    def __init__(self, message: _FakeMessage) -> None:
        self.choices = [_FakeChoice(message)]

    @classmethod
    def text(cls, content: str) -> _FakeResponse:
        return cls(_FakeMessage(content=content))

    @classmethod
    def tool_call(
        cls,
        tool_id: str,
        function_name: str,
        arguments: str = "{}",
    ) -> _FakeResponse:
        tc = _FakeToolCall(tool_id, _FakeFunction(function_name, arguments))
        return cls(_FakeMessage(content=None, tool_calls=[tc]))


# ---------------------------------------------------------------------------
# Part 0: Basic agent tests
# ---------------------------------------------------------------------------


def test_config_defaults() -> None:
    config = HarvestAgentConfig()
    assert config.model == "anthropic/claude-sonnet-4-20250514"
    assert config.max_tokens == 1024
    assert config.session_id  # non-empty


def test_config_from_env_reads_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARVEST_AGENT_MODEL", "openai/gpt-4o")
    monkeypatch.setenv("HARVEST_AGENT_SYSTEM_PROMPT", "custom prompt")

    config = HarvestAgentConfig.from_env()

    assert config.model == "openai/gpt-4o"
    assert config.system_prompt == "custom prompt"


def test_config_from_env_uses_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HARVEST_AGENT_MODEL", raising=False)
    monkeypatch.delenv("HARVEST_AGENT_SYSTEM_PROMPT", raising=False)

    config = HarvestAgentConfig.from_env()

    assert config.model == "anthropic/claude-sonnet-4-20250514"


def test_step_returns_model_reply() -> None:
    recorded: list[dict] = []

    def fake_completion(**kwargs: object) -> _FakeResponse:
        recorded.append(dict(kwargs))
        return _FakeResponse.text("hello back")

    agent = HarvestAgent(
        config=HarvestAgentConfig(model="anthropic/test-model"),
        completion_func=fake_completion,
    )

    response = agent.step("hello")

    assert response == "hello back"
    assert recorded[0]["model"] == "anthropic/test-model"
    assert "api_key" not in recorded[0]  # LiteLLM handles keys
    assert recorded[0]["tools"]  # tools are always passed

    history = agent.get_reasoning_history()
    assert len(history) == 2
    assert isinstance(history[0], TextMessage)
    assert history[0].role == "user"
    assert history[0].content == "hello"
    assert isinstance(history[1], TextMessage)
    assert history[1].role == "assistant"
    assert history[1].content == "hello back"


def test_reset_clears_history() -> None:
    agent = HarvestAgent(
        config=HarvestAgentConfig(),
        completion_func=lambda **kwargs: _FakeResponse.text("done"),
    )

    agent.step("hello")
    agent.reset()

    assert agent.get_reasoning_history() == []


def test_requires_string_input() -> None:
    agent = HarvestAgent(
        config=HarvestAgentConfig(),
        completion_func=lambda **kwargs: _FakeResponse.text("done"),
    )

    with pytest.raises(TypeError, match="expects a string"):
        agent.step({"message": "hello"})


# ---------------------------------------------------------------------------
# Part 1: Tool calling tests
# ---------------------------------------------------------------------------


def test_tools_passed_to_completion() -> None:
    recorded: list[dict] = []

    def fake_completion(**kwargs: object) -> _FakeResponse:
        recorded.append(dict(kwargs))
        return _FakeResponse.text("hi")

    agent = HarvestAgent(
        config=HarvestAgentConfig(),
        completion_func=fake_completion,
    )
    agent.step("hello")

    assert "tools" in recorded[0]
    tools = recorded[0]["tools"]
    assert any(t["function"]["name"] == "get_username" for t in tools)


def test_tool_call_loop() -> None:
    """Fake completion returns a tool call first, then a text response."""
    call_count = 0

    def fake_completion(**kwargs: object) -> _FakeResponse:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _FakeResponse.tool_call("tc_1", "get_username")
        return _FakeResponse.text("Your username is testuser")

    with patch("harvest.harvest_agent._get_username", return_value="testuser"):
        agent = HarvestAgent(
            config=HarvestAgentConfig(),
            completion_func=fake_completion,
        )
        reply = agent.step("what is my username?")

    assert reply == "Your username is testuser"
    assert call_count == 2

    history = agent.get_reasoning_history()
    assert isinstance(history[0], TextMessage)  # user
    assert isinstance(history[1], ToolCallMessage)  # assistant tool call
    assert isinstance(history[2], ToolResultMessage)  # tool result
    assert history[2].content == "testuser"
    assert isinstance(history[3], TextMessage)  # final assistant text


def test_get_username_tool() -> None:
    with patch("harvest.harvest_agent.getpass") as mock_gp:
        mock_gp.getuser.return_value = "mockuser"
        from harvest.harvest_agent import _get_username

        assert _get_username() == "mockuser"


def test_tool_call_safety_cap() -> None:
    """If the model keeps requesting tool calls, we raise RuntimeError."""

    def fake_completion(**kwargs: object) -> _FakeResponse:
        return _FakeResponse.tool_call("tc_loop", "get_username")

    agent = HarvestAgent(
        config=HarvestAgentConfig(),
        completion_func=fake_completion,
    )

    with pytest.raises(RuntimeError, match="safety cap"):
        agent.step("infinite loop")


# ---------------------------------------------------------------------------
# Part 2: Persistence tests (agent side)
# ---------------------------------------------------------------------------


def test_agent_persists_messages_to_store() -> None:
    from harvest.storage.schema.agent import ConversationStore

    store = ConversationStore()

    agent = HarvestAgent(
        config=HarvestAgentConfig(session_id="test-session"),
        completion_func=lambda **kwargs: _FakeResponse.text("reply"),
        conversation_store=store,
    )
    agent.step("hello")

    log = store.load_log("test-session")
    assert len(log) == 2
    assert log[0]["role"] == "user"
    assert log[1]["role"] == "assistant"


def test_agent_does_not_auto_load_history_from_store() -> None:
    from harvest.storage.schema.agent import ConversationStore

    store = ConversationStore()

    agent1 = HarvestAgent(
        config=HarvestAgentConfig(session_id="s1"),
        completion_func=lambda **kwargs: _FakeResponse.text("reply"),
        conversation_store=store,
    )
    agent1.step("hello")

    # New agent with same session — should NOT auto-load
    agent2 = HarvestAgent(
        config=HarvestAgentConfig(session_id="s1"),
        completion_func=lambda **kwargs: _FakeResponse.text("reply2"),
        conversation_store=store,
    )
    assert agent2.get_reasoning_history() == []
