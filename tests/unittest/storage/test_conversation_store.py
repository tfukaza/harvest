"""Tests for the ConversationStore persistence layer."""

from __future__ import annotations

from harvest.harvest_agent import (
    TextMessage,
    ToolCallMessage,
    ToolCallRecord,
    ToolResultMessage,
)
from harvest.storage.schema.agent import ConversationStore


def test_append_and_load_round_trip() -> None:
    store = ConversationStore()

    store.append_message("s1", 0, TextMessage(role="user", content="hello"))
    store.append_message("s1", 1, TextMessage(role="assistant", content="hi"))

    log = store.load_log("s1")
    assert len(log) == 2
    assert log[0]["role"] == "user"
    assert log[0]["content"] == "hello"
    assert log[0]["message_type"] == "text"
    assert log[1]["role"] == "assistant"
    assert log[1]["content"] == "hi"


def test_ordering_by_turn_index() -> None:
    store = ConversationStore()

    # Insert out of order
    store.append_message("s1", 2, TextMessage(role="assistant", content="c"))
    store.append_message("s1", 0, TextMessage(role="user", content="a"))
    store.append_message("s1", 1, TextMessage(role="assistant", content="b"))

    log = store.load_log("s1")
    assert [r["content"] for r in log] == ["a", "b", "c"]


def test_empty_session() -> None:
    store = ConversationStore()

    log = store.load_log("nonexistent")
    assert log == []


def test_list_sessions() -> None:
    store = ConversationStore()

    store.append_message("beta", 0, TextMessage(role="user", content="x"))
    store.append_message("alpha", 0, TextMessage(role="user", content="y"))

    sessions = store.list_sessions()
    assert sessions == ["alpha", "beta"]


def test_tool_call_message_serialization() -> None:
    store = ConversationStore()

    tc = ToolCallRecord(id="tc_1", function_name="get_username", arguments="{}")
    msg = ToolCallMessage(role="assistant", content=None, tool_calls=(tc,))
    store.append_message("s1", 0, msg)

    log = store.load_log("s1")
    assert len(log) == 1
    assert log[0]["message_type"] == "tool_call"
    assert log[0]["tool_calls_json"] is not None
    assert "get_username" in log[0]["tool_calls_json"]


def test_tool_result_message_serialization() -> None:
    store = ConversationStore()

    msg = ToolResultMessage(role="tool", tool_call_id="tc_1", content="testuser")
    store.append_message("s1", 0, msg)

    log = store.load_log("s1")
    assert len(log) == 1
    assert log[0]["message_type"] == "tool_result"
    assert log[0]["tool_call_id"] == "tc_1"
    assert log[0]["content"] == "testuser"
