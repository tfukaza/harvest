"""MockStockService: example Service with DATA_SOURCE role only.

Used exclusively in tests and local development.
Provides a read-only stock price data source.
"""


import json
from typing import TYPE_CHECKING, Any

from harvest.interfaces.service import (
    ActionCommand,
    ActionResult,
    DataQuery,
    DataResult,
    Service,
    ServiceRole,
)
from harvest.interfaces.tool_definition import InterfaceTool, ToolArgument

if TYPE_CHECKING:
    from harvest.events.event_bus import EventBus


class MockStockService(Service):
    """A mock stock market data service with DATA_SOURCE role only.

    Supports one query type:

    - ``"price"`` — returns a fixed mock price for the given symbol

    Exposes one interface tool:

    - ``get_stock_price(symbol)`` — wraps the "price" query type

    This service is read-only.  Attempts to call ``execute`` raise
    :class:`NotImplementedError`.
    """

    def __init__(self, service_id: str = "mock-stock-data") -> None:
        self._service_id = service_id
        self._started = False

    @property
    def service_id(self) -> str:
        return self._service_id

    @property
    def roles(self) -> frozenset[ServiceRole]:
        return frozenset({ServiceRole.DATA_SOURCE})

    def get_capabilities(self) -> list[str]:
        return ["stock_price_lookup"]

    async def fetch(self, query: DataQuery) -> DataResult:
        if query.query_type == "price":
            symbol = query.params.get("symbol", "UNKNOWN")
            mock_price = len(symbol) * 10.0 + 42.0
            return DataResult(
                request_id=query.request_id,
                source_id=self.service_id,
                payload={
                    "symbol": symbol,
                    "price": mock_price,
                    "timestamp": "2026-03-22T00:00:00Z",
                },
            )
        return DataResult(
            request_id=query.request_id,
            source_id=self.service_id,
            payload={},
            error=f"unknown_query_type: '{query.query_type}'",
        )

    async def execute(self, command: ActionCommand) -> ActionResult:
        raise NotImplementedError("MockStockService has DATA_SOURCE role only")

    async def start(self, event_bus: EventBus | None = None) -> None:
        self._started = True

    async def stop(self) -> None:
        self._started = False

    def health_check(self) -> dict[str, Any]:
        return {"status": "healthy", "started": self._started}

    def get_tools(self, role: ServiceRole | None = None) -> list[InterfaceTool]:
        if role is not None and role != ServiceRole.DATA_SOURCE:
            return []

        def _get_stock_price_handler(agent_id: str, symbol: str) -> str:
            if not hasattr(self, "_fetch_callback"):
                return json.dumps({"error": "fetch_callback_not_bound"})
            return self._fetch_callback(
                agent_id,
                self._service_id,
                "price",
                {"symbol": symbol},
            )

        return [
            InterfaceTool(
                name="get_stock_price",
                short_description="Get the current market price for a stock symbol.",
                full_description=(
                    "Get the current market price for a stock symbol. "
                    "Returns the latest available price and a timestamp."
                ),
                arguments=[
                    ToolArgument(
                        name="symbol",
                        type="string",
                        description="Ticker symbol, e.g. 'AAPL'",
                        required=True,
                    ),
                ],
                returns_description=(
                    "JSON with 'symbol', 'price' (float), and 'timestamp' (ISO 8601 string)."
                ),
                service_id=self._service_id,
                service_type="data_source",
                handler=_get_stock_price_handler,
            ),
        ]
