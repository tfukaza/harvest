"""Tests for event notification injection into the system prompt.

- When ExternalEventFired is delivered, notification block appears
- After read_event_notifications(), block is removed
- Multiple events from different sources each produce separate blocks
- All blocks cleared together on read_event_notifications()
"""


import json
import time
from typing import Any

import pytest

from harvest.agent_sandbox.service_router import SandboxServiceRouter
from harvest.agent_sandbox.system_prompt_builder import SystemPromptBuilder
from harvest.events.event_bus import EventBus
from harvest.events.base import ExternalEventFired
from harvest.interfaces.service import (
    ActionCommand,
    ActionResult,
    DataQuery,
    DataResult,
    Service,
    ServicePermission,
    ServiceRole,
)
from harvest.core.policy import AgentPolicy


# ---------------------------------------------------------------------------
# Stub Service (EVENT_SOURCE role)
# ---------------------------------------------------------------------------


class _MockEventSource(Service):
    def __init__(self, service_id: str = "price-alerts") -> None:
        self._id = service_id
        self._bus = None

    @property
    def service_id(self) -> str:
        return self._id

    @property
    def roles(self) -> frozenset[ServiceRole]:
        return frozenset({ServiceRole.EVENT_SOURCE})

    def get_capabilities(self) -> list[str]:
        return ["price_alerts"]

    async def fetch(self, query: DataQuery) -> DataResult:
        raise NotImplementedError

    async def execute(self, command: ActionCommand) -> ActionResult:
        raise NotImplementedError

    async def start(self, event_bus: Any = None) -> None:
        self._bus = event_bus

    async def stop(self) -> None:
        self._bus = None

    def health_check(self) -> dict[str, Any]:
        return {"status": "healthy"}

    def get_tools(self, role: ServiceRole | None = None) -> list:
        return []

    def fire(self, event_type: str, payload: dict) -> None:
        if self._bus:
            self._bus.dispatch(ExternalEventFired(
                source_id=self._id,
                event_type=event_type,
                payload=payload,
            ))


# ---------------------------------------------------------------------------
# Test helpers: simulate what BasicSandbox does
# ---------------------------------------------------------------------------


def _setup_router_with_agent(
    source_id: str = "price-alerts",
    agent_id: str = "agent-1",
) -> tuple[SandboxServiceRouter, SystemPromptBuilder, list[str]]:
    """Set up a router, subscribe an agent, and wire the notification callback.

    Returns (router, builder, cleared_for_agent).
    """
    builder = SystemPromptBuilder()
    cleared: list[str] = []

    def _add_notification(aid: str, src_id: str, evt_type: str) -> None:
        block = (
            f"## Pending Event Notification\n\n"
            f"A new event has arrived from source '{src_id}' "
            f"(type: '{evt_type}'). Call read_event_notifications() to read it."
        )
        builder.append("event_notifications", block)

    def _clear_notifications(aid: str) -> None:
        builder.clear("event_notifications")
        cleared.append(aid)

    router = SandboxServiceRouter(sandbox_id="test")
    router.register_event_notification_callback(_add_notification)

    es = _MockEventSource(source_id)
    router.register_service(es)
    router.register_agent_wake_callback(agent_id, wake_fn=lambda: None)
    router.subscribe_agent(agent_id, source_id)

    policy = AgentPolicy(
        name="test",
        allowed_services=(ServicePermission(source_id),),
    )
    _, tool_map = router.make_service_tools(
        agent_id, policy, clear_notifications_callback=_clear_notifications
    )

    return router, builder, cleared, tool_map


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_event_delivery_injects_notification_block() -> None:
    """When ExternalEventFired is delivered, a notification block appears."""
    router, builder, _, _ = _setup_router_with_agent()

    router.deliver_external_event("price-alerts", "price_alert", {"symbol": "AAPL"})

    result = builder.build("Base prompt.")
    assert "Pending Event Notification" in result
    assert "price-alerts" in result
    assert "price_alert" in result
    assert "read_event_notifications()" in result


def test_read_event_notifications_clears_notification_block() -> None:
    """After read_event_notifications(), the notification block is removed."""
    router, builder, cleared, tool_map = _setup_router_with_agent()

    router.deliver_external_event("price-alerts", "price_alert", {"symbol": "AAPL"})

    # Block should be present
    assert "Pending Event Notification" in builder.build("Base.")

    # Call read_event_notifications
    tool_map["read_event_notifications"]()

    # Block should be cleared
    result = builder.build("Base.")
    assert "Pending Event Notification" not in result
    assert result == "Base."


def test_multiple_events_from_different_sources_produce_separate_blocks() -> None:
    """Multiple events from different sources each get their own block."""
    # Set up two event sources
    builder = SystemPromptBuilder()
    cleared: list[str] = []

    def _add_notification(aid: str, src_id: str, evt_type: str) -> None:
        block = (
            f"## Pending Event Notification\n\n"
            f"A new event has arrived from source '{src_id}' "
            f"(type: '{evt_type}'). Call read_event_notifications() to read it."
        )
        builder.append("event_notifications", block)

    def _clear_notifications(aid: str) -> None:
        builder.clear("event_notifications")
        cleared.append(aid)

    router = SandboxServiceRouter(sandbox_id="test")
    router.register_event_notification_callback(_add_notification)

    es1 = _MockEventSource("source-a")
    es2 = _MockEventSource("source-b")
    router.register_service(es1)
    router.register_service(es2)

    agent_id = "agent-1"
    router.register_agent_wake_callback(agent_id, wake_fn=lambda: None)
    router.subscribe_agent(agent_id, "source-a")
    router.subscribe_agent(agent_id, "source-b")

    policy = AgentPolicy(
        name="test",
        allowed_services=(
            ServicePermission("source-a"),
            ServicePermission("source-b"),
        ),
    )
    _, tool_map = router.make_service_tools(
        agent_id, policy, clear_notifications_callback=_clear_notifications
    )

    router.deliver_external_event("source-a", "event_type_a", {})
    router.deliver_external_event("source-b", "event_type_b", {})

    result = builder.build("Base.")
    assert "source-a" in result
    assert "source-b" in result
    assert "event_type_a" in result
    assert "event_type_b" in result


def test_read_event_notifications_clears_all_blocks() -> None:
    """After read_event_notifications(), ALL pending blocks are cleared."""
    builder = SystemPromptBuilder()

    def _add_notification(aid: str, src_id: str, evt_type: str) -> None:
        block = (
            f"## Pending Event Notification\n\n"
            f"A new event from '{src_id}' (type: '{evt_type}'). Call read_event_notifications()."
        )
        builder.append("event_notifications", block)

    def _clear_notifications(aid: str) -> None:
        builder.clear("event_notifications")

    router = SandboxServiceRouter(sandbox_id="test")
    router.register_event_notification_callback(_add_notification)

    es1 = _MockEventSource("src-a")
    es2 = _MockEventSource("src-b")
    router.register_service(es1)
    router.register_service(es2)

    agent_id = "agent-1"
    router.register_agent_wake_callback(agent_id, wake_fn=lambda: None)
    router.subscribe_agent(agent_id, "src-a")
    router.subscribe_agent(agent_id, "src-b")

    policy = AgentPolicy(
        name="test",
        allowed_services=(
            ServicePermission("src-a"),
            ServicePermission("src-b"),
        ),
    )
    _, tool_map = router.make_service_tools(
        agent_id, policy, clear_notifications_callback=_clear_notifications
    )

    router.deliver_external_event("src-a", "type-a", {})
    router.deliver_external_event("src-b", "type-b", {})

    # Both blocks present
    assert "src-a" in builder.build("Base.")
    assert "src-b" in builder.build("Base.")

    # Clear all
    tool_map["read_event_notifications"]()

    result = builder.build("Base.")
    assert result == "Base."


def test_notification_format_contains_read_instruction() -> None:
    """Notification includes the instruction to call read_event_notifications()."""
    router, builder, _, _ = _setup_router_with_agent(source_id="earnings", agent_id="a2")

    router.deliver_external_event("earnings", "earnings_report", {"symbol": "GOOG"})

    result = builder.build("Base.")
    assert "read_event_notifications()" in result
    assert "earnings" in result
    assert "earnings_report" in result
