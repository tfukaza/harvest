"""
Comprehensive unit tests for MockBroker class.

This module tests the granular functionality of MockBroker including:
- Price history API correctness
- Timezone handling
- Order management
- Performance controls
- Data generation
- Time management
"""

import datetime as dt
import time
import uuid
from unittest.mock import Mock, patch
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
from harvest.enum import Interval, IntervalUnit


class TestMockBrokerInitialization:
    """Test MockBroker initialization and configuration."""

    def test_default_initialization(self):
        """Test MockBroker with default parameters."""
        broker = MockBroker()

        assert broker.exchange == "MOCK"
        assert broker.realistic_simulation is True
        assert broker.stock_market_times is False
        assert broker._continue_polling is True
        assert broker._tick_count == 0
        assert broker._max_ticks is None
        assert isinstance(broker.stats, RuntimeData)
        assert broker.stats.broker_timezone == ZoneInfo("UTC")

    def test_custom_time_initialization(self):
        """Test MockBroker with custom time settings."""
        custom_time = dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
        epoch = dt.datetime(2022, 1, 1, tzinfo=dt.timezone.utc)

        broker = MockBroker(
            current_time=custom_time,
            epoch=epoch,
            realistic_simulation=False,
            stock_market_times=True
        )

        assert broker.current_time == custom_time
        assert broker.epoch == epoch
        assert broker.realistic_simulation is False
        assert broker.stock_market_times is True
        assert broker.stats.utc_timestamp == custom_time
        assert broker.stats.broker_timezone == ZoneInfo("UTC")

    def test_string_time_initialization(self):
        """Test MockBroker with string time parameter."""
        broker = MockBroker(current_time="2023-01-01 12:00")

        expected_time = dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
        assert broker.current_time == expected_time
        assert broker.stats.utc_timestamp == expected_time

    def test_timezone_handling(self):
        """Test proper timezone handling in initialization."""
        # Test UTC timezone
        utc_time = dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
        broker = MockBroker(current_time=utc_time)
        assert broker.stats.broker_timezone == ZoneInfo("UTC")

        # Test with different timezone
        est_time = dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=ZoneInfo("US/Eastern"))
        broker = MockBroker(current_time=est_time)
        assert isinstance(broker.stats.broker_timezone, ZoneInfo)

    def test_dependency_injection(self):
        """Test dependency injection for time provider and sleep function."""
        mock_time_provider = Mock(return_value=dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc))
        mock_sleep = Mock()

        broker = MockBroker(
            time_provider=mock_time_provider,
            sleep_function=mock_sleep
        )

        assert broker.time_provider == mock_time_provider
        assert broker.sleep_function == mock_sleep


class TestMockBrokerPriceHistory:
    """Test price history generation and API functionality."""

    def test_fetch_price_history_basic(self):
        """Test basic price history fetching."""
        broker = MockBroker(
            current_time=dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc),
            epoch=dt.datetime(2023, 1, 1, 0, 0, 0, tzinfo=dt.timezone.utc)
        )

        frame = broker.fetch_price_history(
            "AAPL",
            Interval.MIN_1,
            dt.datetime(2023, 1, 1, 10, 0, 0, tzinfo=dt.timezone.utc),
            dt.datetime(2023, 1, 1, 11, 0, 0, tzinfo=dt.timezone.utc)
        )

        assert len(frame.df) == 60  # 60 minutes
        assert "timestamp" in frame.df.columns
        assert "open" in frame.df.columns
        assert "high" in frame.df.columns
        assert "low" in frame.df.columns
        assert "close" in frame.df.columns
        assert "volume" in frame.df.columns

    def test_fetch_price_history_time_range(self):
        """Test price history with specific time ranges."""
        broker = MockBroker(
            current_time=dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
        )

        start_time = dt.datetime(2023, 1, 1, 10, 0, 0, tzinfo=dt.timezone.utc)
        end_time = dt.datetime(2023, 1, 1, 10, 30, 0, tzinfo=dt.timezone.utc)

        frame = broker.fetch_price_history("AAPL", Interval.MIN_1, start_time, end_time)

        # Verify time range
        timestamps = frame.df.select("timestamp").to_series().to_list()
        assert all(start_time <= ts <= end_time for ts in timestamps)

    def test_fetch_price_history_different_intervals(self):
        """Test price history with different intervals."""
        broker = MockBroker(
            current_time=dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
        )

        start_time = dt.datetime(2023, 1, 1, 0, 0, 0, tzinfo=dt.timezone.utc)
        end_time = dt.datetime(2023, 1, 1, 6, 0, 0, tzinfo=dt.timezone.utc)

        # Test 1-minute interval
        frame_1min = broker.fetch_price_history("AAPL", Interval.MIN_1, start_time, end_time)
        assert len(frame_1min.df) == 360  # 6 hours * 60 minutes

        # Test 5-minute interval
        frame_5min = broker.fetch_price_history("AAPL", Interval.MIN_5, start_time, end_time)
        assert len(frame_5min.df) == 72  # 6 hours * 12 intervals per hour

        # Test 1-hour interval
        frame_1hr = broker.fetch_price_history("AAPL", Interval.HR_1, start_time, end_time)
        assert len(frame_1hr.df) == 6  # 6 hours

    def test_fetch_latest_price(self):
        """Test fetching the latest price."""
        broker = MockBroker(
            current_time=dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc),
            epoch=dt.datetime(2023, 1, 1, 11, 0, 0, tzinfo=dt.timezone.utc)  # Only 1 hour of data
        )

        latest_candle = broker.fetch_latest_price("AAPL", Interval.MIN_1)

        assert hasattr(latest_candle, 'open')
        assert hasattr(latest_candle, 'high')
        assert hasattr(latest_candle, 'low')
        assert hasattr(latest_candle, 'close')
        assert hasattr(latest_candle, 'volume')
        assert hasattr(latest_candle, 'timestamp')

    def test_set_price_data(self):
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

        assert "AAPL" in broker.mock_price_history
        assert Interval.MIN_1 in broker.mock_price_history["AAPL"]
        df = broker.mock_price_history["AAPL"][Interval.MIN_1]
        assert len(df) == 1
        assert df.select("close").row(0)[0] == 102.0

    def test_data_size_limits(self):
        """Test data size limits for performance."""
        broker = MockBroker()

        # Test generate_random_data size limit
        with pytest.raises(ValueError, match="maximum is 1000000"):
            broker.generate_random_data("AAPL", dt.datetime(2023, 1, 1), 2000000)

        # Test successful generation within limits
        rng, df = broker.generate_random_data("AAPL", dt.datetime(2023, 1, 1), 100)
        assert len(df) == 100
        assert "timestamp" in df.columns
        assert "price" in df.columns


class TestMockBrokerOrders:
    """Test order management functionality."""

    def test_stock_order_creation(self):
        """Test creating stock orders."""
        broker = MockBroker()

        order = broker.order_stock_limit(
            OrderSide.BUY,
            "AAPL",
            100.0,
            150.0,
            OrderTimeInForce.GTC
        )

        assert order.order_type == AssetType.STOCK
        assert order.symbol == "AAPL"
        assert order.quantity == 100.0
        assert order.side == OrderSide.BUY
        assert order.status == OrderStatus.OPEN
        assert order.order_id in broker.orders

    def test_crypto_order_creation(self):
        """Test creating crypto orders."""
        broker = MockBroker()

        order = broker.order_crypto_limit(
            "buy",
            "@BTC",
            0.5,
            50000.0,
            "gtc"
        )

        assert order.order_type == AssetType.CRYPTO
        assert order.symbol == "@BTC"
        assert order.quantity == 0.5
        assert order.side == OrderSide.BUY
        assert order.status == OrderStatus.OPEN

    def test_option_order_creation(self):
        """Test creating option orders."""
        broker = MockBroker()

        exp_date = dt.datetime(2023, 12, 15, tzinfo=dt.timezone.utc)
        order = broker.order_option_limit(
            "buy",  # Changed from "call" to "buy"
            "AAPL",
            1.0,
            5.0,
            "call",
            exp_date,
            150.0,
            "gtc"
        )

        assert order.order_type == AssetType.OPTION
        assert order.quantity == 1.0
        assert order.side == OrderSide.BUY
        assert order.base_symbol == "AAPL"

    def test_order_fulfillment(self):
        """Test order fulfillment functionality."""
        broker = MockBroker(
            current_time=dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc),
            epoch=dt.datetime(2023, 1, 1, 11, 0, 0, tzinfo=dt.timezone.utc)  # Only 1 hour of data
        )

        # Create an order
        order = broker.order_stock_limit(
            OrderSide.BUY,
            "AAPL",
            100.0,
            150.0
        )

        # Fulfill the order
        broker.fulfill_order(order)

        assert order.status == OrderStatus.FILLED
        assert order.filled_time is not None
        assert order.filled_price is not None
        assert order.filled_quantity == 100.0
        assert "AAPL" in broker.positions
        assert order.order_id not in broker.orders

    def test_order_cancellation(self):
        """Test order cancellation."""
        broker = MockBroker()

        # Create and cancel stock order
        order = broker.order_stock_limit(OrderSide.BUY, "AAPL", 100.0, 150.0)
        broker.cancel_stock_order(order.order_id)
        assert order.order_id not in broker.orders

        # Create and cancel crypto order
        order = broker.order_crypto_limit("buy", "@BTC", 0.5, 50000.0)
        broker.cancel_crypto_order(order.order_id)
        assert order.order_id not in broker.orders

    def test_order_status_fetching(self):
        """Test fetching order status."""
        broker = MockBroker()

        # Test existing order
        order = broker.order_stock_limit(OrderSide.BUY, "AAPL", 100.0, 150.0)
        fetched_order = broker.fetch_stock_order_status(order.order_id)
        assert fetched_order.order_id == order.order_id

        # Test non-existing order (should return mock filled order)
        fake_id = str(uuid.uuid4())
        mock_order = broker.fetch_stock_order_status(fake_id)
        assert mock_order.status == OrderStatus.FILLED


class TestMockBrokerPositions:
    """Test position management functionality."""

    def test_fetch_stock_positions(self):
        """Test fetching stock positions."""
        broker = MockBroker()

        # Add some positions
        broker.positions["AAPL"] = Position(symbol="AAPL", quantity=100.0, avg_price=150.0)
        broker.positions["GOOGL"] = Position(symbol="GOOGL", quantity=50.0, avg_price=2500.0)

        positions = broker.fetch_stock_positions()
        assert len(positions.positions) == 2
        assert "AAPL" in positions.positions
        assert "GOOGL" in positions.positions

    def test_fetch_option_positions(self):
        """Test fetching option positions."""
        broker = MockBroker()

        # Add stock and option positions
        broker.positions["AAPL"] = Position(symbol="AAPL", quantity=100.0, avg_price=150.0)
        broker.positions["AAPL:20231215:150:C"] = Position(
            symbol="AAPL:20231215:150:C", quantity=1.0, avg_price=5.0
        )

        option_positions = broker.fetch_option_positions()
        assert len(option_positions.positions) == 1
        assert "AAPL:20231215:150:C" in option_positions.positions

    def test_fetch_crypto_positions(self):
        """Test fetching crypto positions."""
        broker = MockBroker()

        # Add stock and crypto positions
        broker.positions["AAPL"] = Position(symbol="AAPL", quantity=100.0, avg_price=150.0)
        broker.positions["@BTC"] = Position(symbol="@BTC", quantity=0.5, avg_price=50000.0)

        crypto_positions = broker.fetch_crypto_positions()
        assert len(crypto_positions.positions) == 1
        assert "@BTC" in crypto_positions.positions

    def test_fetch_account(self):
        """Test fetching account information."""
        broker = MockBroker()

        # Add some positions
        broker.positions["AAPL"] = Position(symbol="AAPL", quantity=100.0, avg_price=150.0)

        account = broker.fetch_account()
        assert account.account_name == "MockAccount"
        assert account.cash == 10000.0
        assert account.buying_power == 20000.0
        assert account.multiplier == 1.0
        assert len(account.positions.positions) == 1


class TestMockBrokerTimeManagement:
    """Test time management and control functionality."""

    def test_time_advancement(self):
        """Test time advancement functionality."""
        broker = MockBroker(
            current_time=dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
        )

        initial_time = broker.get_current_time()
        broker.advance_time()
        advanced_time = broker.get_current_time()

        # Should advance by poll_interval (default MIN_1)
        expected_advance = dt.timedelta(minutes=1)
        assert advanced_time - initial_time == expected_advance

    def test_tick_functionality(self):
        """Test tick functionality."""
        broker = MockBroker(
            current_time=dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
        )

        initial_time = broker.get_current_time()
        broker.tick()
        after_tick_time = broker.get_current_time()

        # Tick should advance time
        assert after_tick_time > initial_time

    def test_tick_counting(self):
        """Test tick counting functionality."""
        broker = MockBroker(realistic_simulation=False)

        assert broker.get_tick_count() == 0

        # Use start() method with max_ticks to test counting
        broker.set_max_ticks(2)
        broker.start({Interval.MIN_1: ["AAPL"]})
        assert broker.get_tick_count() == 2

        broker.reset_tick_count()
        assert broker.get_tick_count() == 0

    def test_max_ticks_control(self):
        """Test max ticks control for testing."""
        broker = MockBroker(realistic_simulation=False)
        broker.set_max_ticks(3)

        # Start polling - should stop after 3 ticks
        broker.start({Interval.MIN_1: ["AAPL"]})

        assert broker.get_tick_count() == 3

    def test_polling_control(self):
        """Test polling control methods."""
        broker = MockBroker()

        assert broker.continue_polling() is True

        broker.stop_polling()
        assert broker.continue_polling() is False

    def test_custom_time_provider(self):
        """Test custom time provider injection."""
        custom_time = dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
        time_provider = Mock(return_value=custom_time)

        broker = MockBroker(time_provider=time_provider)

        # The time provider should be used
        assert broker.time_provider == time_provider
        result_time = broker._default_time_provider()
        # Since _default_time_provider calls get_current_time, which uses stats.utc_timestamp
        assert isinstance(result_time, dt.datetime)


class TestMockBrokerPerformance:
    """Test performance controls and optimizations."""

    def test_realistic_simulation_false(self):
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

    def test_realistic_simulation_true(self):
        """Test realistic simulation mode with mock sleep."""
        mock_sleep = Mock()
        broker = MockBroker(
            realistic_simulation=True,
            sleep_function=mock_sleep
        )
        broker.set_max_ticks(2)

        broker.start({Interval.MIN_1: ["AAPL"]})

        # Sleep should be called
        assert mock_sleep.call_count == 2
        # Should be called with 60 seconds (1 minute interval)
        mock_sleep.assert_called_with(60)

    def test_clear_mock_data(self):
        """Test clearing mock data for memory management."""
        broker = MockBroker(
            current_time=dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc),
            epoch=dt.datetime(2023, 1, 1, 11, 0, 0, tzinfo=dt.timezone.utc)  # Only 1 hour of data
        )

        # Generate some data
        broker.fetch_price_history("AAPL", Interval.MIN_1)
        assert len(broker.mock_price_history) > 0

        # Clear data
        broker.clear_mock_data()
        assert len(broker.mock_price_history) == 0
        assert len(broker.rng) == 0

    def test_limit_mock_data_size(self):
        """Test limiting mock data size."""
        broker = MockBroker()

        # Create mock data with more than limit
        large_df = pl.DataFrame({
            "timestamp": [dt.datetime(2023, 1, 1) + dt.timedelta(minutes=i) for i in range(20000)],
            "price": [100.0] * 20000
        })
        broker.mock_price_history["AAPL"] = {Interval.MIN_1: large_df}

        # Apply size limit
        broker.limit_mock_data_size(10000)

        # Should be limited to 10000 rows
        limited_df = broker.mock_price_history["AAPL"][Interval.MIN_1]
        assert len(limited_df) == 10000

    def test_reset_state(self):
        """Test state reset functionality."""
        broker = MockBroker()

        # Add some data
        broker.orders["test"] = Mock()
        broker.positions["AAPL"] = Mock()
        broker.mock_price_history["AAPL"] = {Interval.MIN_1: pl.DataFrame()}
        broker.rng["AAPL"] = Mock()

        # Reset state
        broker.reset_state()

        assert len(broker.orders) == 0
        assert len(broker.positions) == 0
        assert len(broker.mock_price_history) == 0
        assert len(broker.rng) == 0


class TestMockBrokerMarketData:
    """Test market data related functionality."""

    def test_fetch_market_hours(self):
        """Test fetching market hours."""
        broker = MockBroker()

        test_date = dt.date(2023, 1, 1)
        market_hours = broker.fetch_market_hours(test_date)

        assert market_hours["is_open"] is True
        assert isinstance(market_hours["open_at"], dt.datetime)
        assert isinstance(market_hours["close_at"], dt.datetime)
        assert market_hours["open_at"].time() == dt.time(9, 30)
        assert market_hours["close_at"].time() == dt.time(16, 0)

    def test_fetch_option_market_data(self):
        """Test fetching option market data."""
        broker = MockBroker(
            current_time=dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc),
            epoch=dt.datetime(2023, 1, 1, 11, 0, 0, tzinfo=dt.timezone.utc)  # Only 1 hour of data
        )

        option_data = broker.fetch_option_market_data("AAPL")

        assert option_data.symbol == "AAPL"
        assert option_data.price is not None
        assert option_data.ask > option_data.price
        assert option_data.bid < option_data.price
        assert option_data.ask == option_data.price * 1.05
        assert option_data.bid == option_data.price * 0.95

    def test_fetch_chain_data(self):
        """Test fetching option chain data."""
        broker = MockBroker(
            current_time=dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc),
            epoch=dt.datetime(2023, 1, 1, 11, 0, 0, tzinfo=dt.timezone.utc)  # Only 1 hour of data
        )

        test_date = dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc)
        chain_data = broker.fetch_chain_data("AAPL", test_date)

        assert len(chain_data._df) > 0
        assert "exp_date" in chain_data._df.columns
        assert "strike" in chain_data._df.columns
        assert "type" in chain_data._df.columns
        assert "symbol" in chain_data._df.columns

    def test_fetch_chain_info(self):
        """Test fetching chain info."""
        broker = MockBroker(
            current_time=dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc)
        )

        chain_info = broker.fetch_chain_info("AAPL")

        assert chain_info.chain_id == "123456"
        assert len(chain_info.expiration_list) == 3

        # Check expiration dates are in the future
        current_date = dt.date(2023, 1, 1)
        for exp_date in chain_info.expiration_list:
            assert exp_date > current_date

    def test_supports_symbol(self):
        """Test symbol support checking."""
        broker = MockBroker()

        # Test supported symbols
        assert broker.supports_symbol("AAPL") is True
        assert broker.supports_symbol("GOOGL") is True
        assert broker.supports_symbol("MSFT") is True

        # Test unsupported symbol
        assert broker.supports_symbol("UNKNOWN") is False

    def test_get_supported_intervals_tickers(self):
        """Test getting supported intervals and tickers."""
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


class TestMockBrokerCredentials:
    """Test credential management functionality."""

    def test_create_secret(self):
        """Test creating secrets (should return empty dict for mock)."""
        broker = MockBroker()

        secret = broker.create_secret()
        assert isinstance(secret, dict)
        assert len(secret) == 0

    def test_refresh_cred(self):
        """Test credential refresh (should do nothing for mock)."""
        broker = MockBroker()

        # Should not raise any exception
        broker.refresh_cred()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
