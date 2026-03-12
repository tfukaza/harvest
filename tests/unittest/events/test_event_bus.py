"""Sanity tests for EventBus functionality and event payloads."""

from __future__ import annotations

import asyncio
import datetime as dt
from unittest.mock import Mock

import pytest

from harvest.definitions import OrderSide
from harvest.enum import Interval
from harvest.events import EventBus, EventTypes
from harvest.events.events import (
    ComponentType,
    DataType,
    HealthStatus,
    LogEvent,
    LogLevel,
    OrderPlacedEvent,
    PriceUpdateEvent,
    ResourceUpdateEvent,
)


class TestEventBus:
    """Test cases for EventBus functionality."""

    def test_event_bus_creation(self) -> None:
        event_bus = EventBus()
        assert event_bus._event_handlers == {}
        assert event_bus.get_subscription_count() == 0

    def test_subscribe_and_publish(self) -> None:
        event_bus = EventBus()
        received_events = []

        def handler(data):
            received_events.append(data)

        sub_id = event_bus.subscribe("test_event", handler)
        assert isinstance(sub_id, str)
        assert event_bus.get_subscription_count() == 1

        test_data = {"message": "test"}
        event_bus.publish("test_event", test_data)

        assert len(received_events) == 1
        assert received_events[0] == test_data

    def test_unsubscribe(self) -> None:
        event_bus = EventBus()
        received_events = []

        def handler(data):
            received_events.append(data)

        sub_id = event_bus.subscribe("test_event", handler)
        event_bus.publish("test_event", {"message": "first"})

        event_bus.unsubscribe(sub_id)
        assert event_bus.get_subscription_count() == 0

        event_bus.publish("test_event", {"message": "second"})

        assert len(received_events) == 1
        assert received_events[0]["message"] == "first"

    def test_event_filtering(self) -> None:
        event_bus = EventBus()
        received_events = []

        def handler(data):
            received_events.append(data)

        event_bus.subscribe("price_update", handler, {"symbol": "AAPL"})

        event_bus.publish("price_update", {"symbol": "AAPL", "price": 150.0})
        event_bus.publish("price_update", {"symbol": "GOOGL", "price": 2500.0})

        assert len(received_events) == 1
        assert received_events[0]["symbol"] == "AAPL"

    def test_async_publish(self) -> None:
        event_bus = EventBus()
        received_events = []

        async def async_handler(data):
            await asyncio.sleep(0.01)
            received_events.append(data)

        event_bus.subscribe("async_event", async_handler)
        asyncio.run(event_bus.publish_async("async_event", {"message": "async"}))

        assert len(received_events) == 1
        assert received_events[0]["message"] == "async"

    def test_event_types_enum(self) -> None:
        assert EventTypes.PRICE_UPDATE == "price_update"
        assert EventTypes.RESOURCE_UPDATE == "resource_update"
        assert EventTypes.ORDER_PLACED == "order_placed"
        assert EventTypes.LOG == "log"
        assert EventTypes.PRICE_UPDATE in list(EventTypes)


class TestEvents:
    """Test cases for event classes."""

    def test_price_update_event(self) -> None:
        event = PriceUpdateEvent(
            symbol="AAPL",
            price_data=Mock(),
            timestamp=dt.datetime.now(dt.UTC),
            interval=Interval.MIN_1,
            broker_id="mock-broker",
            exchange="TEST",
        )

        assert event.symbol == "AAPL"
        assert event.price_data is not None
        assert isinstance(event.timestamp, dt.datetime)

    def test_resource_update_event(self) -> None:
        event = ResourceUpdateEvent(
            resource_id="market_data",
            payload={"symbol": "AAPL"},
            timestamp=dt.datetime.now(dt.UTC),
            capability="market_data_distribution",
        )

        assert event.resource_id == "market_data"
        assert event.payload["symbol"] == "AAPL"
        assert event.capability == "market_data_distribution"

    def test_order_placed_event(self) -> None:
        event = OrderPlacedEvent(
            order_id="123",
            algorithm_name="test_algo",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
            order_type="market",
            timestamp=dt.datetime.now(),
        )

        assert event.order_id == "123"
        assert event.algorithm_name == "test_algo"
        assert event.symbol == "AAPL"
        assert event.quantity == 100.0
        assert event.side == OrderSide.BUY

    def test_log_event_with_enums(self) -> None:
        event = LogEvent(
            level=LogLevel.INFO,
            message="Test message",
            component=ComponentType.ALGORITHM,
            timestamp=dt.datetime.now(),
        )

        assert event.level == LogLevel.INFO
        assert event.message == "Test message"
        assert event.component == ComponentType.ALGORITHM
        assert isinstance(event.timestamp, dt.datetime)

    def test_health_status_enum(self) -> None:
        assert HealthStatus.HEALTHY == "healthy"
        assert HealthStatus.DEGRADED == "degraded"
        assert HealthStatus.UNHEALTHY == "unhealthy"
        assert HealthStatus.UNKNOWN == "unknown"
        assert HealthStatus.ERROR == "error"

    def test_data_type_enum(self) -> None:
        assert DataType.CANDLE == "candle"
        assert DataType.QUOTE == "quote"
        assert DataType.TRADE == "trade"
        assert DataType.ORDERBOOK == "orderbook"
        assert DataType.NEWS == "news"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
