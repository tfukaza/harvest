"""Unit tests for SandboxGateway event relay."""


import time

from harvest.agent_sandbox.chat_events import NewChatMessage, SendChatMessage
from harvest.agent_sandbox.event_helpers import SyncEventBus
from harvest.agent_sandbox.sandbox_gateway import SandboxGateway
from harvest.events.base import (
    DataFetchRequested,
    ExternalEventFired,
)


def _wait_for(captured: list, timeout: float = 1.0) -> bool:
    """Block until captured has at least one item."""
    deadline = time.monotonic() + timeout
    while not captured and time.monotonic() < deadline:
        time.sleep(0.01)
    return len(captured) > 0


def test_inbound_relay_external_event():
    """ExternalEventFired on orchestrator bus should appear on sandbox bus."""
    orch_bus = SyncEventBus(name="orch")
    sandbox_bus = SyncEventBus(name="sandbox")
    gw = SandboxGateway("test", orch_bus, sandbox_bus)
    gw.start()

    captured: list = []
    sandbox_bus.on(ExternalEventFired, lambda e: captured.append(e))

    event = ExternalEventFired(source_id="newsapi", event_type="alert", payload={"x": 1})
    orch_bus.dispatch(event)

    assert len(captured) == 1
    assert captured[0].source_id == "newsapi"
    gw.stop()


def test_outbound_relay_audit_event():
    """DataFetchRequested on sandbox bus should appear on orchestrator bus."""
    orch_bus = SyncEventBus(name="orch")
    sandbox_bus = SyncEventBus(name="sandbox")
    gw = SandboxGateway("test", orch_bus, sandbox_bus)
    gw.start()

    captured: list = []
    orch_bus.on(DataFetchRequested, lambda e: captured.append(e))

    event = DataFetchRequested(
        agent_id="a1", service_id="svc", query_type="q",
        sandbox_id="test", source_id="svc", request_id="r1",
    )
    sandbox_bus.dispatch(event)

    assert len(captured) == 1
    assert captured[0].agent_id == "a1"
    gw.stop()


def test_chat_events_not_relayed_outbound():
    """Intra-sandbox chat events must NOT appear on orchestrator bus."""
    orch_bus = SyncEventBus(name="orch")
    sandbox_bus = SyncEventBus(name="sandbox")
    gw = SandboxGateway("test", orch_bus, sandbox_bus)
    gw.start()

    captured: list = []
    orch_bus.on(SendChatMessage, lambda e: captured.append(e))
    orch_bus.on(NewChatMessage, lambda e: captured.append(e))

    sandbox_bus.dispatch(SendChatMessage(
        sender_id="a1", channel_id="ch1", content="hi", message_id="m1",
    ))
    sandbox_bus.dispatch(NewChatMessage(
        channel_id="ch1", sender_id="a1", recipient_ids=["a2"],
    ))

    assert len(captured) == 0
    gw.stop()


def test_stop_unsubscribes():
    """After stop(), events should no longer be relayed."""
    orch_bus = SyncEventBus(name="orch")
    sandbox_bus = SyncEventBus(name="sandbox")
    gw = SandboxGateway("test", orch_bus, sandbox_bus)
    gw.start()
    gw.stop()

    captured: list = []
    sandbox_bus.on(ExternalEventFired, lambda e: captured.append(e))

    orch_bus.dispatch(ExternalEventFired(
        source_id="x", event_type="y", payload={},
    ))

    assert len(captured) == 0
