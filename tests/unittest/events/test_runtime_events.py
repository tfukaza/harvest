"""Contract tests for generalized runtime events."""

from __future__ import annotations

import datetime as dt
from dataclasses import is_dataclass


def test_resource_update_event_exists() -> None:
    from harvest.events.events import ResourceUpdateEvent

    assert is_dataclass(ResourceUpdateEvent)


def test_agent_lifecycle_event_exists() -> None:
    from harvest.events.events import AgentLifecycleEvent

    assert is_dataclass(AgentLifecycleEvent)


def test_tool_call_events_exist() -> None:
    from harvest.events.events import ToolCallEvent, ToolResultEvent

    assert is_dataclass(ToolCallEvent)
    assert is_dataclass(ToolResultEvent)


def test_runtime_lifecycle_event_exists() -> None:
    from harvest.events.events import RuntimeLifecycleEvent

    assert is_dataclass(RuntimeLifecycleEvent)


def test_event_types_include_runtime_categories() -> None:
    from harvest.events.events import EventTypes

    assert EventTypes.RESOURCE_UPDATE == "resource_update"
    assert EventTypes.AGENT_LIFECYCLE == "agent_lifecycle"
    assert EventTypes.RUNTIME_LIFECYCLE == "runtime_lifecycle"
    assert EventTypes.TOOL_CALL == "tool_call"
    assert EventTypes.TOOL_RESULT == "tool_result"


def test_runtime_lifecycle_event_shape() -> None:
    from harvest.events.events import RuntimeLifecycleEvent

    event = RuntimeLifecycleEvent(runtime_id="sandbox-1", state="starting", timestamp=dt.datetime.now(dt.UTC))

    assert event.runtime_id == "sandbox-1"
    assert event.state == "starting"