"""Contract tests for generalized runtime events."""

from __future__ import annotations

from harvest.events import (
    AgentLifecycleChanged,
    HarvestEvent,
    LifecycleState,
    ResourceUpdated,
    RuntimeLifecycleChanged,
    ToolCallCompleted,
    ToolCallRequested,
)


def test_resource_update_event_exists() -> None:
    event = ResourceUpdated(source="runtime", resource_id="res-1")
    assert isinstance(event, HarvestEvent)


def test_agent_lifecycle_event_exists() -> None:
    event = AgentLifecycleChanged(agent_id="agent-1", state=LifecycleState.STARTING, source="runtime")
    assert isinstance(event, HarvestEvent)


def test_tool_call_events_exist() -> None:
    request_event = ToolCallRequested(agent_id="agent-1", tool_name="search", source="runtime")
    result_event = ToolCallCompleted(agent_id="agent-1", tool_name="search", source="runtime")

    assert isinstance(request_event, HarvestEvent)
    assert isinstance(result_event, HarvestEvent)


def test_runtime_lifecycle_event_exists() -> None:
    event = RuntimeLifecycleChanged(runtime_id="sandbox-1", state=LifecycleState.STARTING, source="runtime")
    assert isinstance(event, HarvestEvent)


def test_runtime_lifecycle_event_shape() -> None:
    event = RuntimeLifecycleChanged(runtime_id="sandbox-1", state=LifecycleState.STARTING, source="runtime")

    assert event.runtime_id == "sandbox-1"
    assert event.state == LifecycleState.STARTING
