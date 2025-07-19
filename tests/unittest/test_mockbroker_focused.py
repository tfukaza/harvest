"""
Final MockBroker Unit Tests - Focused on Granular Functionality

This test suite focuses on testing the granular aspects of MockBroker:
- Price history API correctness
- Timezone handling
- Order management
- Performance controls
- Time management

All tests use controlled time ranges to avoid performance issues.
"""

import datetime as dt
import time
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from harvest.broker.mock import MockBroker
from harvest.definitions import (
    AssetType,
    OrderSide,
    OrderStatus,
    OrderTimeInForce,
    Position,
    RuntimeData,
    TickerCandle,
)
from harvest.enum import Interval


class TestMockBrokerCore:
    """Test core MockBroker functionality."""

    def test_initialization_with_timezones(self):
        """Test MockBroker initialization and timezone handling."""
        # Test UTC timezone
        utc_time = dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
        broker = MockBroker(current_time=utc_time)

        assert broker.stats.broker_timezone == ZoneInfo("UTC")
        assert broker.stats.utc_timestamp == utc_time
        assert broker.current_time == utc_time

        # Test string time parsing
        broker2 = MockBroker(current_time="2023-01-01 12:00")
        expected_time = dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
        assert broker2.current_time == expected_time

    def test_dependency_injection(self):
        """Test dependency injection for testing control."""
        mock_time_provider = Mock(return_value=dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc))
        mock_sleep = Mock()

        broker = MockBroker(
            time_provider=mock_time_provider,
            sleep_function=mock_sleep
        )

        assert broker.time_provider == mock_time_provider
        assert broker.sleep_function == mock_sleep

    def test_exchange_and_intervals(self):
        """Test exchange name and supported intervals."""
        broker = MockBroker()

        assert broker.exchange == "MOCK"
        assert Interval.MIN_1 in broker.interval_list
        assert Interval.MIN_5 in broker.interval_list
        assert Interval.HR_1 in broker.interval_list
        assert Interval.DAY_1 in broker.interval_list


class TestMockBrokerPriceAPI:
    """Test price history API with controlled data ranges."""

    def test_fetch_price_history_api(self):
        """Test price history API with controlled time range."""
        broker = MockBroker(
            current_time=dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc),
            epoch=dt.datetime(2023, 1, 1, 11, 0, 0, tzinfo=dt.timezone.utc)
        )

        # Request 30 minutes of data
        start_time = dt.datetime(2023, 1, 1, 11, 30, tzinfo=dt.timezone.utc)
        end_time = dt.datetime(2023, 1, 1, 12, 0, tzinfo=dt.timezone.utc)

        frame = broker.fetch_price_history("AAPL", Interval.MIN_1, start_time, end_time)

        # Verify structure
        assert len(frame.df) == 30  # 30 minutes
        required_columns = ["timestamp", "open", "high", "low", "close", "volume"]
        for col in required_columns:
            assert col in frame.df.columns

        # Verify time range
        timestamps = frame.df.select("timestamp").to_series().to_list()
        assert all(start_time <= ts <= end_time for ts in timestamps)

    def test_different_intervals(self):
        """Test price history with different intervals."""
        broker = MockBroker(
            current_time=dt.datetime(2023, 1, 1, 6, 0, 0, tzinfo=dt.timezone.utc),
            epoch=dt.datetime(2023, 1, 1, 0, 0, 0, tzinfo=dt.timezone.utc)
        )

        start_time = dt.datetime(2023, 1, 1, 0, 0, 0, tzinfo=dt.timezone.utc)
        end_time = dt.datetime(2023, 1, 1, 6, 0, 0, tzinfo=dt.timezone.utc)

        # Test 1-minute interval
        frame_1min = broker.fetch_price_history("AAPL", Interval.MIN_1, start_time, end_time)
        assert len(frame_1min.df) == 360  # 6 hours * 60 minutes

        # Test 5-minute interval
        frame_5min = broker.fetch_price_history("AAPL", Interval.MIN_5, start_time, end_time)
        assert len(frame_5min.df) == 72  # 6 hours * 12 intervals per hour

    def test_set_custom_price_data(self):
        """Test setting custom price data."""
        broker = MockBroker()

        custom_candle = TickerCandle(
            timestamp=dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc),
            open=100.0,
            high=105.0,
            low=95.0,
            close=102.0,
            volume=1000,
            symbol="AAPL"
        )

        broker.set_price_data("AAPL", custom_candle)

        # Verify data was stored
        assert "AAPL" in broker.mock_price_history
        assert Interval.MIN_1 in broker.mock_price_history["AAPL"]
        df = broker.mock_price_history["AAPL"][Interval.MIN_1]
        assert len(df) == 1
        assert df.select("close").row(0)[0] == 102.0

    def test_data_size_limits(self):
        """Test data size limits for performance."""
        broker = MockBroker()

        # Test size limit enforcement
        with pytest.raises(ValueError, match="maximum is 1000000"):
            broker.generate_random_data("AAPL", dt.datetime(2023, 1, 1), 2000000)

        # Test successful generation within limits
        rng, df = broker.generate_random_data("AAPL", dt.datetime(2023, 1, 1), 100)
        assert len(df) == 100
        assert "timestamp" in df.columns
        assert "price" in df.columns


class TestMockBrokerOrders:
    """Test order management functionality."""

    def test_stock_order_lifecycle(self):
        """Test complete stock order lifecycle."""
        broker = MockBroker()

        # Create order
        order = broker.order_stock_limit(
            OrderSide.BUY, "AAPL", 100.0, 150.0, OrderTimeInForce.GTC
        )

        assert order.order_type == AssetType.STOCK
        assert order.symbol == "AAPL"
        assert order.quantity == 100.0
        assert order.side == OrderSide.BUY
        assert order.status == OrderStatus.OPEN
        assert order.order_id in broker.orders

        # Cancel order
        broker.cancel_stock_order(order.order_id)
        assert order.order_id not in broker.orders

    def test_crypto_order_creation(self):
        """Test crypto order creation."""
        broker = MockBroker()

        order = broker.order_crypto_limit("buy", "@BTC", 0.5, 50000.0, "gtc")

        assert order.order_type == AssetType.CRYPTO
        assert order.symbol == "@BTC"
        assert order.quantity == 0.5
        assert order.side == OrderSide.BUY
        assert order.status == OrderStatus.OPEN

    def test_option_order_creation(self):
        """Test option order creation."""
        broker = MockBroker()

        exp_date = dt.datetime(2023, 12, 15, tzinfo=dt.timezone.utc)
        order = broker.order_option_limit(
            "buy", "AAPL", 1.0, 5.0, "call", exp_date, 150.0, "gtc"
        )

        assert order.order_type == AssetType.OPTION
        assert order.quantity == 1.0
        assert order.side == OrderSide.BUY
        assert order.base_symbol == "AAPL"

    def test_order_status_retrieval(self):
        """Test order status retrieval."""
        broker = MockBroker()

        # Test existing order
        order = broker.order_stock_limit(OrderSide.BUY, "AAPL", 100.0, 150.0)
        fetched_order = broker.fetch_stock_order_status(order.order_id)
        assert fetched_order.order_id == order.order_id

        # Test non-existing order (should return mock filled order)
        mock_order = broker.fetch_stock_order_status("fake_id")
        assert mock_order.status == OrderStatus.FILLED


class TestMockBrokerPositions:
    """Test position management."""

    def test_position_filtering(self):
        """Test position filtering by asset type."""
        broker = MockBroker()

        # Add different types of positions
        broker.positions["AAPL"] = Position(symbol="AAPL", quantity=100.0, avg_price=150.0)
        broker.positions["AAPL:20231215:150:C"] = Position(
            symbol="AAPL:20231215:150:C", quantity=1.0, avg_price=5.0
        )
        broker.positions["@BTC"] = Position(symbol="@BTC", quantity=0.5, avg_price=50000.0)

        # Test stock positions
        stock_positions = broker.fetch_stock_positions()
        assert len(stock_positions.positions) == 3  # All positions for stock

        # Test option positions
        option_positions = broker.fetch_option_positions()
        assert len(option_positions.positions) == 1
        assert "AAPL:20231215:150:C" in option_positions.positions

        # Test crypto positions
        crypto_positions = broker.fetch_crypto_positions()
        assert len(crypto_positions.positions) == 1
        assert "@BTC" in crypto_positions.positions

    def test_account_information(self):
        """Test account information retrieval."""
        broker = MockBroker()

        # Add a position
        broker.positions["AAPL"] = Position(symbol="AAPL", quantity=100.0, avg_price=150.0)

        account = broker.fetch_account()
        assert account.account_name == "MockAccount"
        assert account.cash == 10000.0
        assert account.buying_power == 20000.0
        assert account.multiplier == 1.0
        assert len(account.positions.positions) == 1


class TestMockBrokerTimeControl:
    """Test time management and control."""

    def test_time_advancement(self):
        """Test time advancement functionality."""
        broker = MockBroker(
            current_time=dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
        )

        initial_time = broker.get_current_time()
        broker.advance_time()
        advanced_time = broker.get_current_time()

        # Should advance by poll_interval (default MIN_1 = 1 minute)
        expected_advance = dt.timedelta(minutes=1)
        assert advanced_time - initial_time == expected_advance

    def test_polling_control(self):
        """Test polling control mechanisms."""
        broker = MockBroker(realistic_simulation=False)

        # Test continue/stop polling
        assert broker.continue_polling() is True
        broker.stop_polling()
        assert broker.continue_polling() is False

        # Test max ticks control
        broker = MockBroker(realistic_simulation=False)
        broker.set_max_ticks(3)

        start_time = time.time()
        broker.start({Interval.MIN_1: ["AAPL"]})
        elapsed = time.time() - start_time

        # Should complete quickly and stop after 3 ticks
        assert elapsed < 0.1
        assert broker.get_tick_count() == 3


class TestMockBrokerPerformance:
    """Test performance controls and optimizations."""

    def test_fast_simulation_mode(self):
        """Test fast simulation mode (no sleep)."""
        mock_sleep = Mock()
        broker = MockBroker(
            realistic_simulation=False,
            sleep_function=mock_sleep
        )
        broker.set_max_ticks(2)

        start_time = time.time()
        broker.start({Interval.MIN_1: ["AAPL"]})
        elapsed = time.time() - start_time

        # Should be very fast (no sleep)
        assert elapsed < 0.1
        # Sleep should not be called
        mock_sleep.assert_not_called()

    def test_realistic_simulation_with_mock_sleep(self):
        """Test realistic simulation with controlled sleep."""
        mock_sleep = Mock()
        broker = MockBroker(
            realistic_simulation=True,
            sleep_function=mock_sleep
        )
        broker.set_max_ticks(2)

        broker.start({Interval.MIN_1: ["AAPL"]})

        # Sleep should be called twice (for 2 ticks)
        assert mock_sleep.call_count == 2
        # Should be called with 60 seconds (1 minute interval)
        mock_sleep.assert_called_with(60)

    def test_data_management(self):
        """Test data management for memory efficiency."""
        broker = MockBroker()

        # Add some mock data
        broker.mock_price_history["AAPL"] = {
            Interval.MIN_1: pl.DataFrame({
                "timestamp": [dt.datetime(2023, 1, 1)] * 100,
                "price": [100.0] * 100
            })
        }
        broker.rng["AAPL"] = Mock()

        # Test clearing data
        broker.clear_mock_data()
        assert len(broker.mock_price_history) == 0
        assert len(broker.rng) == 0

        # Test state reset
        broker.orders["test"] = Mock()
        broker.positions["AAPL"] = Mock()
        broker.reset_state()
        assert len(broker.orders) == 0
        assert len(broker.positions) == 0


class TestMockBrokerMarketData:
    """Test market data functionality."""

    def test_market_hours(self):
        """Test market hours retrieval."""
        broker = MockBroker()

        test_date = dt.date(2023, 1, 1)
        market_hours = broker.fetch_market_hours(test_date)

        assert market_hours["is_open"] is True
        assert isinstance(market_hours["open_at"], dt.datetime)
        assert isinstance(market_hours["close_at"], dt.datetime)
        assert market_hours["open_at"].time() == dt.time(9, 30)
        assert market_hours["close_at"].time() == dt.time(16, 0)

    def test_symbol_support(self):
        """Test symbol support checking."""
        broker = MockBroker()

        # Test supported symbols
        assert broker.supports_symbol("AAPL") is True
        assert broker.supports_symbol("GOOGL") is True
        assert broker.supports_symbol("MSFT") is True

        # Test unsupported symbol
        assert broker.supports_symbol("UNKNOWN") is False

    def test_supported_intervals_tickers(self):
        """Test supported intervals and tickers mapping."""
        broker = MockBroker()

        supported = broker._get_supported_intervals_tickers()

        assert isinstance(supported, dict)
        assert Interval.MIN_1 in supported
        assert Interval.MIN_5 in supported
        assert Interval.HR_1 in supported
        assert Interval.DAY_1 in supported

        # All intervals should have the same ticker list
        for interval, tickers in supported.items():
            assert "AAPL" in tickers
            assert "GOOGL" in tickers
            assert "MSFT" in tickers

    def test_credentials_mock(self):
        """Test credential functionality (should be mocked)."""
        broker = MockBroker()

        # Should return empty dict for mock
        secret = broker.create_secret()
        assert isinstance(secret, dict)
        assert len(secret) == 0

        # Should not raise any exception
        broker.refresh_cred()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
