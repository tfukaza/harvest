"""MockAlertService: example Service with EVENT_SOURCE role only.

Used exclusively in tests and local development.
Pushes price alert events to subscribed agents via the event bus.

EventSources follow the inbox model — they have no interface tools.
Events are self-describing payloads read via read_event_notifications().
"""


from typing import TYPE_CHECKING, Any

from harvest.interfaces.service import (
    ActionCommand,
    ActionResult,
    DataQuery,
    DataResult,
    Service,
    ServiceRole,
)

if TYPE_CHECKING:
    from harvest.events.event_bus import EventBus
    from harvest.interfaces.tool_definition import InterfaceTool


class MockAlertService(Service):
    """A mock price alert service with EVENT_SOURCE role only.

    Fires ``"price_alert"`` events when manually triggered via
    :meth:`fire_alert`.  Events are self-describing payloads — agents read
    delivered notifications through ``read_event_notifications()``.

    This service cannot fetch data or execute actions.  Attempts to call
    ``fetch`` or ``execute`` raise :class:`NotImplementedError`.
    """

    def __init__(self, service_id: str = "mock-price-alerts") -> None:
        self._service_id = service_id
        self._event_bus: EventBus | None = None
        self._started = False

    @property
    def service_id(self) -> str:
        return self._service_id

    @property
    def roles(self) -> frozenset[ServiceRole]:
        return frozenset({ServiceRole.EVENT_SOURCE})

    def get_capabilities(self) -> list[str]:
        return ["price_threshold_alerts"]

    async def fetch(self, query: DataQuery) -> DataResult:
        raise NotImplementedError("MockAlertService has EVENT_SOURCE role only")

    async def execute(self, command: ActionCommand) -> ActionResult:
        raise NotImplementedError("MockAlertService has EVENT_SOURCE role only")

    async def start(self, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus
        self._started = True

    async def stop(self) -> None:
        self._started = False
        self._event_bus = None

    def health_check(self) -> dict[str, Any]:
        return {"status": "healthy", "started": self._started}

    def get_tools(self, role: ServiceRole | None = None) -> list[InterfaceTool]:
        # EventSources follow the inbox model — no interface tools.
        return []

    def fire_alert(self, symbol: str, price: float, threshold: float) -> None:
        """Manually fire a price alert event for testing.

        Args:
            symbol: Ticker symbol that crossed the threshold.
            price: Current price.
            threshold: The threshold that was crossed.
        """
        if self._event_bus is None:
            return

        from harvest.events.base import ExternalEventFired

        self._event_bus.dispatch(
            ExternalEventFired(
                source_id=self._service_id,
                event_type="price_alert",
                payload={
                    "symbol": symbol,
                    "current_price": price,
                    "threshold": threshold,
                    "direction": "above" if price >= threshold else "below",
                    "message": (
                        f"{symbol} crossed {threshold}: current price is {price}"
                    ),
                },
            )
        )
