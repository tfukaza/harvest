"""MockOrderService: example Service with ACTION role only.

Used exclusively in tests and local development.
Provides order placement and cancellation actions.
"""


import json
import uuid
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


class MockOrderService(Service):
    """A mock order execution service with ACTION role only.

    Supports two command types:

    - ``"place_order"`` — simulates placing a market order
    - ``"cancel_order"`` — simulates cancelling an order

    Exposes two interface tools:

    - ``place_market_order(symbol, side, quantity)``
    - ``cancel_order(order_id)``

    This service causes side effects (order placement).  Attempts to call
    ``fetch`` raise :class:`NotImplementedError`.
    """

    def __init__(self, service_id: str = "mock-orders") -> None:
        self._service_id = service_id
        self._started = False

    @property
    def service_id(self) -> str:
        return self._service_id

    @property
    def roles(self) -> frozenset[ServiceRole]:
        return frozenset({ServiceRole.ACTION})

    def get_capabilities(self) -> list[str]:
        return ["place_market_order", "cancel_order"]

    async def fetch(self, query: DataQuery) -> DataResult:
        raise NotImplementedError("MockOrderService has ACTION role only")

    async def execute(self, command: ActionCommand) -> ActionResult:
        if command.command_type == "place_order":
            symbol = command.params.get("symbol", "UNKNOWN")
            side = command.params.get("side", "buy")
            quantity = command.params.get("quantity", 0)
            order_id = str(uuid.uuid4())
            return ActionResult(
                request_id=command.request_id,
                action_id=self.service_id,
                payload={
                    "order_id": order_id,
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity,
                    "status": "filled",
                    "filled_at": "2026-03-22T00:00:00Z",
                },
            )
        elif command.command_type == "cancel_order":
            order_id = command.params.get("order_id", "")
            return ActionResult(
                request_id=command.request_id,
                action_id=self.service_id,
                payload={
                    "order_id": order_id,
                    "status": "cancelled",
                },
            )
        return ActionResult(
            request_id=command.request_id,
            action_id=self.service_id,
            payload={},
            error=f"unknown_command_type: '{command.command_type}'",
        )

    async def start(self, event_bus: EventBus | None = None) -> None:
        self._started = True

    async def stop(self) -> None:
        self._started = False

    def health_check(self) -> dict[str, Any]:
        return {"status": "healthy", "started": self._started}

    def get_tools(self, role: ServiceRole | None = None) -> list[InterfaceTool]:
        if role is not None and role != ServiceRole.ACTION:
            return []

        def _place_market_order_handler(
            agent_id: str,
            symbol: str,
            side: str,
            quantity: int,
        ) -> str:
            if not hasattr(self, "_execute_callback"):
                return json.dumps({"error": "execute_callback_not_bound"})
            return self._execute_callback(
                agent_id,
                self._service_id,
                "place_order",
                {"symbol": symbol, "side": side, "quantity": quantity},
            )

        def _cancel_order_handler(agent_id: str, order_id: str) -> str:
            if not hasattr(self, "_execute_callback"):
                return json.dumps({"error": "execute_callback_not_bound"})
            return self._execute_callback(
                agent_id,
                self._service_id,
                "cancel_order",
                {"order_id": order_id},
            )

        return [
            InterfaceTool(
                name="place_market_order",
                short_description="Place an immediate market order on behalf of the agent.",
                full_description=(
                    "Place an immediate market order on behalf of the agent. "
                    "The order is executed at the current market price."
                ),
                arguments=[
                    ToolArgument(
                        name="symbol",
                        type="string",
                        description="Ticker symbol, e.g. 'AAPL'",
                        required=True,
                    ),
                    ToolArgument(
                        name="side",
                        type="string",
                        description="'buy' or 'sell'",
                        required=True,
                    ),
                    ToolArgument(
                        name="quantity",
                        type="integer",
                        description="Number of shares",
                        required=True,
                    ),
                ],
                returns_description="JSON with 'order_id', 'status', and 'filled_at'.",
                service_id=self._service_id,
                service_type="action",
                handler=_place_market_order_handler,
            ),
            InterfaceTool(
                name="cancel_order",
                short_description="Cancel a pending order by its order ID.",
                full_description=(
                    "Cancel a pending order by its order ID. "
                    "Returns confirmation once the cancellation is processed."
                ),
                arguments=[
                    ToolArgument(
                        name="order_id",
                        type="string",
                        description="The order ID returned by place_market_order",
                        required=True,
                    ),
                ],
                returns_description="JSON with 'order_id' and 'status' ('cancelled').",
                service_id=self._service_id,
                service_type="action",
                handler=_cancel_order_handler,
            ),
        ]
