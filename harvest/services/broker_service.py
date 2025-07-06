import datetime as dt
from typing import TYPE_CHECKING

from .service_interface import Service
from ..events.event_bus import EventBus
from ..definitions import Order, Account, Position, OrderSide
from ..util.helper import mark_up, mark_down

if TYPE_CHECKING:
    from ..events.events import OrderPlacedEvent


class BrokerService(Service):
    """
    Service for managing broker operations including order placement and account management.
    Acts as an interface between algorithms and the underlying broker implementation.
    """

    def __init__(self, broker_instance):
        super().__init__("broker")
        self.broker = broker_instance
        self.event_bus = None
        self._is_running = False

    async def start(self) -> None:
        """Start the broker service"""
        self.is_running = True
        self._start_time = dt.datetime.utcnow().timestamp()

    async def stop(self) -> None:
        """Stop the broker service"""
        self.is_running = False

    def health_check(self) -> dict[str, any]:  # type: ignore
        """Perform health check on the broker service"""
        return {
            "status": "healthy" if self.is_running else "stopped",
            "broker_connected": self.broker is not None,
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
                         extended_hours: bool = False) -> Order | None:
        """
        Place order through broker
        
        Args:
            symbol: Symbol to trade
            side: BUY or SELL
            quantity: Quantity to trade
            order_type: Order type (market, limit, etc.)
            time_in_force: Time in force (gtc, gtd)
            extended_hours: Whether to allow extended hours trading
            
        Returns:
            Order object if successful, None otherwise
        """
        if not self.broker:
            raise Exception("No broker instance available")

        # Calculate limit price for market orders
        limit_price = None
        if order_type == "market":
            current_price = self._get_current_price(symbol)
            if side == OrderSide.BUY:
                limit_price = mark_up(current_price)
            else:
                limit_price = mark_down(current_price)

        # Place order through broker
        try:
            if side == OrderSide.BUY:
                result = self.broker.buy(symbol, quantity, time_in_force, extended_hours)
            else:
                result = self.broker.sell(symbol, quantity, time_in_force, extended_hours)

            # Publish order placed event
            if result and self.event_bus:
                event_data = {
                    "order_id": result.order_id if hasattr(result, 'order_id') else "unknown",
                    "algorithm_name": "",  # Will be set by algorithm
                    "symbol": symbol,
                    "side": side.value,
                    "quantity": quantity,
                    "timestamp": dt.datetime.utcnow()
                }
                self.event_bus.publish('order_placed', event_data)

            return result

        except Exception as e:
            # Log error and return None
            print(f"Order placement failed: {e}")
            return None

    def _get_current_price(self, symbol: str) -> float:
        """
        Get current price for a symbol
        
        Args:
            symbol: Symbol to get price for
            
        Returns:
            Current price as float
        """
        if not self.broker:
            raise Exception("No broker instance available")
        
        # This would typically call broker's price fetching method
        # For now, return a placeholder value
        try:
            # Attempt to get price from broker - method name may vary
            if hasattr(self.broker, 'get_current_price'):
                return self.broker.get_current_price(symbol)
            elif hasattr(self.broker, 'fetch_price'):
                return self.broker.fetch_price(symbol)
            else:
                # Fallback to a default price for now
                return 100.0
        except Exception:
            return 100.0

    async def get_account_info(self) -> Account:
        """
        Get current account information
        
        Returns:
            Account object with current account data
        """
        if not self.broker:
            raise Exception("No broker instance available")
        
        return self.broker.fetch_account()

    async def get_positions(self) -> list[Position]:
        """
        Get current positions
        
        Returns:
            List of Position objects for all current positions
        """
        if not self.broker:
            raise Exception("No broker instance available")
        
        # Combine stock, crypto, and option positions
        try:
            positions = []
            
            # Get positions from broker - method name may vary by broker
            if hasattr(self.broker, 'get_positions'):
                broker_positions = self.broker.get_positions()
                if hasattr(broker_positions, 'stock'):
                    positions.extend(broker_positions.stock)
                if hasattr(broker_positions, 'crypto'):
                    positions.extend(broker_positions.crypto)
                if hasattr(broker_positions, 'option'):
                    positions.extend(broker_positions.option)
            elif hasattr(self.broker, 'positions'):
                broker_positions = self.broker.positions
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

    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an existing order
        
        Args:
            order_id: ID of order to cancel
            
        Returns:
            True if successful, False otherwise
        """
        if not self.broker:
            raise Exception("No broker instance available")
        
        try:
            if hasattr(self.broker, 'cancel_order'):
                result = self.broker.cancel_order(order_id)
                
                # Publish order cancelled event
                if result and self.event_bus:
                    event_data = {
                        "order_id": order_id,
                        "timestamp": dt.datetime.utcnow()
                    }
                    self.event_bus.publish('order_cancelled', event_data)
                
                return result
            else:
                return False
                
        except Exception as e:
            print(f"Order cancellation failed: {e}")
            return False

    async def get_order_status(self, order_id: str) -> dict | None:
        """
        Get status of a specific order
        
        Args:
            order_id: ID of order to check
            
        Returns:
            Order status information as dict, None if not found
        """
        if not self.broker:
            raise Exception("No broker instance available")
        
        try:
            if hasattr(self.broker, 'get_order_status'):
                return self.broker.get_order_status(order_id)
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
