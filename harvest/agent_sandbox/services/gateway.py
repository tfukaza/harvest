"""Gateway that relays events between the orchestrator bus and a per-sandbox bus.

Inbound (orchestrator -> sandbox):
    ExternalEventFired -- so SandboxServiceRouter can subscribe locally.

Outbound (sandbox -> orchestrator):
    Audit events only: DataFetchRequested, DataFetchCompleted, ActionRequested,
    ActionCompleted, ExternalEventDelivered, ToolsAutoRegistered, ToolSpecsInjected.

Everything else (chat events, lifecycle events, service request/response events)
stays on the sandbox bus and is NOT relayed.
"""


import logging
from typing import Any, Callable

from harvest.events.base import (
    ActionCompleted,
    ActionRequested,
    DataFetchCompleted,
    DataFetchRequested,
    ExternalEventDelivered,
    ExternalEventFired,
    HarvestEvent,
    ToolsAutoRegistered,
    ToolSpecsInjected,
)

logger = logging.getLogger(__name__)

# Audit events relayed sandbox -> orchestrator (whitelist approach)
OUTBOUND_EVENT_TYPES: set[type[HarvestEvent]] = {
    DataFetchRequested,
    DataFetchCompleted,
    ActionRequested,
    ActionCompleted,
    ExternalEventDelivered,
    ToolsAutoRegistered,
    ToolSpecsInjected,
}

# Events relayed orchestrator -> sandbox
INBOUND_EVENT_TYPES: set[type[HarvestEvent]] = {
    ExternalEventFired,
}


class SandboxGateway:
    """Relays events between the orchestrator bus and a per-sandbox bus.

    The orchestrator bus may be a bubus-backed EventBus or a SyncEventBus.
    The sandbox bus is always a SyncEventBus. Both share the same
    on/off/dispatch interface.

    Uses a whitelist: only explicitly listed event types flow outbound.
    Everything else stays local by default.
    """

    def __init__(
        self,
        sandbox_id: str,
        orchestrator_bus: Any,
        sandbox_bus: Any,
    ) -> None:
        self._sandbox_id = sandbox_id
        self._orchestrator_bus = orchestrator_bus
        self._sandbox_bus = sandbox_bus
        self._inbound_handlers: list[tuple[type[HarvestEvent], Callable]] = []
        self._outbound_handlers: list[tuple[type[HarvestEvent], Callable]] = []

    def start(self) -> None:
        """Subscribe to both buses and begin relaying."""
        # Inbound: orchestrator -> sandbox
        for event_type in INBOUND_EVENT_TYPES:
            handler = self._make_relay_handler(self._sandbox_bus)
            self._orchestrator_bus.on(event_type, handler)
            self._inbound_handlers.append((event_type, handler))

        # Outbound: sandbox -> orchestrator (audit events only)
        for event_type in OUTBOUND_EVENT_TYPES:
            handler = self._make_outbound_handler()
            self._sandbox_bus.on(event_type, handler)
            self._outbound_handlers.append((event_type, handler))

    def stop(self) -> None:
        """Unsubscribe from both buses."""
        for event_type, handler in self._inbound_handlers:
            self._orchestrator_bus.off(event_type, handler)
        for event_type, handler in self._outbound_handlers:
            self._sandbox_bus.off(event_type, handler)
        self._inbound_handlers.clear()
        self._outbound_handlers.clear()

    @staticmethod
    def _make_relay_handler(target_bus: Any) -> Callable[[HarvestEvent], None]:
        """Create a handler that re-dispatches events onto the target bus."""
        def _relay(event: HarvestEvent) -> None:
            target_bus.dispatch(event)
        return _relay

    def _make_outbound_handler(self) -> Callable[[HarvestEvent], None]:
        """Create a handler that relays events to the orchestrator bus."""
        orch = self._orchestrator_bus
        def _relay(event: HarvestEvent) -> None:
            orch.dispatch(event)
        return _relay
