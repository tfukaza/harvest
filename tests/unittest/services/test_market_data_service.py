"""Sanity tests for MarketDataService at the Resource boundary."""

from __future__ import annotations

import datetime as dt
from unittest.mock import Mock

import polars as pl

from harvest.definitions import TickerCandleList
from harvest.resource import Resource
from harvest.services.market_data_service import MarketDataService


def create_sample_price_data() -> TickerCandleList:
    """Create a minimal candle payload for market-data tests."""
    return TickerCandleList(
        pl.DataFrame(
            {
                "timestamp": [dt.datetime.now(dt.UTC)],
                "symbol": ["AAPL"],
                "interval": ["MIN_1"],
                "open": [100.0],
                "high": [101.0],
                "low": [99.5],
                "close": [100.5],
                "volume": [1000.0],
            }
        )
    )


def test_market_data_service_is_a_resource() -> None:
    service = MarketDataService(Mock())

    assert isinstance(service, Resource)
    assert service.resource_id == "market_data"


def test_market_data_service_publishes_resource_update() -> None:
    service = MarketDataService(Mock())
    event_bus = Mock()
    central_storage = Mock()
    sample_price_data = create_sample_price_data()

    service.set_event_bus(event_bus)
    service.set_central_storage(central_storage)

    service.publish_price_update("AAPL", sample_price_data)

    central_storage.store_price_data.assert_called_once_with(sample_price_data)
    assert event_bus.publish.call_count == 2
    first_call = event_bus.publish.call_args_list[0]
    second_call = event_bus.publish.call_args_list[1]

    assert first_call.args[0] == "price_update"
    assert first_call.args[1]["symbol"] == "AAPL"
    assert second_call.args[0] == "resource_update"
    assert second_call.args[1]["resource_id"] == "market_data"
    assert second_call.args[1]["capability"] == "market_data_distribution"