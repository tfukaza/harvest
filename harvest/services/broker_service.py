import datetime as dt
from typing import TYPE_CHECKING, Dict, Any

from .service_interface import Service
from ..events.event_bus import EventBus
from ..definitions import Order, Account, Position, OrderSide
from ..util.helper import mark_up, mark_down

if TYPE_CHECKING:
    from ..events.events import OrderPlacedEvent


class BrokerService(Service):
    """
    Service for managing broker operations including order placement and account management.
    Acts as an interface between algorithms and the underlying broker implementations.
    """

    def __init__(self, brokers: Dict[str, Any]):
        super().__init__("broker")
        self.brokers = brokers  # Dictionary of broker instances keyed by brokerage name
        self.event_bus = None
        self._is_running = False

    def _get_broker(self, brokerage: str):
        """Retrieve the broker instance for the specified brokerage."""
        if brokerage not in self.brokers:
            raise ValueError(f"Brokerage {brokerage} not found")
        return self.brokers[brokerage]

    async def start(self) -> None:
        """Start the broker service"""
        self.is_running = True
        self._start_time = dt.datetime.utcnow().timestamp()

    async def stop(self) -> None:
        """Stop the broker service"""
        self.is_running = False

    def health_check(self) -> dict[str, any]:  # type: ignore
        """Perform health check on the broker service and all managed brokers"""
        broker_statuses = {}
        all_brokers_connected = True

        for brokerage_name, broker in self.brokers.items():
            try:
                # Check if broker has health check method
                if hasattr(broker, 'health_check'):
                    broker_status = broker.health_check()
                else:
                    # Basic connectivity check
                    broker_status = {
                        "connected": broker is not None,
                        "status": "healthy" if broker is not None else "disconnected"
                    }

                broker_statuses[brokerage_name] = broker_status
                if not broker_status.get("connected", False):
                    all_brokers_connected = False

            except Exception as e:
                broker_statuses[brokerage_name] = {
                    "connected": False,
                    "status": "error",
                    "error": str(e)
                }
                all_brokers_connected = False

        return {
            "status": "healthy" if self.is_running and all_brokers_connected else "degraded",
            "brokers": broker_statuses,
            "event_bus_connected": self.event_bus is not None,
            "uptime_seconds": dt.datetime.utcnow().timestamp() - (self._start_time or 0)
        }

    def get_capabilities(self) -> list[str]:
        """Get list of service capabilities"""
        return [
            "order_placement",
            "account_management",
            "position_tracking",
            "order_status_monitoring",
            "real_time_updates"
        ]

    def set_event_bus(self, event_bus: EventBus) -> None:
        """Set the event bus for publishing broker events"""
        self.event_bus = event_bus

    async def place_order(self, symbol: str, side: OrderSide, quantity: float,
                         order_type: str, time_in_force: str = "gtc",
                         extended_hours: bool = False, brokerage: str = "default") -> Order | None:
        """
        Place order through the specified broker

        Args:
            symbol: Symbol to trade
            side: BUY or SELL
            quantity: Quantity to trade
            order_type: Order type (market, limit, etc.)
            time_in_force: Time in force (gtc, gtd)
            extended_hours: Whether to allow extended hours trading
            brokerage: Name of the brokerage to use

        Returns:
            Order object if successful, None otherwise
        """
        broker = self._get_broker(brokerage)

        # Calculate limit price for market orders
        limit_price = None
        if order_type == "market":
            current_price = self._get_current_price(symbol, brokerage)
            if side == OrderSide.BUY:
                limit_price = mark_up(current_price)
            else:
                limit_price = mark_down(current_price)

        # Place order through broker
        try:
            if side == OrderSide.BUY:
                result = broker.buy(symbol, quantity, time_in_force, extended_hours)
            else:
                result = broker.sell(symbol, quantity, time_in_force, extended_hours)

            # Publish order placed event
            if result and self.event_bus:
                event_data = {
                    "order_id": result.order_id if hasattr(result, 'order_id') else "unknown",
                    "algorithm_name": "",  # Will be set by algorithm
                    "symbol": symbol,
                    "side": side.value,
                    "quantity": quantity,
                    "brokerage": brokerage,
                    "timestamp": dt.datetime.utcnow()
                }
                self.event_bus.publish('order_placed', event_data)

            return result

        except Exception as e:
            # Log error and return None
            print(f"Order placement failed: {e}")
            return None

    def _get_current_price(self, symbol: str, brokerage: str) -> float:
        """
        Get current price for a symbol from the specified broker

        Args:
            symbol: Symbol to get price for
            brokerage: Name of the brokerage to use

        Returns:
            Current price as float
        """
        broker = self._get_broker(brokerage)
        try:
            if hasattr(broker, 'get_current_price'):
                return broker.get_current_price(symbol)
            elif hasattr(broker, 'fetch_price'):
                return broker.fetch_price(symbol)
            else:
                return 100.0  # Placeholder value
        except Exception:
            return 100.0

    async def get_account_info(self, brokerage: str = "default") -> Account:
        """
        Get current account information from the specified broker

        Args:
            brokerage: Name of the brokerage to use

        Returns:
            Account object with current account data
        """
        broker = self._get_broker(brokerage)
        return broker.fetch_account()

    async def get_positions(self, brokerage: str = "default") -> list[Position]:
        """
        Get current positions from the specified broker

        Args:
            brokerage: Name of the brokerage to use

        Returns:
            List of Position objects for all current positions
        """
        broker = self._get_broker(brokerage)
        try:
            positions = []
            if hasattr(broker, 'get_positions'):
                broker_positions = broker.get_positions()
                if hasattr(broker_positions, 'stock'):
                    positions.extend(broker_positions.stock)
                if hasattr(broker_positions, 'crypto'):
                    positions.extend(broker_positions.crypto)
                if hasattr(broker_positions, 'option'):
                    positions.extend(broker_positions.option)
            elif hasattr(broker, 'positions'):
                broker_positions = broker.positions
                if hasattr(broker_positions, 'stock'):
                    positions.extend(broker_positions.stock)
                if hasattr(broker_positions, 'crypto'):
                    positions.extend(broker_positions.crypto)
                if hasattr(broker_positions, 'option'):
                    positions.extend(broker_positions.option)
            return positions
        except Exception as e:
            print(f"Failed to get positions: {e}")
            return []

    async def cancel_order(self, order_id: str, brokerage: str = "default") -> bool:
        """
        Cancel an existing order through the specified broker

        Args:
            order_id: ID of order to cancel
            brokerage: Name of the brokerage to use

        Returns:
            True if successful, False otherwise
        """
        broker = self._get_broker(brokerage)
        try:
            if hasattr(broker, 'cancel_order'):
                result = broker.cancel_order(order_id)
                if result and self.event_bus:
                    event_data = {
                        "order_id": order_id,
                        "brokerage": brokerage,
                        "timestamp": dt.datetime.utcnow()
                    }
                    self.event_bus.publish('order_cancelled', event_data)
                return result
            else:
                return False
        except Exception as e:
            print(f"Order cancellation failed: {e}")
            return False

    async def get_order_status(self, order_id: str, brokerage: str = "default") -> dict | None:
        """
        Get status of a specific order from the specified broker

        Args:
            order_id: ID of order to check
            brokerage: Name of the brokerage to use

        Returns:
            Order status information as dict, None if not found
        """
        broker = self._get_broker(brokerage)

        try:
            if hasattr(broker, 'get_order_status'):
                return broker.get_order_status(order_id)
            else:
                return None

        except Exception as e:
            print(f"Failed to get order status: {e}")
            return None

    def monitor_orders(self) -> None:
        """
        Start monitoring orders for fills and updates
        This would typically run in a background task
        """
        # This would be implemented as a background monitoring task
        # that checks for order fills and publishes events
        pass
