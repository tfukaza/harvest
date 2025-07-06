"""
Unit tests for the storage base classes.

This comprehensive test suite covers both LocalAlgorithmStorage and CentralStorage classes
to ensure proper functionality of transaction history, performance tracking, and data management.

Test Coverage:
- LocalAlgorithmStorage (14 tests):
  * Initialization with various configurations
  * Transaction insertion and retrieval with filters
  * Algorithm performance tracking and UPSERT functionality
  * Automatic performance data updates across multiple intervals
  * Data cleanup based on storage limits
  * File-based database persistence

- CentralStorage (15 tests):
  * Initialization and configuration
  * Price history insertion and retrieval with UPSERT
  * Account performance tracking across multiple intervals
  * Data cleanup and retention policies
  * Time-based filtering and queries

- Integration & Compatibility (4 tests):
  * Algorithm isolation in LocalAlgorithmStorage
  * Shared data access in CentralStorage
  * Backward compatibility with Storage alias
  * Cross-class functionality

All tests use in-memory SQLite databases for fast execution and isolation.
The tests verify both happy path scenarios and edge cases like data cleanup,
UPSERT behavior, and filtering functionality.
"""

import sys
import os

# Add the harvest directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import datetime as dt
import pytest
import polars as pl
import tempfile
from unittest.mock import Mock, patch

# Import directly from the storage module to avoid circular imports
from harvest.storage._base import (
    LocalAlgorithmStorage,
    CentralStorage,
    Storage,
    PriceHistory,
    AccountPerformanceHistory,
    TransactionHistory,
    AlgorithmPerformanceHistory,
)
from harvest.definitions import (
    OrderSide,
    OrderEvent,
    RuntimeData,
    TickerFrame,
    TimeDelta,
    TimeSpan,
    Transaction,
    TransactionFrame,
)
from harvest.enum import Interval


class TestLocalAlgorithmStorage:
    """Test cases for LocalAlgorithmStorage class."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.algorithm_name = "test_algorithm"
        self.storage = LocalAlgorithmStorage(
            algorithm_name=self.algorithm_name,
            # Use in-memory database for testing
            db_path=None,
        )
        self.test_timestamp = dt.datetime(2024, 1, 1, 12, 0, 0)

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        storage = LocalAlgorithmStorage("test_algo")

        assert storage.algorithm_name == "test_algo"
        assert storage.transaction_storage_limit.value == 14
        assert "5min_1day" in storage.performance_storage_limit
        assert storage.performance_storage_limit["5min_1day"].value == 1

    def test_init_with_custom_limits(self):
        """Test initialization with custom storage limits."""
        custom_transaction_limit = TimeDelta(TimeSpan.DAY, 7)
        custom_performance_limits = {
            "5min_1day": TimeDelta(TimeSpan.DAY, 2),
            "custom_interval": TimeDelta(TimeSpan.DAY, 30),
        }

        storage = LocalAlgorithmStorage(
            algorithm_name="custom_algo",
            transaction_storage_limit=custom_transaction_limit,
            performance_storage_limit=custom_performance_limits,
        )

        assert storage.transaction_storage_limit.value == 7
        assert storage.performance_storage_limit["5min_1day"].value == 2
        assert storage.performance_storage_limit["custom_interval"].value == 30

    def test_init_with_file_database(self):
        """Test initialization with file-based database."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = f"sqlite:///{tmp.name}"

        try:
            storage = LocalAlgorithmStorage(
                algorithm_name="file_algo",
                db_path=db_path,
            )

            # Test that we can perform operations
            transaction = Transaction(
                timestamp=self.test_timestamp,
                symbol="AAPL",
                side=OrderSide.BUY,
                quantity=100.0,
                price=150.0,
                event=OrderEvent.FILL,
                algorithm_name="file_algo",
            )

            storage.insert_transaction(transaction)

            # Verify transaction was stored
            history = storage.get_transaction_history("AAPL")
            assert len(history.df) == 1

        finally:
            # Clean up
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)

    def test_insert_transaction(self):
        """Test inserting a transaction."""
        transaction = Transaction(
            timestamp=self.test_timestamp,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
            price=150.0,
            event=OrderEvent.FILL,
            algorithm_name=self.algorithm_name,
        )

        self.storage.insert_transaction(transaction)

        # Verify transaction was stored
        history = self.storage.get_transaction_history("AAPL")
        assert len(history.df) == 1

        row = history.df.row(0, named=True)
        assert row["symbol"] == "AAPL"
        assert row["side"] == "buy"  # OrderSide.BUY.value is "buy"
        assert row["quantity"] == 100.0
        assert row["price"] == 150.0
        assert row["event"] == "FILL"  # OrderEvent.FILL.value is "FILL"
        assert row["algorithm_name"] == self.algorithm_name

    def test_insert_multiple_transactions(self):
        """Test inserting multiple transactions."""
        transactions = [
            Transaction(
                timestamp=self.test_timestamp,
                symbol="AAPL",
                side=OrderSide.BUY,
                quantity=100.0,
                price=150.0,
                event=OrderEvent.FILL,
                algorithm_name=self.algorithm_name,
            ),
            Transaction(
                timestamp=self.test_timestamp + dt.timedelta(minutes=5),
                symbol="AAPL",
                side=OrderSide.SELL,
                quantity=50.0,
                price=155.0,
                event=OrderEvent.FILL,
                algorithm_name=self.algorithm_name,
            ),
            Transaction(
                timestamp=self.test_timestamp + dt.timedelta(minutes=10),
                symbol="GOOGL",
                side=OrderSide.BUY,
                quantity=25.0,
                price=2800.0,
                event=OrderEvent.FILL,
                algorithm_name=self.algorithm_name,
            ),
        ]

        for transaction in transactions:
            self.storage.insert_transaction(transaction)

        # Test getting all AAPL transactions
        aapl_history = self.storage.get_transaction_history("AAPL")
        assert len(aapl_history.df) == 2

        # Test getting all GOOGL transactions
        googl_history = self.storage.get_transaction_history("GOOGL")
        assert len(googl_history.df) == 1

    def test_get_transaction_history_with_filters(self):
        """Test getting transaction history with various filters."""
        # Insert test transactions
        base_time = self.test_timestamp
        transactions = [
            Transaction(base_time, "AAPL", OrderSide.BUY, 100.0, 150.0, OrderEvent.FILL, self.algorithm_name),
            Transaction(base_time + dt.timedelta(minutes=5), "AAPL", OrderSide.SELL, 50.0, 155.0, OrderEvent.FILL, self.algorithm_name),
            Transaction(base_time + dt.timedelta(minutes=10), "AAPL", OrderSide.BUY, 25.0, 152.0, OrderEvent.FILL, self.algorithm_name),
        ]

        for transaction in transactions:
            self.storage.insert_transaction(transaction)

        # Test filtering by side
        buy_history = self.storage.get_transaction_history("AAPL", side=OrderSide.BUY)
        assert len(buy_history.df) == 2

        sell_history = self.storage.get_transaction_history("AAPL", side=OrderSide.SELL)
        assert len(sell_history.df) == 1

        # Test filtering by time range
        time_filtered = self.storage.get_transaction_history(
            "AAPL",
            start=base_time + dt.timedelta(minutes=3),
            end=base_time + dt.timedelta(minutes=7)
        )
        assert len(time_filtered.df) == 1

    def test_insert_algorithm_performance(self):
        """Test inserting algorithm performance data."""
        self.storage.insert_algorithm_performance(
            timestamp=self.test_timestamp,
            interval="5min_1day",
            equity=10000.0,
            return_percentage=2.5,
            return_absolute=245.0,
        )

        # Verify performance data was stored
        performance = self.storage.get_algorithm_performance_history("5min_1day")
        assert len(performance) == 1

        row = performance.row(0, named=True)
        assert row["algorithm_name"] == self.algorithm_name
        assert row["interval"] == "5min_1day"
        assert row["equity"] == 10000.0
        assert row["return_percentage"] == 2.5
        assert row["return_absolute"] == 245.0

    def test_insert_algorithm_performance_upsert(self):
        """Test that duplicate timestamps get updated (UPSERT behavior)."""
        # Insert initial performance data
        self.storage.insert_algorithm_performance(
            timestamp=self.test_timestamp,
            interval="5min_1day",
            equity=10000.0,
            return_percentage=2.5,
            return_absolute=245.0,
        )

        # Insert updated data for same timestamp
        self.storage.insert_algorithm_performance(
            timestamp=self.test_timestamp,
            interval="5min_1day",
            equity=10500.0,
            return_percentage=5.0,
            return_absolute=500.0,
        )

        # Verify only one record exists with updated values
        performance = self.storage.get_algorithm_performance_history("5min_1day")
        assert len(performance) == 1

        row = performance.row(0, named=True)
        assert row["equity"] == 10500.0
        assert row["return_percentage"] == 5.0
        assert row["return_absolute"] == 500.0

    def test_get_algorithm_performance_history_with_filters(self):
        """Test getting performance history with time filters."""
        base_time = self.test_timestamp

        # Insert performance data at different times
        for i in range(5):
            self.storage.insert_algorithm_performance(
                timestamp=base_time + dt.timedelta(minutes=i*5),
                interval="5min_1day",
                equity=10000.0 + i*100,
                return_percentage=i,
                return_absolute=i*10,
            )

        # Test getting all data
        all_performance = self.storage.get_algorithm_performance_history("5min_1day")
        assert len(all_performance) == 5

        # Test time-based filtering
        filtered_performance = self.storage.get_algorithm_performance_history(
            "5min_1day",
            start=base_time + dt.timedelta(minutes=10),
            end=base_time + dt.timedelta(minutes=15)
        )
        assert len(filtered_performance) == 2

    def test_update_performance_data(self):
        """Test the automatic performance data update method."""
        # Test with 5-minute boundary (should update 5min_1day)
        timestamp_5min = dt.datetime(2024, 1, 1, 12, 5, 0)  # minute % 5 == 0

        self.storage.update_performance_data(
            timestamp=timestamp_5min,
            equity=10000.0,
            previous_equity=9500.0,
        )

        # Verify 5min_1day interval was updated
        performance = self.storage.get_algorithm_performance_history("5min_1day")
        assert len(performance) == 1

        row = performance.row(0, named=True)
        assert row["equity"] == 10000.0
        # Check return calculation: ((10000 - 9500) / 9500) * 100 ≈ 5.26%
        assert abs(row["return_percentage"] - 5.263157894736842) < 0.01

    def test_update_performance_data_multiple_intervals(self):
        """Test updating performance data for multiple intervals simultaneously."""
        # Test at market close (16:00) which should update daily intervals
        timestamp_close = dt.datetime(2024, 1, 1, 16, 0, 0)

        self.storage.update_performance_data(
            timestamp=timestamp_close,
            equity=12000.0,
            previous_equity=10000.0,
        )

        # Should update 1hour_1week (minute == 0) and daily intervals (hour == 16)
        hour_performance = self.storage.get_algorithm_performance_history("1hour_1week")
        assert len(hour_performance) == 1

        daily_performance = self.storage.get_algorithm_performance_history("1day_1month")
        assert len(daily_performance) == 1

    def test_get_latest_performance(self):
        """Test getting the latest performance data."""
        # Insert multiple performance records
        base_time = self.test_timestamp
        for i in range(3):
            self.storage.insert_algorithm_performance(
                timestamp=base_time + dt.timedelta(minutes=i*5),
                interval="5min_1day",
                equity=10000.0 + i*100,
                return_percentage=i,
                return_absolute=i*10,
            )

        # Get latest performance
        latest = self.storage.get_latest_performance("5min_1day")

        assert latest is not None
        assert latest["equity"] == 10200.0  # Last inserted value
        assert latest["return_percentage"] == 2
        assert latest["algorithm_name"] == self.algorithm_name

    def test_get_latest_performance_no_data(self):
        """Test getting latest performance when no data exists."""
        latest = self.storage.get_latest_performance("5min_1day")
        assert latest is None

    def test_transaction_storage_cleanup(self):
        """Test that old transactions are cleaned up based on storage limits."""
        # Create storage with very short retention (1 minute for testing)
        short_storage = LocalAlgorithmStorage(
            algorithm_name="cleanup_test",
            transaction_storage_limit=TimeDelta(TimeSpan.MINUTE, 1),
        )

        base_time = self.test_timestamp

        # Insert old transaction
        old_transaction = Transaction(
            timestamp=base_time,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
            price=150.0,
            event=OrderEvent.FILL,
            algorithm_name="cleanup_test",
        )
        short_storage.insert_transaction(old_transaction)

        # Insert new transaction (should trigger cleanup)
        new_transaction = Transaction(
            timestamp=base_time + dt.timedelta(minutes=5),  # 5 minutes later
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=50.0,
            price=155.0,
            event=OrderEvent.FILL,
            algorithm_name="cleanup_test",
        )
        short_storage.insert_transaction(new_transaction)

        # Old transaction should be cleaned up
        history = short_storage.get_transaction_history("AAPL")
        assert len(history.df) == 1

        # Should only have the new transaction
        row = history.df.row(0, named=True)
        assert row["side"] == "sell"  # OrderSide.SELL.value is "sell"
        assert row["quantity"] == 50.0


class TestCentralStorage:
    """Test cases for CentralStorage class."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.storage = CentralStorage(
            # Use in-memory database for testing
            db_path=None,
        )
        self.test_timestamp = dt.datetime(2024, 1, 1, 12, 0, 0)

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        storage = CentralStorage()

        assert Interval.MIN_1 in storage.price_storage_limit
        assert storage.price_storage_limit[Interval.MIN_1].value == 1
        assert "5min_1day" in storage.performance_storage_limit
        assert storage.performance_storage_limit["5min_1day"].value == 1

    def test_init_with_custom_limits(self):
        """Test initialization with custom storage limits."""
        custom_price_limits = {
            Interval.MIN_1: TimeDelta(TimeSpan.DAY, 2),
            Interval.MIN_5: TimeDelta(TimeSpan.DAY, 14),
        }
        custom_performance_limits = {
            "5min_1day": TimeDelta(TimeSpan.DAY, 2),
            "custom_interval": TimeDelta(TimeSpan.DAY, 30),
        }

        storage = CentralStorage(
            price_storage_limit=custom_price_limits,
            performance_storage_limit=custom_performance_limits,
        )

        assert storage.price_storage_limit[Interval.MIN_1].value == 2
        assert storage.price_storage_limit[Interval.MIN_5].value == 14
        assert storage.performance_storage_limit["5min_1day"].value == 2
        assert storage.performance_storage_limit["custom_interval"].value == 30

    def test_setup_method(self):
        """Test the setup method for compatibility."""
        mock_stats = Mock(spec=RuntimeData)

        self.storage.setup(mock_stats)

        assert self.storage.stats == mock_stats

    def test_insert_price_history(self):
        """Test inserting price history data."""
        # Create test price data
        df = pl.DataFrame({
            "timestamp": [self.test_timestamp, self.test_timestamp + dt.timedelta(minutes=1)],
            "symbol": ["AAPL", "AAPL"],
            "interval": ["MIN_1", "MIN_1"],  # Use proper interval format
            "open": [150.0, 151.0],
            "high": [152.0, 153.0],
            "low": [149.0, 150.0],
            "close": [151.0, 152.0],
            "volume": [1000.0, 1100.0],
        })

        ticker_frame = TickerFrame(df)
        self.storage.insert_price_history(ticker_frame)

        # Verify price data was stored
        history = self.storage.get_price_history("AAPL", Interval.MIN_1)
        assert len(history.df) == 2

        row = history.df.row(0, named=True)
        assert row["symbol"] == "AAPL"
        assert row["open"] == 150.0
        assert row["high"] == 152.0
        assert row["close"] == 151.0

    def test_insert_price_history_upsert(self):
        """Test that duplicate price data gets updated (UPSERT behavior)."""
        # Insert initial price data
        df1 = pl.DataFrame({
            "timestamp": [self.test_timestamp],
            "symbol": ["AAPL"],
            "interval": ["MIN_1"],
            "open": [150.0],
            "high": [152.0],
            "low": [149.0],
            "close": [151.0],
            "volume": [1000.0],
        })

        self.storage.insert_price_history(TickerFrame(df1))

        # Insert updated data for same timestamp
        df2 = pl.DataFrame({
            "timestamp": [self.test_timestamp],
            "symbol": ["AAPL"],
            "interval": ["MIN_1"],
            "open": [150.0],
            "high": [155.0],  # Updated high
            "low": [149.0],
            "close": [154.0],  # Updated close
            "volume": [1200.0],  # Updated volume
        })

        self.storage.insert_price_history(TickerFrame(df2))

        # Verify only one record exists with updated values
        history = self.storage.get_price_history("AAPL", Interval.MIN_1)
        assert len(history.df) == 1

        row = history.df.row(0, named=True)
        assert row["high"] == 155.0
        assert row["close"] == 154.0
        assert row["volume"] == 1200.0

    def test_get_price_history_with_filters(self):
        """Test getting price history with various filters."""
        # Insert test price data
        base_time = self.test_timestamp
        df = pl.DataFrame({
            "timestamp": [base_time + dt.timedelta(minutes=i) for i in range(5)],
            "symbol": ["AAPL"] * 5,
            "interval": ["MIN_1"] * 5,
            "open": [150.0 + i for i in range(5)],
            "high": [152.0 + i for i in range(5)],
            "low": [149.0 + i for i in range(5)],
            "close": [151.0 + i for i in range(5)],
            "volume": [1000.0 + i*100 for i in range(5)],
        })

        self.storage.insert_price_history(TickerFrame(df))

        # Test getting all data
        all_history = self.storage.get_price_history("AAPL", Interval.MIN_1)
        assert len(all_history.df) == 5

        # Test time-based filtering
        filtered_history = self.storage.get_price_history(
            "AAPL",
            Interval.MIN_1,
            start=base_time + dt.timedelta(minutes=2),
            end=base_time + dt.timedelta(minutes=3)
        )
        assert len(filtered_history.df) == 2

    def test_insert_account_performance(self):
        """Test inserting account performance data."""
        self.storage.insert_account_performance(
            timestamp=self.test_timestamp,
            interval="5min_1day",
            equity=50000.0,
            return_percentage=3.5,
            return_absolute=1750.0,
        )

        # Verify performance data was stored
        performance = self.storage.get_account_performance_history("5min_1day")
        assert len(performance) == 1

        row = performance.row(0, named=True)
        assert row["interval"] == "5min_1day"
        assert row["equity"] == 50000.0
        assert row["return_percentage"] == 3.5
        assert row["return_absolute"] == 1750.0

    def test_insert_account_performance_upsert(self):
        """Test that duplicate performance timestamps get updated."""
        # Insert initial performance data
        self.storage.insert_account_performance(
            timestamp=self.test_timestamp,
            interval="5min_1day",
            equity=50000.0,
            return_percentage=3.5,
            return_absolute=1750.0,
        )

        # Insert updated data for same timestamp
        self.storage.insert_account_performance(
            timestamp=self.test_timestamp,
            interval="5min_1day",
            equity=52000.0,
            return_percentage=4.0,
            return_absolute=2000.0,
        )

        # Verify only one record exists with updated values
        performance = self.storage.get_account_performance_history("5min_1day")
        assert len(performance) == 1

        row = performance.row(0, named=True)
        assert row["equity"] == 52000.0
        assert row["return_percentage"] == 4.0
        assert row["return_absolute"] == 2000.0

    def test_get_account_performance_history_with_filters(self):
        """Test getting account performance history with time filters."""
        base_time = self.test_timestamp

        # Insert performance data at different times
        for i in range(5):
            self.storage.insert_account_performance(
                timestamp=base_time + dt.timedelta(minutes=i*5),
                interval="5min_1day",
                equity=50000.0 + i*1000,
                return_percentage=i,
                return_absolute=i*100,
            )

        # Test getting all data
        all_performance = self.storage.get_account_performance_history("5min_1day")
        assert len(all_performance) == 5

        # Test time-based filtering
        filtered_performance = self.storage.get_account_performance_history(
            "5min_1day",
            start=base_time + dt.timedelta(minutes=10),
            end=base_time + dt.timedelta(minutes=15)
        )
        assert len(filtered_performance) == 2

    def test_update_account_performance_data(self):
        """Test the automatic account performance data update method."""
        # Test with 5-minute boundary (should update 5min_1day)
        timestamp_5min = dt.datetime(2024, 1, 1, 12, 5, 0)  # minute % 5 == 0

        self.storage.update_account_performance_data(
            timestamp=timestamp_5min,
            account_equity=50000.0,
            previous_account_equity=48000.0,
        )

        # Verify 5min_1day interval was updated
        performance = self.storage.get_account_performance_history("5min_1day")
        assert len(performance) == 1

        row = performance.row(0, named=True)
        assert row["equity"] == 50000.0
        # Check return calculation: ((50000 - 48000) / 48000) * 100 ≈ 4.17%
        assert abs(row["return_percentage"] - 4.166666666666667) < 0.01

    def test_update_account_performance_data_multiple_intervals(self):
        """Test updating account performance data for multiple intervals."""
        # Test at market close (16:00) which should update daily intervals
        timestamp_close = dt.datetime(2024, 1, 1, 16, 0, 0)

        self.storage.update_account_performance_data(
            timestamp=timestamp_close,
            account_equity=60000.0,
            previous_account_equity=50000.0,
        )

        # Should update 1hour_1week (minute == 0) and daily intervals (hour == 16)
        hour_performance = self.storage.get_account_performance_history("1hour_1week")
        assert len(hour_performance) == 1

        daily_performance = self.storage.get_account_performance_history("1day_1month")
        assert len(daily_performance) == 1

    def test_get_latest_account_performance(self):
        """Test getting the latest account performance data."""
        # Insert multiple performance records
        base_time = self.test_timestamp
        for i in range(3):
            self.storage.insert_account_performance(
                timestamp=base_time + dt.timedelta(minutes=i*5),
                interval="5min_1day",
                equity=50000.0 + i*1000,
                return_percentage=i,
                return_absolute=i*100,
            )

        # Get latest performance
        latest = self.storage.get_latest_account_performance("5min_1day")

        assert latest is not None
        assert latest["equity"] == 52000.0  # Last inserted value
        assert latest["return_percentage"] == 2
        assert latest["interval"] == "5min_1day"

    def test_get_latest_account_performance_no_data(self):
        """Test getting latest performance when no data exists."""
        latest = self.storage.get_latest_account_performance("5min_1day")
        assert latest is None

    def test_get_available_performance_intervals(self):
        """Test getting available performance intervals."""
        intervals = self.storage.get_available_performance_intervals()

        expected_intervals = [
            "5min_1day", "1hour_1week", "1day_1month",
            "1day_3months", "1day_1year", "variable_all"
        ]

        for interval in expected_intervals:
            assert interval in intervals

    def test_price_storage_cleanup(self):
        """Test that old price data is cleaned up based on storage limits."""
        # Create storage with very short retention (1 minute for testing)
        short_storage = CentralStorage(
            price_storage_limit={
                Interval.MIN_1: TimeDelta(TimeSpan.MINUTE, 1),
            }
        )

        base_time = self.test_timestamp

        # Insert old price data
        old_df = pl.DataFrame({
            "timestamp": [base_time],
            "symbol": ["AAPL"],
            "interval": ["MIN_1"],
            "open": [150.0],
            "high": [152.0],
            "low": [149.0],
            "close": [151.0],
            "volume": [1000.0],
        })
        short_storage.insert_price_history(TickerFrame(old_df))

        # Insert new price data (should trigger cleanup)
        new_df = pl.DataFrame({
            "timestamp": [base_time + dt.timedelta(minutes=5)],  # 5 minutes later
            "symbol": ["AAPL"],
            "interval": ["MIN_1"],
            "open": [155.0],
            "high": [157.0],
            "low": [154.0],
            "close": [156.0],
            "volume": [1200.0],
        })
        short_storage.insert_price_history(TickerFrame(new_df))

        # Old price data should be cleaned up
        history = short_storage.get_price_history("AAPL", Interval.MIN_1)
        assert len(history.df) == 1

        # Should only have the new price data
        row = history.df.row(0, named=True)
        assert row["close"] == 156.0
        assert row["volume"] == 1200.0


class TestBackwardCompatibility:
    """Test backward compatibility features."""

    def test_storage_alias(self):
        """Test that Storage is an alias for CentralStorage."""
        assert Storage is CentralStorage

    def test_storage_alias_functionality(self):
        """Test that Storage alias works the same as CentralStorage."""
        storage = Storage()

        # Test that it has the same methods
        assert hasattr(storage, 'insert_price_history')
        assert hasattr(storage, 'get_price_history')
        assert hasattr(storage, 'insert_account_performance')
        assert hasattr(storage, 'get_account_performance_history')

        # Test that it actually works
        test_timestamp = dt.datetime(2024, 1, 1, 12, 0, 0)
        storage.insert_account_performance(
            timestamp=test_timestamp,
            interval="5min_1day",
            equity=10000.0,
        )

        performance = storage.get_account_performance_history("5min_1day")
        assert len(performance) == 1


class TestIntegration:
    """Integration tests for both storage classes working together."""

    def test_different_algorithms_isolated(self):
        """Test that different algorithms have isolated local storage."""
        algo1_storage = LocalAlgorithmStorage("algorithm_1")
        algo2_storage = LocalAlgorithmStorage("algorithm_2")

        # Insert transaction for algorithm 1
        transaction1 = Transaction(
            timestamp=dt.datetime(2024, 1, 1, 12, 0, 0),
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
            price=150.0,
            event=OrderEvent.FILL,
            algorithm_name="algorithm_1",
        )
        algo1_storage.insert_transaction(transaction1)

        # Insert transaction for algorithm 2
        transaction2 = Transaction(
            timestamp=dt.datetime(2024, 1, 1, 12, 5, 0),
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=50.0,
            price=155.0,
            event=OrderEvent.FILL,
            algorithm_name="algorithm_2",
        )
        algo2_storage.insert_transaction(transaction2)

        # Each algorithm should only see its own transactions
        algo1_history = algo1_storage.get_transaction_history("AAPL")
        algo2_history = algo2_storage.get_transaction_history("AAPL")

        assert len(algo1_history.df) == 1
        assert len(algo2_history.df) == 1

        assert algo1_history.df.row(0, named=True)["side"] == "buy"
        assert algo2_history.df.row(0, named=True)["side"] == "sell"

    def test_central_storage_shared_across_algorithms(self):
        """Test that central storage is shared across all algorithms."""
        central_storage = CentralStorage()

        # Insert price data (this would typically be done by a data provider)
        df = pl.DataFrame({
            "timestamp": [dt.datetime(2024, 1, 1, 12, 0, 0)],
            "symbol": ["AAPL"],
            "interval": ["MIN_1"],
            "open": [150.0],
            "high": [152.0],
            "low": [149.0],
            "close": [151.0],
            "volume": [1000.0],
        })
        central_storage.insert_price_history(TickerFrame(df))

        # Both algorithms should be able to access the same price data
        price_history = central_storage.get_price_history("AAPL", Interval.MIN_1)
        assert len(price_history.df) == 1

        # Any algorithm can access this data
        row = price_history.df.row(0, named=True)
        assert row["symbol"] == "AAPL"
        assert row["close"] == 151.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
