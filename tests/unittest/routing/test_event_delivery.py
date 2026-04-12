"""Tests for EVENT_SOURCE delivery through SandboxServiceRouter."""


import json
from typing import Any

import pytest

from harvest.agent_sandbox.services.router import SandboxServiceRouter
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


class _ManualEventService(Service):
    def __init__(self, service_id: str = "price-alerts") -> None:
        self._id = service_id

    @property
    def service_id(self) -> str:
        return self._id

    @property
    def roles(self) -> frozenset[ServiceRole]:
        return frozenset({ServiceRole.EVENT_SOURCE})

    def get_capabilities(self) -> list[str]:
        return ["manual"]

    async def fetch(self, query: DataQuery) -> DataResult:
        raise NotImplementedError

    async def execute(self, command: ActionCommand) -> ActionResult:
        raise NotImplementedError

    async def start(self, event_bus: Any = None) -> None:
        pass

    async def stop(self) -> None:
        pass

    def health_check(self) -> dict[str, Any]:
        return {"status": "healthy"}

    def get_tools(self, role: ServiceRole | None = None) -> list:
        return []


# ---------------------------------------------------------------------------
# Subscription and delivery
# ---------------------------------------------------------------------------


def test_subscribed_agent_receives_event() -> None:
    router = SandboxServiceRouter(sandbox_id="test-sandbox")
    router.register_service(_ManualEventService("price-alerts"))

    wake_calls: list[str] = []
    router.register_agent_wake_callback("agent-1", lambda: wake_calls.append("agent-1"))
    router.subscribe_agent("agent-1", "price-alerts")

    policy = AgentPolicy(
        name="trader",
        allowed_services=(ServicePermission("price-alerts"),),
    )
    _, tool_map = router.make_service_tools("agent-1", policy)
    assert "read_event_notifications" in tool_map

    router.deliver_external_event("price-alerts", "threshold_crossed", {"symbol": "AAPL", "price": 200.0})

    assert "agent-1" in wake_calls

    notifications_json = tool_map["read_event_notifications"]()
    notifications = json.loads(notifications_json)
    assert len(notifications) == 1
    assert notifications[0]["source_id"] == "price-alerts"
    assert notifications[0]["event_type"] == "threshold_crossed"
    assert notifications[0]["payload"]["symbol"] == "AAPL"


def test_unsubscribed_agent_does_not_receive_event() -> None:
    router = SandboxServiceRouter(sandbox_id="test-sandbox")
    router.register_service(_ManualEventService("price-alerts"))

    wake_calls: list[str] = []
    router.register_agent_wake_callback("agent-A", lambda: wake_calls.append("agent-A"))
    router.register_agent_wake_callback("agent-B", lambda: wake_calls.append("agent-B"))

    # Only agent-A is subscribed
    router.subscribe_agent("agent-A", "price-alerts")

    policy_a = AgentPolicy(
        name="a",
        allowed_services=(ServicePermission("price-alerts"),),
    )
    policy_b = AgentPolicy(name="b", allowed_services=())

    _, map_a = router.make_service_tools("agent-A", policy_a)
    _, map_b = router.make_service_tools("agent-B", policy_b)

    router.deliver_external_event("price-alerts", "tick", {"value": 42})

    assert "agent-A" in wake_calls
    assert "agent-B" not in wake_calls

    notifs_a = json.loads(map_a["read_event_notifications"]())
    assert len(notifs_a) == 1

    assert "read_event_notifications" not in map_b


def test_multiple_events_accumulate_until_read() -> None:
    router = SandboxServiceRouter(sandbox_id="test-sandbox")
    router.register_service(_ManualEventService("alerts"))
    router.register_agent_wake_callback("a", lambda: None)
    router.subscribe_agent("a", "alerts")

    policy = AgentPolicy(name="p", allowed_services=(ServicePermission("alerts"),))
    _, tool_map = router.make_service_tools("a", policy)

    router.deliver_external_event("alerts", "evt1", {"n": 1})
    router.deliver_external_event("alerts", "evt2", {"n": 2})
    router.deliver_external_event("alerts", "evt3", {"n": 3})

    notifs = json.loads(tool_map["read_event_notifications"]())
    assert len(notifs) == 3
    assert [n["event_type"] for n in notifs] == ["evt1", "evt2", "evt3"]


def test_read_clears_queue() -> None:
    router = SandboxServiceRouter(sandbox_id="test-sandbox")
    router.register_service(_ManualEventService("alerts"))
    router.register_agent_wake_callback("a", lambda: None)
    router.subscribe_agent("a", "alerts")

    policy = AgentPolicy(name="p", allowed_services=(ServicePermission("alerts"),))
    _, tool_map = router.make_service_tools("a", policy)

    router.deliver_external_event("alerts", "evt", {})

    first_read = json.loads(tool_map["read_event_notifications"]())
    assert len(first_read) == 1

    second_read = json.loads(tool_map["read_event_notifications"]())
    assert len(second_read) == 0


def test_subscribe_to_unregistered_source_raises() -> None:
    router = SandboxServiceRouter()
    with pytest.raises(ValueError, match="unknown event source"):
        router.subscribe_agent("a", "nonexistent-source")


# ---------------------------------------------------------------------------
# Service registry
# ---------------------------------------------------------------------------


def test_register_duplicate_event_service_raises() -> None:
    router = SandboxServiceRouter()
    router.register_service(_ManualEventService("dup"))
    with pytest.raises(ValueError, match="already registered"):
        router.register_service(_ManualEventService("dup"))


def test_list_services() -> None:
    router = SandboxServiceRouter()
    router.register_service(_ManualEventService("src-a"))
    router.register_service(_ManualEventService("src-b"))
    assert set(router.list_services()) == {"src-a", "src-b"}


# ---------------------------------------------------------------------------
# Unregister agent
# ---------------------------------------------------------------------------


def test_unregister_agent_removes_subscriptions_and_queue() -> None:
    router = SandboxServiceRouter()
    router.register_service(_ManualEventService("alerts"))
    router.register_agent_wake_callback("a", lambda: None)
    router.subscribe_agent("a", "alerts")

    router.deliver_external_event("alerts", "x", {})
    router.unregister_agent("a")

    router.deliver_external_event("alerts", "y", {})

    assert "a" not in router._pending_events
    assert "a" not in router._agent_subscriptions
    assert "a" not in router._agent_wake_callbacks


# ---------------------------------------------------------------------------
# Event bus wiring
# ---------------------------------------------------------------------------


def test_external_event_fired_via_event_bus_wires_handler() -> None:
    """set_event_bus subscribes to ExternalEventFired; firing routes to agents."""
    from harvest.events.base import ExternalEventFired

    handlers: dict[type, list] = {}

    class _MockBus:
        def on(self, event_type: type, handler: Any) -> None:
            handlers.setdefault(event_type, []).append(handler)

        def dispatch(self, event: Any) -> None:
            for h in handlers.get(type(event), []):
                h(event)

    router = SandboxServiceRouter(sandbox_id="test-sandbox")
    router.register_service(_ManualEventService("price-alerts"))
    router.register_agent_wake_callback("agent-1", lambda: None)
    router.subscribe_agent("agent-1", "price-alerts")

    policy = AgentPolicy(
        name="p",
        allowed_services=(ServicePermission("price-alerts"),),
    )
    _, tool_map = router.make_service_tools("agent-1", policy)

    router.set_event_bus(_MockBus())  # type: ignore[arg-type]

    for h in handlers.get(ExternalEventFired, []):
        h(ExternalEventFired(
            source_id="price-alerts",
            event_type="threshold",
            payload={"value": 99},
        ))

    notifs = json.loads(tool_map["read_event_notifications"]())
    assert len(notifs) == 1
    assert notifs[0]["event_type"] == "threshold"
