"""Unit tests for dispatch_and_wait and wait_for_event."""


import threading

from harvest.agent_sandbox.event_helpers import (
    SyncEventBus,
    dispatch_and_wait,
    wait_for_event,
)
from harvest.events.base import HarvestEvent


class PingEvent(HarvestEvent):
    request_id: str = ""


class PongEvent(HarvestEvent):
    request_id: str = ""


def test_dispatch_and_wait_happy_path():
    """dispatch_and_wait should return the matching response."""
    bus = SyncEventBus(name="test")

    # Simulate a server that responds to PingEvent with PongEvent
    def _server(event: PingEvent) -> None:
        bus.dispatch(PongEvent(request_id=event.request_id))

    bus.on(PingEvent, _server)

    result = dispatch_and_wait(
        bus,
        request=PingEvent(request_id="r1"),
        response_types=(PongEvent,),
        filter_fn=lambda e: e.request_id == "r1",
        timeout=2.0,
    )

    assert result is not None
    assert isinstance(result, PongEvent)
    assert result.request_id == "r1"


def test_dispatch_and_wait_timeout():
    """dispatch_and_wait should return None on timeout."""
    bus = SyncEventBus(name="test")

    result = dispatch_and_wait(
        bus,
        request=PingEvent(request_id="r2"),
        response_types=(PongEvent,),
        filter_fn=lambda e: e.request_id == "r2",
        timeout=0.1,
    )

    assert result is None


def test_dispatch_and_wait_filter():
    """dispatch_and_wait should only match events passing the filter."""
    bus = SyncEventBus(name="test")

    def _server(event: PingEvent) -> None:
        # Respond with wrong request_id first, then correct one
        bus.dispatch(PongEvent(request_id="wrong"))
        bus.dispatch(PongEvent(request_id=event.request_id))

    bus.on(PingEvent, _server)

    result = dispatch_and_wait(
        bus,
        request=PingEvent(request_id="r3"),
        response_types=(PongEvent,),
        filter_fn=lambda e: e.request_id == "r3",
        timeout=2.0,
    )

    assert result is not None
    assert result.request_id == "r3"


def test_wait_for_event_happy_path():
    """wait_for_event should capture a matching event dispatched externally."""
    bus = SyncEventBus(name="test")

    # Dispatch from another thread after a brief delay
    def _send():
        bus.dispatch(PongEvent(request_id="w1"))

    threading.Timer(0.05, _send).start()

    result = wait_for_event(
        bus,
        event_types=(PongEvent,),
        filter_fn=lambda e: e.request_id == "w1",
        timeout=2.0,
    )

    assert result is not None
    assert result.request_id == "w1"


def test_wait_for_event_timeout():
    """wait_for_event should return None on timeout."""
    bus = SyncEventBus(name="test")

    result = wait_for_event(
        bus,
        event_types=(PongEvent,),
        filter_fn=lambda e: True,
        timeout=0.1,
    )

    assert result is None
