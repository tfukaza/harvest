"""
Tests for MockBroker implementation.

These tests verify that MockBroker properly implements the Broker interface
and provides useful functionality for unit testing.
"""

import datetime as dt
import pytest
import polars as pl
from unittest.mock import MagicMock

from harvest.broker.mock import MockBroker
from harvest.definitions import (
    Account,
    AssetType,
    Order,
    OrderSide,
    OrderStatus,
    OrderTimeInForce,
    Position,
    RuntimeData,
    TickerCandle,
)
from harvest.enum import Interval


class TestMockBrokerBasic:
    """Basic tests for MockBroker initialization and configuration."""

    def test_init_default(self):
        """Test MockBroker initialization with default parameters."""
        broker = MockBroker()

        assert broker.exchange == "MOCK"
        assert len(broker.interval_list) > 0
        assert broker.req_keys == []
        assert broker.realistic_simulation is True
        assert broker.stock_market_times is False
        assert isinstance(broker.current_time, dt.datetime)
        assert isinstance(broker.epoch, dt.datetime)
        assert broker.orders == {}
        assert broker.positions == {}
        assert broker.stats is None

    def test_init_with_custom_time(self):
        """Test MockBroker initialization with custom time."""
        custom_time = dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
        broker = MockBroker(current_time=custom_time)

        assert broker.current_time == custom_time

    def test_init_with_string_time(self):
        """Test MockBroker initialization with string time."""
        broker = MockBroker(current_time="2023-01-01 12:00")

        expected_time = dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
        assert broker.current_time == expected_time

    def test_setup_runtime_data(self):
        """Test setup method with RuntimeData."""
        broker = MockBroker()
        runtime_data = MagicMock(spec=RuntimeData)
        runtime_data.utc_timestamp = dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)

        broker.setup(runtime_data)

        assert broker.stats is runtime_data

    def test_polling_control(self):
        """Test polling control methods."""
        broker = MockBroker()

        assert broker.continue_polling() is True

        broker.stop_polling()
        assert broker.continue_polling() is False


class TestMockBrokerAbstractMethods:
    """Test implementation of abstract methods from Broker base class."""

    def test_create_secret(self):
        """Test create_secret method."""
        broker = MockBroker()
        result = broker.create_secret()

        assert isinstance(result, dict)
        assert result == {}

    def test_refresh_cred(self):
        """Test refresh_cred method."""
        broker = MockBroker()
        # Should not raise any exception
        broker.refresh_cred()

    def test_fetch_market_hours(self):
        """Test fetch_market_hours method."""
        broker = MockBroker()
        test_date = dt.date(2023, 1, 1)

        result = broker.fetch_market_hours(test_date)

        assert isinstance(result, dict)
        assert "is_open" in result
        assert "open_at" in result
        assert "close_at" in result
        assert result["is_open"] is True
        assert isinstance(result["open_at"], dt.datetime)
        assert isinstance(result["close_at"], dt.datetime)

    def test_fetch_account_empty(self):
        """Test fetch_account with empty positions and orders."""
        broker = MockBroker()

        account = broker.fetch_account()

        assert isinstance(account, Account)
        assert account.account_name == "MockAccount"
        assert account.cash == 10000.0
        assert account.equity == 10000.0
        assert account.buying_power == 20000.0
        assert account.multiplier == 1.0
        assert account.asset_value == 0.0

    def test_fetch_positions_empty(self):
        """Test position fetching methods with empty positions."""
        broker = MockBroker()

        stock_positions = broker.fetch_stock_positions()
        option_positions = broker.fetch_option_positions()
        crypto_positions = broker.fetch_crypto_positions()

        assert len(stock_positions) == 0
        assert len(option_positions) == 0
        assert len(crypto_positions) == 0

    def test_fetch_order_queue_empty(self):
        """Test fetch_order_queue with empty orders."""
        broker = MockBroker()

        order_queue = broker.fetch_order_queue()

        assert len(order_queue) == 0


class TestMockBrokerOrderManagement:
    """Test order management functionality."""

    def test_order_stock_limit(self):
        """Test placing a stock limit order."""
        broker = MockBroker()

        order = broker.order_stock_limit(
            side=OrderSide.BUY,
            symbol="AAPL",
            quantity=100.0,
            limit_price=150.0,
            in_force=OrderTimeInForce.GTC
        )

        assert isinstance(order, Order)
        assert order.order_type == AssetType.STOCK
        assert order.symbol == "AAPL"
        assert order.quantity == 100.0
        assert order.side == OrderSide.BUY
        assert order.status == OrderStatus.OPEN
        assert order.order_id is not None
        assert order.order_id in broker.orders

    def test_order_crypto_limit(self):
        """Test placing a crypto limit order."""
        broker = MockBroker()

        order = broker.order_crypto_limit(
            side="buy",
            symbol="@BTC",
            quantity=0.5,
            limit_price=50000.0,
            in_force="gtc"
        )

        assert isinstance(order, Order)
        assert order.order_type == AssetType.CRYPTO
        assert order.symbol == "@BTC"
        assert order.quantity == 0.5
        assert order.side == OrderSide.BUY
        assert order.status == OrderStatus.OPEN
        assert order.order_id in broker.orders

    def test_order_option_limit(self):
        """Test placing an option limit order."""
        broker = MockBroker()
        exp_date = dt.datetime(2023, 12, 15, tzinfo=dt.timezone.utc)

        order = broker.order_option_limit(
            side="buy",
            symbol="SPY",
            quantity=1.0,
            limit_price=5.0,
            option_type="call",
            exp_date=exp_date,
            strike=400.0,
            in_force="gtc"
        )

        assert isinstance(order, Order)
        assert order.order_type == AssetType.OPTION
        assert order.quantity == 1.0
        assert order.side == OrderSide.BUY
        assert order.status == OrderStatus.OPEN
        assert order.base_symbol == "SPY"
        assert order.order_id in broker.orders

    def test_cancel_orders(self):
        """Test canceling orders."""
        broker = MockBroker()

        # Place an order
        order = broker.order_stock_limit(
            side=OrderSide.BUY,
            symbol="AAPL",
            quantity=100.0,
            limit_price=150.0
        )

        assert order.order_id in broker.orders

        # Cancel the order
        broker.cancel_stock_order(order.order_id)

        assert order.order_id not in broker.orders

    def test_fetch_order_status_existing(self):
        """Test fetching status of existing orders."""
        broker = MockBroker()

        # Place an order
        order = broker.order_stock_limit(
            side=OrderSide.BUY,
            symbol="AAPL",
            quantity=100.0,
            limit_price=150.0
        )

        # Fetch the order status
        fetched_order = broker.fetch_stock_order_status(order.order_id)

        assert fetched_order.order_id == order.order_id
        assert fetched_order.symbol == order.symbol
        assert fetched_order.status == OrderStatus.OPEN

    def test_fetch_order_status_nonexistent(self):
        """Test fetching status of non-existent orders."""
        broker = MockBroker()

        # Fetch non-existent order (should return mock filled order)
        fetched_order = broker.fetch_stock_order_status("nonexistent_id")

        assert fetched_order.order_id == "nonexistent_id"
        assert fetched_order.status == OrderStatus.FILLED
        assert fetched_order.filled_price is not None


class TestMockBrokerMarketData:
    """Test market data functionality."""

    def test_fetch_price_history_default_params(self):
        """Test fetching price history with default parameters."""
        broker = MockBroker()

        ticker_frame = broker.fetch_price_history("AAPL", Interval.MIN_1)

        assert ticker_frame is not None
        assert hasattr(ticker_frame, 'df')
        assert isinstance(ticker_frame.df, pl.DataFrame)

        # Check that the DataFrame has expected columns
        expected_columns = {"timestamp", "open", "high", "low", "close", "volume"}
        assert expected_columns.issubset(set(ticker_frame.df.columns))

    def test_fetch_price_history_with_dates(self):
        """Test fetching price history with specific date range."""
        broker = MockBroker()
        start = dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc)
        end = dt.datetime(2023, 1, 2, tzinfo=dt.timezone.utc)

        ticker_frame = broker.fetch_price_history("AAPL", Interval.MIN_1, start, end)

        assert ticker_frame is not None
        assert len(ticker_frame.df) > 0

        # Check that timestamps are within the requested range
        timestamps = ticker_frame.df["timestamp"].to_list()
        assert all(start <= ts <= end for ts in timestamps)

    def test_fetch_latest_price(self):
        """Test fetching latest price."""
        broker = MockBroker()

        candle = broker.fetch_latest_price("AAPL", Interval.MIN_1)

        assert isinstance(candle, TickerCandle)
        assert candle.symbol == "AAPL"
        assert candle.close > 0

    def test_fetch_option_market_data(self):
        """Test fetching option market data."""
        broker = MockBroker()

        option_data = broker.fetch_option_market_data("SPY")

        assert option_data.symbol == "SPY"
        assert option_data.price > 0
        assert option_data.ask > option_data.bid
        assert option_data.ask > option_data.price
        assert option_data.bid < option_data.price

    def test_fetch_chain_data(self):
        """Test fetching options chain data."""
        broker = MockBroker()
        test_date = dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc)

        chain_data = broker.fetch_chain_data("SPY", test_date)

        assert chain_data is not None
        assert hasattr(chain_data, 'df')
        assert isinstance(chain_data.df, pl.DataFrame)
        assert len(chain_data.df) > 0

        # Check expected columns
        expected_columns = {"exp_date", "strike", "type", "symbol"}
        assert expected_columns.issubset(set(chain_data.df.columns))

    def test_fetch_chain_info(self):
        """Test fetching chain info."""
        broker = MockBroker()

        chain_info = broker.fetch_chain_info("SPY")

        assert chain_info is not None
        assert hasattr(chain_info, 'exp_dates')
        assert len(chain_info.exp_dates) > 0
        assert all(isinstance(date, dt.date) for date in chain_info.exp_dates)


class TestMockBrokerHelperMethods:
    """Test helper methods for testing."""

    def test_set_price_data(self):
        """Test setting mock price data."""
        broker = MockBroker()

        candle = TickerCandle(
            symbol="AAPL",
            timestamp=dt.datetime(2023, 1, 1, 12, 0, tzinfo=dt.timezone.utc),
            open=150.0,
            high=155.0,
            low=149.0,
            close=152.0,
            volume=1000000
        )

        broker.set_price_data("AAPL", candle)

        assert "AAPL" in broker.mock_price_history
        assert Interval.MIN_1 in broker.mock_price_history["AAPL"]

        df = broker.mock_price_history["AAPL"][Interval.MIN_1]
        assert len(df) == 1
        assert df["close"].item() == 152.0

    def test_fulfill_order(self):
        """Test fulfilling an order."""
        broker = MockBroker()

        # Create an order
        order = broker.order_stock_limit(
            side=OrderSide.BUY,
            symbol="AAPL",
            quantity=100.0,
            limit_price=150.0
        )

        # Set some price data first
        candle = TickerCandle(
            symbol="AAPL",
            timestamp=dt.datetime(2023, 1, 1, 12, 0, tzinfo=dt.timezone.utc),
            open=150.0,
            high=155.0,
            low=149.0,
            close=152.0,
            volume=1000000
        )
        broker.set_price_data("AAPL", candle)

        # Fulfill the order
        broker.fulfill_order(order)

        # Check that order is filled
        assert order.status == OrderStatus.FILLED
        assert order.filled_price is not None
        assert order.filled_quantity == order.quantity
        assert order.filled_time is not None

        # Check that position is created
        assert "AAPL" in broker.positions
        position = broker.positions["AAPL"]
        assert position.quantity == 100.0

        # Check that order is removed from active orders
        assert order.order_id not in broker.orders

    def test_reset_state(self):
        """Test resetting broker state."""
        broker = MockBroker()

        # Add some data
        order = broker.order_stock_limit(
            side=OrderSide.BUY,
            symbol="AAPL",
            quantity=100.0,
            limit_price=150.0
        )

        candle = TickerCandle(
            symbol="AAPL",
            timestamp=dt.datetime(2023, 1, 1, 12, 0, tzinfo=dt.timezone.utc),
            open=150.0,
            high=155.0,
            low=149.0,
            close=152.0,
            volume=1000000
        )
        broker.set_price_data("AAPL", candle)
        broker.fulfill_order(order)

        # Verify data exists
        assert len(broker.orders) == 0  # Order was fulfilled and removed
        assert len(broker.positions) == 1
        assert len(broker.mock_price_history) == 1

        # Reset state
        broker.reset_state()

        # Verify state is cleared
        assert len(broker.orders) == 0
        assert len(broker.positions) == 0
        assert len(broker.mock_price_history) == 0
        assert len(broker.rng) == 0

    def test_get_current_time_with_stats(self):
        """Test get_current_time with runtime stats."""
        broker = MockBroker()

        # Without stats
        initial_time = broker.get_current_time()
        assert initial_time == broker.current_time

        # With stats
        runtime_data = MagicMock(spec=RuntimeData)
        stats_time = dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
        runtime_data.utc_timestamp = stats_time

        broker.setup(runtime_data)

        current_time = broker.get_current_time()
        assert current_time == stats_time

    def test_supports_symbol(self):
        """Test symbol support checking."""
        broker = MockBroker()

        # Test supported symbols
        assert broker.supports_symbol("AAPL") is True
        assert broker.supports_symbol("MSFT") is True
        assert broker.supports_symbol("GOOGL") is True

        # Test unsupported symbol
        assert broker.supports_symbol("UNKNOWN") is False

    def test_get_supported_intervals_tickers(self):
        """Test getting supported intervals and tickers."""
        broker = MockBroker()

        supported = broker._get_supported_intervals_tickers()

        assert isinstance(supported, dict)
        assert len(supported) > 0

        # Check that all intervals have ticker lists
        for interval, tickers in supported.items():
            assert isinstance(interval, Interval)
            assert isinstance(tickers, list)
            assert len(tickers) > 0
            assert all(isinstance(ticker, str) for ticker in tickers)


class TestMockBrokerPositionTypes:
    """Test position filtering by asset type."""

    def test_fetch_positions_by_type(self):
        """Test fetching positions filtered by asset type."""
        broker = MockBroker()

        # Add different types of positions
        broker.positions["AAPL"] = Position(symbol="AAPL", quantity=100.0, avg_price=150.0)
        broker.positions["SPY:20241215:400:C"] = Position(symbol="SPY:20241215:400:C", quantity=1.0, avg_price=5.0)
        broker.positions["@BTC"] = Position(symbol="@BTC", quantity=0.1, avg_price=50000.0)

        # Test stock positions
        stock_positions = broker.fetch_stock_positions()
        assert len(stock_positions) == 1
        assert "AAPL" in stock_positions

        # Test option positions
        option_positions = broker.fetch_option_positions()
        assert len(option_positions) == 1
        assert "SPY:20241215:400:C" in option_positions

        # Test crypto positions
        crypto_positions = broker.fetch_crypto_positions()
        assert len(crypto_positions) == 1
        assert "@BTC" in crypto_positions


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
