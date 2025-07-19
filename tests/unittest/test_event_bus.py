"""
Unit tests for EventBus functionality.
"""

import asyncio
import pytest
import datetime as dt
from unittest.mock import Mock

from harvest.events import EventBus, EventTypes
from harvest.events.events import (
    PriceUpdateEvent,
    OrderPlacedEvent,
    LogEvent,
    HealthStatus,
    LogLevel,
    ComponentType,
    DataType
)
from harvest.definitions import OrderSide


class TestEventBus:
    """Test cases for EventBus functionality."""

    def test_event_bus_creation(self):
        """Test EventBus can be created."""
        event_bus = EventBus()
        assert event_bus._event_handlers == {}
        assert event_bus.get_subscription_count() == 0

    def test_subscribe_and_publish(self):
        """Test basic subscribe and publish functionality."""
        event_bus = EventBus()
        received_events = []

        def handler(data):
            received_events.append(data)

        # Subscribe
        sub_id = event_bus.subscribe("test_event", handler)
        assert isinstance(sub_id, str)
        assert event_bus.get_subscription_count() == 1

        # Publish
        test_data = {"message": "test"}
        event_bus.publish("test_event", test_data)

        # Verify
        assert len(received_events) == 1
        assert received_events[0] == test_data

    def test_unsubscribe(self):
        """Test unsubscribe functionality."""
        event_bus = EventBus()
        received_events = []

        def handler(data):
            received_events.append(data)

        # Subscribe and publish
        sub_id = event_bus.subscribe("test_event", handler)
        event_bus.publish("test_event", {"message": "first"})

        # Unsubscribe
        event_bus.unsubscribe(sub_id)
        assert event_bus.get_subscription_count() == 0

        # Publish again
        event_bus.publish("test_event", {"message": "second"})

        # Should only have first event
        assert len(received_events) == 1
        assert received_events[0]["message"] == "first"

    def test_multiple_subscribers(self):
        """Test multiple subscribers to same event."""
        event_bus = EventBus()
        received_events_1 = []
        received_events_2 = []

        def handler_1(data):
            received_events_1.append(data)

        def handler_2(data):
            received_events_2.append(data)

        # Subscribe multiple handlers
        event_bus.subscribe("test_event", handler_1)
        event_bus.subscribe("test_event", handler_2)

        # Publish
        test_data = {"message": "broadcast"}
        event_bus.publish("test_event", test_data)

        # Both should receive
        assert len(received_events_1) == 1
        assert len(received_events_2) == 1
        assert received_events_1[0] == test_data
        assert received_events_2[0] == test_data

    def test_event_filtering(self):
        """Test event filtering functionality."""
        event_bus = EventBus()
        received_events = []

        def handler(data):
            received_events.append(data)

        # Subscribe with filter
        filters = {"symbol": "AAPL"}
        event_bus.subscribe("price_update", handler, filters)

        # Publish matching event
        event_bus.publish("price_update", {"symbol": "AAPL", "price": 150.0})

        # Publish non-matching event
        event_bus.publish("price_update", {"symbol": "GOOGL", "price": 2500.0})

        # Should only receive matching event
        assert len(received_events) == 1
        assert received_events[0]["symbol"] == "AAPL"

    async def test_async_publish(self):
        """Test asynchronous event publishing."""
        event_bus = EventBus()
        received_events = []

        async def async_handler(data):
            await asyncio.sleep(0.01)  # Simulate async work
            received_events.append(data)

        # Subscribe async handler
        event_bus.subscribe("async_event", async_handler)

        # Publish async
        await event_bus.publish_async("async_event", {"message": "async"})

        # Verify
        assert len(received_events) == 1
        assert received_events[0]["message"] == "async"

    def test_clear_all_subscriptions(self):
        """Test clearing all subscriptions."""
        event_bus = EventBus()

        def handler(data):
            pass

        # Add multiple subscriptions
        event_bus.subscribe("event1", handler)
        event_bus.subscribe("event2", handler)

        assert event_bus.get_subscription_count() == 2

        # Clear all
        event_bus.clear_all_subscriptions()
        assert event_bus.get_subscription_count() == 0

    def test_event_types_enum(self):
        """Test EventTypes enum functionality."""
        # Test that EventTypes values are strings
        assert EventTypes.PRICE_UPDATE == "price_update"
        assert EventTypes.ORDER_PLACED == "order_placed"
        assert EventTypes.LOG == "log"

        # Test that we can iterate over event types
        event_types = list(EventTypes)
        assert len(event_types) > 0
        assert EventTypes.PRICE_UPDATE in event_types


class TestEvents:
    """Test cases for event classes."""

    def test_price_update_event(self):
        """Test PriceUpdateEvent creation."""
        event = PriceUpdateEvent(
            symbol="AAPL",
            price_data=Mock(),
            timestamp=dt.datetime.now()
        )

        assert event.symbol == "AAPL"
        assert event.price_data is not None
        assert isinstance(event.timestamp, dt.datetime)

    def test_order_placed_event(self):
        """Test OrderPlacedEvent creation."""
        event = OrderPlacedEvent(
            order_id="123",
            algorithm_name="test_algo",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
            order_type="market",
            timestamp=dt.datetime.now()
        )

        assert event.order_id == "123"
        assert event.algorithm_name == "test_algo"
        assert event.symbol == "AAPL"
        assert event.quantity == 100.0
        assert event.side == OrderSide.BUY

    def test_log_event_with_enums(self):
        """Test LogEvent creation with enum values."""
        event = LogEvent(
            level=LogLevel.INFO,
            message="Test message",
            component=ComponentType.ALGORITHM,
            timestamp=dt.datetime.now()
        )

        assert event.level == LogLevel.INFO
        assert event.message == "Test message"
        assert event.component == ComponentType.ALGORITHM
        assert isinstance(event.timestamp, dt.datetime)

    def test_health_status_enum(self):
        """Test HealthStatus enum values."""
        assert HealthStatus.HEALTHY == "healthy"
        assert HealthStatus.DEGRADED == "degraded"
        assert HealthStatus.UNHEALTHY == "unhealthy"
        assert HealthStatus.UNKNOWN == "unknown"
        assert HealthStatus.ERROR == "error"

    def test_log_level_enum(self):
        """Test LogLevel enum values."""
        assert LogLevel.DEBUG == "DEBUG"
        assert LogLevel.INFO == "INFO"
        assert LogLevel.WARNING == "WARNING"
        assert LogLevel.ERROR == "ERROR"
        assert LogLevel.CRITICAL == "CRITICAL"

    def test_component_type_enum(self):
        """Test ComponentType enum values."""
        assert ComponentType.ALGORITHM == "algorithm"
        assert ComponentType.BROKER == "broker"
        assert ComponentType.SERVICE == "service"
        assert ComponentType.SYSTEM == "system"
        assert ComponentType.MAIN == "main"

    def test_data_type_enum(self):
        """Test DataType enum values."""
        assert DataType.CANDLE == "candle"
        assert DataType.QUOTE == "quote"
        assert DataType.TRADE == "trade"
        assert DataType.ORDERBOOK == "orderbook"
        assert DataType.NEWS == "news"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
