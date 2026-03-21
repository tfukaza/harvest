"""Tests for Phase 7: Conversation Compaction."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from harvest.harvest_agent import (
    HarvestAgent,
    HarvestAgentConfig,
    Message,
    SummaryMessage,
    TextMessage,
    ToolCallMessage,
    ToolCallRecord,
    ToolResultMessage,
)


# ---------------------------------------------------------------------------
# Fake LiteLLM response helpers (duplicated from test_harvest_agent.py)
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


def _make_agent(
    *,
    context_limit: int = 128_000,
    compaction_threshold: float = 0.75,
    recent_turns_to_keep: int = 10,
    token_count: int | None = None,
    completion_func: Any = None,
    token_counter_func: Any = None,
    conversation_store: Any = None,
    summary_response: str = "This is a summary.",
) -> HarvestAgent:
    """Helper to create an agent with sensible test defaults."""

    call_count = 0

    def default_completion(**kwargs: Any) -> _FakeResponse:
        nonlocal call_count
        call_count += 1
        # If no tools are passed, this is a summarization call
        if "tools" not in kwargs:
            return _FakeResponse.text(summary_response)
        return _FakeResponse.text(f"reply-{call_count}")

    config = HarvestAgentConfig(
        model="test/model",
        context_limit=context_limit,
        compaction_threshold=compaction_threshold,
        recent_turns_to_keep=recent_turns_to_keep,
    )

    counter = None
    if token_count is not None:
        counter = lambda **kw: token_count
    elif token_counter_func is not None:
        counter = token_counter_func

    return HarvestAgent(
        config=config,
        completion_func=completion_func or default_completion,
        conversation_store=conversation_store,
        token_counter_func=counter,
    )


# ---------------------------------------------------------------------------
# Workstream A: Token Counting
# ---------------------------------------------------------------------------


class TestTokenCounting:
    def test_count_tokens_returns_int(self) -> None:
        agent = _make_agent(token_count=42)
        assert agent._count_tokens() == 42
        assert isinstance(agent._count_tokens(), int)

    def test_injectable_token_counter_func(self) -> None:
        calls: list[dict] = []

        def counter(**kwargs: Any) -> int:
            calls.append(kwargs)
            return 100

        agent = _make_agent(token_counter_func=counter)
        result = agent._count_tokens()

        assert result == 100
        assert len(calls) == 1
        assert calls[0]["model"] == "test/model"

    def test_fallback_on_error(self) -> None:
        """When litellm.token_counter raises, fall back to heuristic."""

        def bad_counter(**kwargs: Any) -> int:
            raise RuntimeError("tokenizer not found")

        # We need an agent without a token_counter_func so it tries litellm
        agent = _make_agent()
        agent._token_counter_func = None

        with patch("harvest.harvest_agent.litellm") as mock_litellm:
            mock_litellm.token_counter.side_effect = RuntimeError("no tokenizer")
            result = agent._count_tokens()

        assert isinstance(result, int)
        assert result > 0  # heuristic produces some count


# ---------------------------------------------------------------------------
# Workstream B: Configuration
# ---------------------------------------------------------------------------


class TestCompactionConfig:
    def test_config_defaults(self) -> None:
        config = HarvestAgentConfig()
        assert config.context_limit == 128_000
        assert config.compaction_threshold == 0.75
        assert config.recent_turns_to_keep == 10
        assert config.summary_model is None
        assert config.summary_max_tokens == 1024

    def test_from_env_reads_context_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HARVEST_AGENT_CONTEXT_LIMIT", "64000")
        config = HarvestAgentConfig.from_env()
        assert config.context_limit == 64_000

    def test_from_env_reads_compaction_threshold(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HARVEST_AGENT_COMPACTION_THRESHOLD", "0.5")
        config = HarvestAgentConfig.from_env()
        assert config.compaction_threshold == 0.5

    def test_from_env_explicit_overrides_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HARVEST_AGENT_CONTEXT_LIMIT", "64000")
        config = HarvestAgentConfig.from_env(context_limit=32000)
        assert config.context_limit == 32_000


# ---------------------------------------------------------------------------
# Workstream C: SummaryMessage
# ---------------------------------------------------------------------------


class TestSummaryMessage:
    def test_to_model_message_format(self) -> None:
        msg = SummaryMessage(
            role="user",
            content="Summary text here",
            summarized_turn_count=5,
            summary_generation=1,
        )
        result = msg.to_model_message()
        assert result["role"] == "user"
        assert "[Conversation summary — 5 earlier messages compacted]" in result["content"]
        assert "Summary text here" in result["content"]

    def test_frozen(self) -> None:
        msg = SummaryMessage(role="user", content="test")
        with pytest.raises(AttributeError):
            msg.content = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Workstream D: Compaction Logic
# ---------------------------------------------------------------------------


class TestCompactionTrigger:
    def test_no_compaction_below_threshold(self) -> None:
        """Token count below threshold should not trigger compaction."""
        agent = _make_agent(
            context_limit=1000,
            compaction_threshold=0.75,
            token_count=100,  # well below 750
            recent_turns_to_keep=2,
        )
        # Populate history with several messages
        for i in range(5):
            agent._history.append(TextMessage(role="user", content=f"msg {i}"))
            agent._history.append(TextMessage(role="assistant", content=f"reply {i}"))

        original_len = len(agent._history)
        agent._maybe_compact()
        assert len(agent._history) == original_len

    def test_compaction_runs_above_threshold(self) -> None:
        """Token count above threshold triggers compaction."""
        agent = _make_agent(
            context_limit=100,
            compaction_threshold=0.5,
            token_count=80,  # above 50
            recent_turns_to_keep=2,
        )
        # Populate with enough messages
        for i in range(10):
            agent._history.append(TextMessage(role="user", content=f"msg {i}"))
            agent._history.append(TextMessage(role="assistant", content=f"reply {i}"))

        original_len = len(agent._history)
        agent._maybe_compact()

        assert len(agent._history) < original_len
        assert isinstance(agent._history[0], SummaryMessage)

    def test_history_shorter_after_compaction(self) -> None:
        agent = _make_agent(
            context_limit=100,
            compaction_threshold=0.5,
            token_count=80,
            recent_turns_to_keep=4,
        )
        for i in range(10):
            agent._history.append(TextMessage(role="user", content=f"msg {i}"))

        original_len = len(agent._history)
        agent._maybe_compact()

        # 1 (summary) + 4 (recent) = 5
        assert len(agent._history) == 5
        assert len(agent._history) < original_len

    def test_history_starts_with_summary_after_compaction(self) -> None:
        agent = _make_agent(
            context_limit=100,
            compaction_threshold=0.5,
            token_count=80,
            recent_turns_to_keep=2,
        )
        for i in range(6):
            agent._history.append(TextMessage(role="user", content=f"msg {i}"))

        agent._maybe_compact()
        assert isinstance(agent._history[0], SummaryMessage)
        assert agent._history[0].summary_generation == 1


class TestSplitPointAtomicity:
    def test_tool_call_result_groups_never_split(self) -> None:
        """If split would land on a ToolResultMessage, extend to keep the whole group."""
        agent = _make_agent(
            context_limit=100,
            compaction_threshold=0.5,
            token_count=80,
            recent_turns_to_keep=2,  # would split at index 6 (8 - 2)
        )
        # 0: user msg
        agent._history.append(TextMessage(role="user", content="hello"))
        # 1: assistant text
        agent._history.append(TextMessage(role="assistant", content="hi"))
        # 2: user msg
        agent._history.append(TextMessage(role="user", content="do something"))
        # 3: assistant text
        agent._history.append(TextMessage(role="assistant", content="ok"))
        # 4: user msg
        agent._history.append(TextMessage(role="user", content="use tool"))
        # 5: tool call
        agent._history.append(
            ToolCallMessage(
                role="assistant",
                tool_calls=(ToolCallRecord(id="tc1", function_name="get_username", arguments="{}"),),
            )
        )
        # 6: tool result  <-- split would land here with recent_turns_to_keep=2
        agent._history.append(
            ToolResultMessage(role="tool", tool_call_id="tc1", content="testuser")
        )
        # 7: assistant text
        agent._history.append(TextMessage(role="assistant", content="Your username is testuser"))

        agent._maybe_compact()

        # The tool call group (indices 5,6) must not be split.
        # After compaction: [SummaryMessage, ToolCallMessage, ToolResultMessage, TextMessage]
        # or possibly [SummaryMessage, user msg, ToolCallMessage, ToolResultMessage, TextMessage]
        # The key check: no ToolResultMessage without its preceding ToolCallMessage
        history = agent._history
        for i, msg in enumerate(history):
            if isinstance(msg, ToolResultMessage):
                # Find its matching ToolCallMessage — must be before it in history
                found = False
                for j in range(i - 1, -1, -1):
                    if isinstance(history[j], ToolCallMessage):
                        found = True
                        break
                    if isinstance(history[j], (TextMessage, SummaryMessage)):
                        break
                assert found, "ToolResultMessage found without preceding ToolCallMessage"


class TestReCompaction:
    def test_old_summary_included_in_prompt_and_generation_increments(self) -> None:
        """Re-compaction should include old summary and increment generation."""
        summarization_prompts: list[str] = []

        def tracking_completion(**kwargs: Any) -> _FakeResponse:
            if "tools" not in kwargs:
                # summarization call
                user_content = kwargs["messages"][1]["content"]
                summarization_prompts.append(user_content)
                return _FakeResponse.text("Re-summarized content.")
            return _FakeResponse.text("reply")

        agent = _make_agent(
            context_limit=100,
            compaction_threshold=0.5,
            token_count=80,
            recent_turns_to_keep=2,
            completion_func=tracking_completion,
        )

        # Start with an existing SummaryMessage
        agent._history.append(
            SummaryMessage(
                role="user",
                content="Old summary content",
                summarized_turn_count=5,
                summary_generation=1,
            )
        )
        for i in range(8):
            agent._history.append(TextMessage(role="user", content=f"msg {i}"))

        agent._maybe_compact()

        # The summarization prompt should contain the old summary
        assert len(summarization_prompts) == 1
        assert "Old summary content" in summarization_prompts[0]
        assert "Previous summary (generation 1)" in summarization_prompts[0]

        # Generation should be 2
        assert isinstance(agent._history[0], SummaryMessage)
        assert agent._history[0].summary_generation == 2


class TestIntraLoopCompaction:
    def test_large_tool_result_triggers_compaction(self) -> None:
        """Tool result pushing tokens over threshold triggers compaction before next call."""
        token_counts = iter([100, 100, 80, 10])  # first two calls below, then above, then below
        call_count = 0
        compaction_happened = False

        def variable_token_counter(**kwargs: Any) -> int:
            return next(token_counts, 10)

        responses: list[_FakeResponse] = []

        def tracking_completion(**kwargs: Any) -> _FakeResponse:
            nonlocal call_count, compaction_happened
            call_count += 1
            if "tools" not in kwargs:
                # This is the summarization call — compaction is happening
                compaction_happened = True
                return _FakeResponse.text("Compacted summary")
            if call_count == 1:
                return _FakeResponse.tool_call("tc_1", "get_username")
            return _FakeResponse.text("done")

        agent = HarvestAgent(
            config=HarvestAgentConfig(
                model="test/model",
                context_limit=100,
                compaction_threshold=0.75,  # threshold = 75
                recent_turns_to_keep=2,
            ),
            completion_func=tracking_completion,
            token_counter_func=variable_token_counter,
        )

        # Pre-populate history so there's something to compact
        for i in range(5):
            agent._history.append(TextMessage(role="user", content=f"old msg {i}"))
            agent._history.append(TextMessage(role="assistant", content=f"old reply {i}"))

        with patch("harvest.harvest_agent._get_username", return_value="testuser"):
            reply = agent.step("trigger tool")

        assert reply == "done"
        assert compaction_happened

    def test_loop_continues_after_mid_loop_compaction(self) -> None:
        """After compaction inside the tool loop, the next iteration still works."""
        call_count = 0

        def completion_func(**kwargs: Any) -> _FakeResponse:
            nonlocal call_count
            call_count += 1
            if "tools" not in kwargs:
                return _FakeResponse.text("summary")
            if call_count <= 2:
                return _FakeResponse.tool_call(f"tc_{call_count}", "get_username")
            return _FakeResponse.text("final answer")

        # Token counter: always above threshold to force compaction
        agent = HarvestAgent(
            config=HarvestAgentConfig(
                model="test/model",
                context_limit=100,
                compaction_threshold=0.5,
                recent_turns_to_keep=2,
            ),
            completion_func=completion_func,
            token_counter_func=lambda **kw: 80,
        )

        # Pre-populate so there's something to compact
        for i in range(5):
            agent._history.append(TextMessage(role="user", content=f"old {i}"))
            agent._history.append(TextMessage(role="assistant", content=f"reply {i}"))

        with patch("harvest.harvest_agent._get_username", return_value="testuser"):
            reply = agent.step("go")

        assert reply == "final answer"

    def test_all_tool_results_appended_before_compaction(self) -> None:
        """Multiple tool results in one round-trip are all appended before compaction fires."""
        compaction_histories: list[list[Message]] = []

        original_maybe_compact = HarvestAgent._maybe_compact

        def tracking_compact(self_agent: HarvestAgent) -> None:
            compaction_histories.append(list(self_agent._history))
            # Don't actually compact for this test
            return

        call_count = 0

        def completion_func(**kwargs: Any) -> _FakeResponse:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Return two tool calls
                tc1 = _FakeToolCall("tc_1", _FakeFunction("get_username"))
                tc2 = _FakeToolCall("tc_2", _FakeFunction("get_username"))
                return _FakeResponse(_FakeMessage(content=None, tool_calls=[tc1, tc2]))
            return _FakeResponse.text("done")

        agent = HarvestAgent(
            config=HarvestAgentConfig(model="test/model"),
            completion_func=completion_func,
            token_counter_func=lambda **kw: 10,
        )

        with patch.object(HarvestAgent, "_maybe_compact", tracking_compact):
            with patch("harvest.harvest_agent._get_username", return_value="testuser"):
                agent.step("go")

        # The second call to _maybe_compact (post-tool-result) should have both results
        # First call is pre-turn, second is post-tool-result
        assert len(compaction_histories) >= 2
        post_tool_history = compaction_histories[1]
        tool_results = [m for m in post_tool_history if isinstance(m, ToolResultMessage)]
        assert len(tool_results) == 2


class TestEdgeCases:
    def test_history_shorter_than_recent_turns_no_compaction(self) -> None:
        agent = _make_agent(
            context_limit=100,
            compaction_threshold=0.5,
            token_count=80,
            recent_turns_to_keep=10,
        )
        # Only 3 messages — fewer than recent_turns_to_keep
        agent._history.append(TextMessage(role="user", content="hello"))
        agent._history.append(TextMessage(role="assistant", content="hi"))
        agent._history.append(TextMessage(role="user", content="bye"))

        original_len = len(agent._history)
        agent._maybe_compact()
        assert len(agent._history) == original_len


# ---------------------------------------------------------------------------
# Workstream E: Persistence
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_conversation_store_records_summary_message(self) -> None:
        from harvest.storage.schema.agent import ConversationStore

        store = ConversationStore()

        agent = _make_agent(
            context_limit=100,
            compaction_threshold=0.5,
            token_count=80,
            recent_turns_to_keep=2,
            conversation_store=store,
        )
        agent.config = HarvestAgentConfig(
            model="test/model",
            context_limit=100,
            compaction_threshold=0.5,
            recent_turns_to_keep=2,
            session_id=agent.config.session_id,
        )

        # Populate history directly (not through step, to avoid completion calls)
        for i in range(6):
            agent._append(TextMessage(role="user", content=f"msg {i}"))

        agent._maybe_compact()

        log = store.load_log(agent.config.session_id)
        summary_rows = [r for r in log if r["message_type"] == "summary"]
        assert len(summary_rows) == 1
        content = json.loads(summary_rows[0]["content"])
        assert "summary" in content
        assert content["summarized_turn_count"] == 4  # 6 - 2 recent
        assert content["summary_generation"] == 1


# ---------------------------------------------------------------------------
# Workstream F: CLI parser tests
# ---------------------------------------------------------------------------


class TestCLICompactionFlags:
    def test_context_limit_flag(self) -> None:
        from harvest.cli import parser

        args = parser.parse_args(["agent", "--context-limit", "64000"])
        assert args.context_limit == 64000

    def test_compaction_threshold_flag(self) -> None:
        from harvest.cli import parser

        args = parser.parse_args(["agent", "--compaction-threshold", "0.8"])
        assert args.compaction_threshold == 0.8

    def test_no_compaction_flag(self) -> None:
        from harvest.cli import parser

        args = parser.parse_args(["agent", "--no-compaction"])
        assert args.no_compaction is True

    def test_defaults_are_none_and_false(self) -> None:
        from harvest.cli import parser

        args = parser.parse_args(["agent"])
        assert args.context_limit is None
        assert args.compaction_threshold is None
        assert args.no_compaction is False
