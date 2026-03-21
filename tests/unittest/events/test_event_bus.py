"""Sanity tests for typed EventBus behavior and event models."""

from __future__ import annotations

import asyncio

from harvest.events import (
    AccountUpdated,
    ComponentType,
    DataType,
    EventBus,
    HealthStatus,
    LogLevel,
    OrderPlaced,
    PriceUpdated,
    ResourceUpdated,
)


class TestEventBus:
    """Test cases for EventBus functionality."""

    def test_event_bus_creation(self) -> None:
        event_bus = EventBus()
        assert event_bus._bus is not None
        asyncio.run(event_bus.stop())

    def test_on_and_dispatch_sync(self) -> None:
        received_symbols: list[str] = []

        def handler(event: PriceUpdated) -> None:
            received_symbols.append(event.symbol)

        async def _run() -> None:
            event_bus = EventBus()
            event_bus.on(PriceUpdated, handler)
            await event_bus.dispatch_async(
                PriceUpdated(
                    source="test",
                    symbol="AAPL",
                    interval="1m",
                    broker_id="mock",
                    exchange="TEST",
                    price_data={"close": 150.0},
                )
            )
            await event_bus.stop()

        asyncio.run(_run())
        assert received_symbols == ["AAPL"]

    def test_dispatch_async_with_async_handler(self) -> None:
        event_bus = EventBus()
        received_order_ids: list[str] = []

        async def handler(event: OrderPlaced) -> None:
            await asyncio.sleep(0.01)
            received_order_ids.append(event.order_id)

        async def _run() -> None:
            event_bus.on(OrderPlaced, handler)
            await event_bus.dispatch_async(
                OrderPlaced(
                    source="test",
                    order_id="ord-1",
                    symbol="AAPL",
                    side="buy",
                    quantity=1.0,
                    order_type="market",
                )
            )
            await event_bus.stop()

        asyncio.run(_run())
        assert received_order_ids == ["ord-1"]


class TestEvents:
    """Test cases for event classes and enums."""

    def test_price_updated_event(self) -> None:
        event = PriceUpdated(
            source="broker",
            symbol="AAPL",
            interval="1m",
            broker_id="mock-broker",
            exchange="TEST",
            price_data={"close": 150.0},
        )

        assert event.symbol == "AAPL"
        assert event.price_data["close"] == 150.0

    def test_resource_updated_event(self) -> None:
        event = ResourceUpdated(
            source="service",
            resource_id="market_data",
            payload={"symbol": "AAPL"},
            capability="market_data_distribution",
        )

        assert event.resource_id == "market_data"
        assert event.payload["symbol"] == "AAPL"
        assert event.capability == "market_data_distribution"

    def test_order_placed_event(self) -> None:
        event = OrderPlaced(
            source="algo",
            order_id="123",
            algorithm_name="test_algo",
            symbol="AAPL",
            side="buy",
            quantity=100.0,
            order_type="market",
        )

        assert event.order_id == "123"
        assert event.algorithm_name == "test_algo"
        assert event.symbol == "AAPL"
        assert event.quantity == 100.0
        assert event.side == "buy"

    def test_account_updated_event(self) -> None:
        event = AccountUpdated(
            source="broker",
            algorithm_name="test_algo",
            equity=100000.0,
            buying_power=50000.0,
            cash=25000.0,
            asset_value=75000.0,
        )

        assert event.algorithm_name == "test_algo"
        assert event.equity == 100000.0

    def test_health_status_enum(self) -> None:
        assert HealthStatus.HEALTHY == "healthy"
        assert HealthStatus.DEGRADED == "degraded"
        assert HealthStatus.UNHEALTHY == "unhealthy"
        assert HealthStatus.UNKNOWN == "unknown"
        assert HealthStatus.ERROR == "error"

    def test_component_type_enum(self) -> None:
        assert ComponentType.ALGORITHM == "algorithm"
        assert ComponentType.BROKER == "broker"
        assert ComponentType.SERVICE == "service"

    def test_log_level_enum(self) -> None:
        assert LogLevel.INFO == "INFO"
        assert LogLevel.ERROR == "ERROR"

    def test_data_type_enum(self) -> None:
        assert DataType.CANDLE == "candle"
        assert DataType.QUOTE == "quote"
        assert DataType.TRADE == "trade"
        assert DataType.ORDERBOOK == "orderbook"
        assert DataType.NEWS == "news"
