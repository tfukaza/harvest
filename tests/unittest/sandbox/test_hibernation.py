"""Tests for the agent hibernation system."""


import datetime as dt
import json
import threading
import time
from typing import Any
from unittest.mock import MagicMock

import pytest

from harvest.core.agent import Agent
from harvest.agent_sandbox.basic_sandbox import BasicSandbox, HIBERNATION_POLL_MIN, _AgentHandle
from harvest.agent_sandbox.channels import DMChannel
from harvest.agent_sandbox.chat import ChatRouter
from harvest.agent_sandbox.config import AgentSandboxConfig
from harvest.agent_sandbox.hibernation import EventSource, InboxEventSource, WakeEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _StubAgent(Agent):
    """Minimal agent that records step() calls."""

    def __init__(self) -> None:
        self.step_calls: list[str] = []
        self.step_called = threading.Event()

    def step(self, input_data: Any) -> str:
        self.step_calls.append(input_data)
        self.step_called.set()
        return f"ack: {input_data}"

    def reset(self) -> None:
        self.step_calls.clear()

    def get_reasoning_history(self) -> list[Any]:
        return []

    def shutdown(self) -> None:
        pass


class _FailingEventSource(EventSource):
    """Event source that always raises."""

    def poll(self, agent_id: str) -> list[WakeEvent]:
        raise RuntimeError("boom")


class _StaticEventSource(EventSource):
    """Event source that returns pre-set events once, then empty."""

    def __init__(self, events: list[WakeEvent]) -> None:
        self._events = list(events)

    def poll(self, agent_id: str) -> list[WakeEvent]:
        if self._events:
            result = self._events
            self._events = []
            return result
        return []


# ---------------------------------------------------------------------------
# WakeEvent tests
# ---------------------------------------------------------------------------


def test_wake_event_dataclass() -> None:
    event = WakeEvent(
        source_type="inbox",
        agent_id="agent-a",
        payload={"key": "value"},
    )
    assert event.source_type == "inbox"
    assert event.agent_id == "agent-a"
    assert event.payload == {"key": "value"}
    assert isinstance(event.timestamp, dt.datetime)


def test_wake_event_frozen() -> None:
    event = WakeEvent(source_type="inbox", agent_id="a")
    with pytest.raises(AttributeError):
        event.source_type = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# InboxEventSource tests
# ---------------------------------------------------------------------------


def test_inbox_event_source_empty() -> None:
    router = ChatRouter()
    router.register_agent("agent-a")
    source = InboxEventSource(router)
    assert source.poll("agent-a") == []


def test_inbox_event_source_returns_events() -> None:
    router = ChatRouter()
    router.register_agent("agent-a")
    router.register_agent("agent-b")
    dm = DMChannel(channel_id="dm:a:b", member_ids=["agent-a", "agent-b"])
    router.create_channel(dm)

    router.send_message("agent-a", "dm:a:b", "hello", "msg-1")

    source = InboxEventSource(router)
    events = source.poll("agent-b")
    assert len(events) == 1
    assert events[0].source_type == "inbox"
    assert events[0].agent_id == "agent-b"
    assert events[0].payload["sender_id"] == "agent-a"
    assert events[0].payload["content"] == "hello"
    assert events[0].payload["message_id"] == "msg-1"


def test_inbox_event_source_consumes_messages() -> None:
    router = ChatRouter()
    router.register_agent("agent-a")
    router.register_agent("agent-b")
    dm = DMChannel(channel_id="dm:a:b", member_ids=["agent-a", "agent-b"])
    router.create_channel(dm)

    router.send_message("agent-a", "dm:a:b", "hello", "msg-1")

    source = InboxEventSource(router)
    events = source.poll("agent-b")
    assert len(events) == 1

    # Second poll should return empty — read_inbox clears
    events2 = source.poll("agent-b")
    assert events2 == []


# ---------------------------------------------------------------------------
# _format_wake_events tests
# ---------------------------------------------------------------------------


def test_format_wake_events_inbox() -> None:
    import datetime as dt
    ts = dt.datetime(2026, 1, 15, 12, 30, 45, tzinfo=dt.UTC)
    events = [
        WakeEvent(
            source_type="inbox",
            agent_id="a",
            payload={"sender_id": "bob", "content": "hi there"},
            timestamp=ts,
        ),
    ]
    result = BasicSandbox._format_wake_events(events)
    assert result == "[msg: 12:30:45] @bob in #: hi there"


def test_format_wake_events_generic() -> None:
    events = [
        WakeEvent(
            source_type="timer",
            agent_id="a",
            payload={"elapsed": 30},
        ),
    ]
    result = BasicSandbox._format_wake_events(events)
    assert result == '[event:timer] {"elapsed": 30}'


def test_format_wake_events_mixed() -> None:
    import datetime as dt
    ts = dt.datetime(2026, 1, 15, 12, 30, 45, tzinfo=dt.UTC)
    events = [
        WakeEvent(source_type="inbox", agent_id="a", payload={"sender_id": "bob", "content": "hi"}, timestamp=ts),
        WakeEvent(source_type="timer", agent_id="a", payload={"tick": 1}),
    ]
    result = BasicSandbox._format_wake_events(events)
    lines = result.split("\n")
    assert len(lines) == 2
    assert lines[0] == "[msg: 12:30:45] @bob in #: hi"
    assert "timer" in lines[1]


def test_format_wake_events_ambient() -> None:
    events = [
        WakeEvent(
            source_type="inbox",
            agent_id="a",
            payload={"sender_id": "bob", "content": "hi", "channel_id": "general", "mention_type": "ambient"},
        ),
        WakeEvent(
            source_type="inbox",
            agent_id="a",
            payload={"sender_id": "alice", "content": "hey", "channel_id": "general", "mention_type": "ambient"},
        ),
    ]
    result = BasicSandbox._format_wake_events(events)
    assert result == "2 new messages in #general"


def test_format_wake_events_mention_and_ambient() -> None:
    import datetime as dt
    ts = dt.datetime(2026, 1, 15, 12, 30, 45, tzinfo=dt.UTC)
    events = [
        WakeEvent(
            source_type="inbox",
            agent_id="a",
            payload={"sender_id": "bob", "content": "hey @a", "channel_id": "general", "mention_type": "mention"},
            timestamp=ts,
        ),
        WakeEvent(
            source_type="inbox",
            agent_id="a",
            payload={"sender_id": "alice", "content": "ok", "channel_id": "general", "mention_type": "ambient"},
        ),
    ]
    result = BasicSandbox._format_wake_events(events)
    lines = result.split("\n")
    assert len(lines) == 2
    assert lines[0] == "[msg: 12:30:45] @bob in #general: hey @a"
    assert lines[1] == "1 new message in #general"


# ---------------------------------------------------------------------------
# Hibernation loop tests
# ---------------------------------------------------------------------------


def test_hibernation_loop_stops_on_stop_event() -> None:
    """Agent loop exits cleanly when stop_event is set."""
    config = AgentSandboxConfig(runner_id="test", display_name="test")
    sandbox = BasicSandbox(config=config)

    agent = _StubAgent()
    sandbox.register_agent("agent-a", agent)
    handle = sandbox.get_agent_handle("agent-a")

    # Start the loop in a thread
    thread = threading.Thread(target=sandbox._agent_loop, args=("agent-a", handle))
    thread.start()

    # Stop immediately
    handle.stop_event.set()
    handle.wake_signal.set()  # unblock the wait
    thread.join(timeout=2.0)
    assert not thread.is_alive()


def test_hibernation_loop_wakes_on_message() -> None:
    """Agent wakes from hibernation when an event arrives."""
    config = AgentSandboxConfig(runner_id="test", display_name="test")
    sandbox = BasicSandbox(config=config)

    agent = _StubAgent()
    sandbox.register_agent("agent-a", agent)
    handle = sandbox.get_agent_handle("agent-a")

    # Add a static event source with one event
    event = WakeEvent(source_type="inbox", agent_id="agent-a", payload={"sender_id": "bob", "content": "hello"})
    handle.event_sources.append(_StaticEventSource([event]))

    # Start loop
    thread = threading.Thread(target=sandbox._agent_loop, args=("agent-a", handle))
    thread.start()

    # Wake it up
    handle.wake_signal.set()

    # Wait for step to be called
    assert agent.step_called.wait(timeout=3.0)
    assert len(agent.step_calls) == 1
    assert "@bob" in agent.step_calls[0] and "hello" in agent.step_calls[0]

    # Clean up
    handle.stop_event.set()
    handle.wake_signal.set()
    thread.join(timeout=2.0)


def test_wake_signal_interrupts_sleep() -> None:
    """Setting wake_signal causes immediate poll, not waiting for full interval."""
    config = AgentSandboxConfig(runner_id="test", display_name="test")
    sandbox = BasicSandbox(config=config)

    agent = _StubAgent()
    sandbox.register_agent("agent-a", agent)
    handle = sandbox.get_agent_handle("agent-a")

    event = WakeEvent(source_type="inbox", agent_id="agent-a", payload={"sender_id": "x", "content": "fast"})
    handle.event_sources.append(_StaticEventSource([event]))

    thread = threading.Thread(target=sandbox._agent_loop, args=("agent-a", handle))
    start = time.monotonic()
    thread.start()

    # Set wake signal immediately
    handle.wake_signal.set()

    assert agent.step_called.wait(timeout=2.0)
    elapsed = time.monotonic() - start

    # Should be much faster than the 5s poll interval
    assert elapsed < HIBERNATION_POLL_MIN

    handle.stop_event.set()
    handle.wake_signal.set()
    thread.join(timeout=2.0)


def test_multiple_event_sources() -> None:
    """Events from multiple sources are merged."""
    config = AgentSandboxConfig(runner_id="test", display_name="test")
    sandbox = BasicSandbox(config=config)

    agent = _StubAgent()
    sandbox.register_agent("agent-a", agent)
    handle = sandbox.get_agent_handle("agent-a")

    event1 = WakeEvent(source_type="inbox", agent_id="agent-a", payload={"sender_id": "bob", "content": "msg1"})
    event2 = WakeEvent(source_type="timer", agent_id="agent-a", payload={"tick": 1})
    handle.event_sources.append(_StaticEventSource([event1]))
    handle.event_sources.append(_StaticEventSource([event2]))

    thread = threading.Thread(target=sandbox._agent_loop, args=("agent-a", handle))
    thread.start()
    handle.wake_signal.set()

    assert agent.step_called.wait(timeout=3.0)
    prompt = agent.step_calls[0]
    assert "@bob" in prompt and "msg1" in prompt
    assert "timer" in prompt

    handle.stop_event.set()
    handle.wake_signal.set()
    thread.join(timeout=2.0)


def test_event_source_error_does_not_crash_loop() -> None:
    """A failing event source is logged but doesn't crash the loop."""
    config = AgentSandboxConfig(runner_id="test", display_name="test")
    sandbox = BasicSandbox(config=config)

    agent = _StubAgent()
    sandbox.register_agent("agent-a", agent)
    handle = sandbox.get_agent_handle("agent-a")

    # Add a failing source AND a working source
    event = WakeEvent(source_type="inbox", agent_id="agent-a", payload={"sender_id": "x", "content": "ok"})
    handle.event_sources.append(_FailingEventSource())
    handle.event_sources.append(_StaticEventSource([event]))

    thread = threading.Thread(target=sandbox._agent_loop, args=("agent-a", handle))
    thread.start()
    handle.wake_signal.set()

    # The working source's event should still be delivered
    assert agent.step_called.wait(timeout=3.0)
    assert len(agent.step_calls) == 1

    handle.stop_event.set()
    handle.wake_signal.set()
    thread.join(timeout=2.0)


def test_add_event_source() -> None:
    """add_event_source adds to the handle's event_sources list."""
    config = AgentSandboxConfig(runner_id="test", display_name="test")
    sandbox = BasicSandbox(config=config)

    agent = _StubAgent()
    sandbox.register_agent("agent-a", agent)
    handle = sandbox.get_agent_handle("agent-a")

    initial_count = len(handle.event_sources)
    sandbox.add_event_source("agent-a", _FailingEventSource())
    assert len(handle.event_sources) == initial_count + 1


def test_step_runs_to_completion_before_hibernation() -> None:
    """Agent completes step() fully before re-entering hibernation."""
    config = AgentSandboxConfig(runner_id="test", display_name="test")
    sandbox = BasicSandbox(config=config)

    step_started = threading.Event()
    step_finished = threading.Event()

    class _SlowAgent(Agent):
        def step(self, input_data: Any) -> str:
            step_started.set()
            time.sleep(0.2)  # simulate work
            step_finished.set()
            return "done"

        def reset(self) -> None:
            pass

        def get_reasoning_history(self) -> list[Any]:
            return []

        def shutdown(self) -> None:
            pass

    agent = _SlowAgent()
    sandbox.register_agent("agent-a", agent)
    handle = sandbox.get_agent_handle("agent-a")

    event = WakeEvent(source_type="inbox", agent_id="agent-a", payload={"sender_id": "x", "content": "go"})
    handle.event_sources.append(_StaticEventSource([event]))

    thread = threading.Thread(target=sandbox._agent_loop, args=("agent-a", handle))
    thread.start()
    handle.wake_signal.set()

    # Wait for step to start
    assert step_started.wait(timeout=3.0)
    # step_finished should happen before the next hibernation cycle
    assert step_finished.wait(timeout=3.0)

    handle.stop_event.set()
    handle.wake_signal.set()
    thread.join(timeout=2.0)


def test_register_agent_auto_wires_inbox_source() -> None:
    """register_agent automatically adds an InboxEventSource."""
    config = AgentSandboxConfig(runner_id="test", display_name="test")
    sandbox = BasicSandbox(config=config)

    agent = _StubAgent()
    sandbox.register_agent("agent-a", agent)
    handle = sandbox.get_agent_handle("agent-a")

    inbox_sources = [s for s in handle.event_sources if isinstance(s, InboxEventSource)]
    assert len(inbox_sources) == 1
