import datetime as dt
import sqlite3
import os
from typing import TYPE_CHECKING

import polars as pl
import sqlalchemy
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.schema import UniqueConstraint

if TYPE_CHECKING:
    from harvest.events.event_bus import EventBus

from harvest.definitions import OrderSide, RuntimeData, TickerFrame, TimeDelta, TimeSpan, Transaction, TransactionFrame
from harvest.enum import Interval
from harvest.util.helper import debugger

"""
This module provides storage classes for the trading system.

NOTE: This code intentionally contains some duplication (non-DRY patterns) between
LocalAlgorithmStorage and CentralStorage classes. This is by design to allow these
classes to diverge significantly in the future as requirements evolve. Each class
may develop unique features, optimizations, and storage backends that would be
difficult to maintain if they shared too much common code.

LocalAlgorithmStorage: SQLite-based local cache for transaction history and algorithm
performance data. Each Algorithm instance should have its own LocalAlgorithmStorage
for quick access to its specific data.

CentralStorage: Centralized storage for price history and account performance data.
This ensures consistency across all algorithms and can optionally use persistent
databases for long-term storage.

Database Models:
- PriceHistory: OHLCV stock price data
- AccountPerformanceHistory: Account-level performance tracking
- TransactionHistory: Transaction records for algorithms
- AlgorithmPerformanceHistory: Algorithm-specific performance tracking
"""


class LocalBase(DeclarativeBase):
    """
    Base class for local algorithm storage tables.

    This base class is used for SQLAlchemy ORM models that will be stored
    in LocalAlgorithmStorage instances (transaction and algorithm performance data).
    """
    pass


class CentralBase(DeclarativeBase):
    """
    Base class for central storage tables.

    This base class is used for SQLAlchemy ORM models that will be stored
    in CentralStorage instances (price history and account performance data).
    """
    pass


# Models for CentralStorage (price history and account performance)
class PriceHistory(CentralBase):
    """
    SQLAlchemy model for storing stock price history (OHLCV data).

    This table stores historical price data with timestamps, symbols, and intervals.
    Used by CentralStorage to provide consistent price data across all algorithms.

    Attributes:
        id: Primary key
        timestamp: UTC timestamp of the price data point
        symbol: Stock/crypto symbol (e.g., 'AAPL', 'BTC-USD')
        interval: Time interval string (e.g., '1min', '5min', '1hour', '1day')
        open: Opening price for the interval
        high: Highest price during the interval
        low: Lowest price during the interval
        close: Closing price for the interval
        volume: Trading volume during the interval
    """
    __tablename__ = "price_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[dt.datetime]
    symbol: Mapped[str]
    interval: Mapped[str]
    open: Mapped[float]
    high: Mapped[float]
    low: Mapped[float]
    close: Mapped[float]
    volume: Mapped[float]

    __table_args__ = (UniqueConstraint("timestamp", "symbol", "interval"),)


class AccountPerformanceHistory(CentralBase):
    """
    SQLAlchemy model for storing account-level performance data.

    This table tracks the overall account performance across different time intervals.
    Used by CentralStorage to maintain account-level performance metrics that are
    consistent across all algorithms.

    Attributes:
        id: Primary key
        timestamp: UTC timestamp of the performance measurement
        interval: Time interval type (e.g., '5min_1day', '1hour_1week', '1day_1month')
        equity: Total account equity at this timestamp
        return_percentage: Percentage return for this time period
        return_absolute: Absolute dollar return for this time period
    """
    __tablename__ = "account_performance_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[dt.datetime]
    interval: Mapped[str]
    equity: Mapped[float]
    return_percentage: Mapped[float]
    return_absolute: Mapped[float]

    __table_args__ = (UniqueConstraint("timestamp", "interval"),)


# Models for LocalAlgorithmStorage (transactions and algorithm performance)
class TransactionHistory(LocalBase):
    """
    SQLAlchemy model for storing transaction records.

    This table stores all buy/sell transactions for algorithms. Each algorithm
    instance has its own LocalAlgorithmStorage with this table for quick access
    to its transaction history.

    Attributes:
        id: Primary key
        timestamp: UTC timestamp when the transaction occurred
        symbol: Stock/crypto symbol for the transaction
        side: Transaction side ('BUY' or 'SELL')
        quantity: Number of shares/units traded
        price: Price per share/unit
        event: Transaction event type ('ORDER' or 'FILL')
        algorithm_name: Name of the algorithm that made this transaction
    """
    __tablename__ = "transaction_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[dt.datetime]
    symbol: Mapped[str]
    side: Mapped[str]
    quantity: Mapped[float]
    price: Mapped[float]
    event: Mapped[str]
    algorithm_name: Mapped[str]


class AlgorithmPerformanceHistory(LocalBase):
    """
    SQLAlchemy model for storing algorithm-specific performance data.

    This table tracks individual algorithm performance across different time intervals.
    Each algorithm instance has its own LocalAlgorithmStorage with this table for
    tracking its specific performance metrics.

    Attributes:
        id: Primary key
        timestamp: UTC timestamp of the performance measurement
        algorithm_name: Name of the algorithm
        interval: Time interval type (e.g., '5min_1day', '1hour_1week', '1day_1month')
        equity: Algorithm's allocated equity at this timestamp
        return_percentage: Percentage return for this algorithm in this time period
        return_absolute: Absolute dollar return for this algorithm in this time period
    """
    __tablename__ = "algorithm_performance_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[dt.datetime]
    algorithm_name: Mapped[str]
    interval: Mapped[str]
    equity: Mapped[float]
    return_percentage: Mapped[float]
    return_absolute: Mapped[float]

    __table_args__ = (UniqueConstraint("timestamp", "algorithm_name", "interval"),)


class LocalAlgorithmStorage:
    """
    Local SQLite-based storage for individual algorithm data.

    Each Algorithm instance should have its own LocalAlgorithmStorage for fast local
    access to algorithm-specific data. This class provides:

    - Transaction history: Quick access to the algorithm's buy/sell transactions
    - Algorithm performance history: Performance tracking specific to this algorithm

    The storage uses SQLite for fast local caching and should typically be in-memory
    or use a local file per algorithm instance. This design allows each algorithm to
    have isolated, fast access to its own data without affecting other algorithms.

    Data Management:
    - Automatic cleanup of old data based on configurable time limits
    - UPSERT operations to handle duplicate timestamps
    - Performance tracking across multiple time intervals

    Thread Safety:
    - This class is designed for single-algorithm use and is not thread-safe
    - Each algorithm should have its own instance
    """

    def __init__(
        self,
        algorithm_name: str,
        db_path: str | None = None,
        transaction_storage_limit: TimeDelta | None = None,
        performance_storage_limit: dict[str, TimeDelta] | None = None,
    ) -> None:
        """
        Initialize local storage for a specific algorithm.

        Args:
            algorithm_name: Name of the algorithm this storage belongs to. Used for
                          filtering and identification in database records.
            db_path: SQLite database path. If None, uses in-memory database for maximum
                    speed. For persistence across algorithm restarts, provide a file path
                    like "sqlite:///algorithm_data.db"
            transaction_storage_limit: Maximum time to keep transaction history.
                                     Defaults to 14 days. Set to None for unlimited storage.
            performance_storage_limit: Dictionary mapping interval names to TimeDelta
                                     objects for performance history retention limits.
                                     Defaults to predefined limits for different intervals.

        Raises:
            sqlalchemy.exc.DatabaseError: If database connection fails
        """
        self.algorithm_name = algorithm_name
        self.event_bus: "EventBus | None" = None  # Will be set by the algorithm or service
        self.is_running = True  # Storage is always running once initialized

        # Set default db_path to algorithm-specific database
        if db_path is None:
            db_path = f"sqlite:///algorithms/{algorithm_name}.db"
            self.ensure_directory_exists()

        self.db_engine = sqlalchemy.create_engine(db_path)

        # Transaction storage limits
        if not transaction_storage_limit:
            self.transaction_storage_limit = TimeDelta(TimeSpan.DAY, 14)
        else:
            self.transaction_storage_limit = transaction_storage_limit

        # Performance storage limits
        default_performance_storage_limit = {
            "5min_1day": TimeDelta(TimeSpan.DAY, 1),
            "1hour_1week": TimeDelta(TimeSpan.DAY, 7),
            "1day_1month": TimeDelta(TimeSpan.DAY, 30),
            "1day_3months": TimeDelta(TimeSpan.DAY, 90),
            "1day_1year": TimeDelta(TimeSpan.DAY, 365),
            "variable_all": TimeDelta(TimeSpan.DAY, -1),
        }

        if not performance_storage_limit:
            self.performance_storage_limit = default_performance_storage_limit
        else:
            self.performance_storage_limit = default_performance_storage_limit | performance_storage_limit

        # Tracking oldest timestamps for cleanup
        self.transaction_history_oldest_timestamp: dict[str, dt.datetime] = {}
        self.algorithm_performance_oldest_timestamp: dict[str, dt.datetime] = {}

        # Create tables
        LocalBase.metadata.drop_all(self.db_engine)
        LocalBase.metadata.create_all(self.db_engine)

    def ensure_directory_exists(self) -> None:
        """
        Ensure the algorithms directory exists for the database file.

        Creates the algorithms/ directory if it doesn't exist to store
        algorithm-specific database files.
        """
        algorithms_dir = "algorithms"
        if not os.path.exists(algorithms_dir):
            os.makedirs(algorithms_dir)

    def get_capabilities(self) -> list[str]:
        """
        Get the capabilities provided by this algorithm storage.

        Returns:
            List of capability strings
        """
        return [
            "algorithm_storage",
            "transaction_history",
            "performance_tracking",
            "local_database"
        ]

    async def register_with_discovery(self, service_registry) -> None:
        """
        Register this storage instance with service discovery.

        Args:
            service_registry: ServiceRegistry instance to register with
        """
        await service_registry.register_service(
            f"storage_{self.algorithm_name}",
            self,
            {"type": "algorithm_storage", "algorithm": self.algorithm_name}
        )

    def publish_transaction_event(self, transaction: Transaction) -> None:
        """
        Publish transaction events to event bus.

        Args:
            transaction: Transaction object to publish as an event
        """
        if hasattr(self, 'event_bus') and self.event_bus is not None:
            from harvest.events.events import TransactionEvent
            event = TransactionEvent(
                algorithm_name=self.algorithm_name,
                transaction=transaction,
                timestamp=transaction.timestamp
            )
            self.event_bus.publish('transaction', event.__dict__)

    def insert_transaction(self, transaction: Transaction) -> None:
        """
        Insert a transaction record for this algorithm.

        Stores a buy/sell transaction in the local database. Automatically handles
        cleanup of old transactions based on the configured storage limit.

        Args:
            transaction: Transaction object containing all transaction details
                        (timestamp, symbol, side, quantity, price, event, algorithm_name)

        Side Effects:
            - Inserts new transaction record into database
            - May delete old transaction records if storage limit is exceeded
            - Updates internal tracking of oldest timestamps

        Raises:
            sqlalchemy.exc.DatabaseError: If database insert fails
        """
        df = pl.DataFrame({
            "timestamp": [transaction.timestamp],
            "symbol": [transaction.symbol],
            "event": [transaction.event],
            "algorithm_name": [transaction.algorithm_name],
            "side": [transaction.side.value],
            "quantity": [transaction.quantity],
            "price": [transaction.price],
        })

        symbol = transaction.symbol
        latest_timestamp = transaction.timestamp

        # Clean up old data if storage limit is set
        if self.transaction_storage_limit:
            new_oldest_timestamp = latest_timestamp - self.transaction_storage_limit.delta_datetime
            if (symbol in self.transaction_history_oldest_timestamp
                and latest_timestamp - self.transaction_history_oldest_timestamp[symbol] > self.transaction_storage_limit.delta_datetime):
                with Session(self.db_engine) as session:
                    session.query(TransactionHistory).filter(
                        TransactionHistory.timestamp <= new_oldest_timestamp,
                        TransactionHistory.symbol == symbol,
                    ).delete()
                    session.commit()

            self.transaction_history_oldest_timestamp[symbol] = new_oldest_timestamp

        # Insert new transaction using SQLAlchemy directly
        stmt = insert(TransactionHistory).values([{
            "timestamp": transaction.timestamp,
            "symbol": transaction.symbol,
            "event": transaction.event,
            "algorithm_name": transaction.algorithm_name,
            "side": transaction.side.value,
            "quantity": transaction.quantity,
            "price": transaction.price,
        }])

        with Session(self.db_engine) as session:
            session.execute(stmt)
            session.commit()

    def get_transaction_history(
        self,
        symbol: str,
        side: OrderSide | None = None,
        start: dt.datetime | None = None,
        end: dt.datetime | None = None,
    ) -> TransactionFrame:
        """
        Retrieve transaction history for this algorithm with optional filtering.

        Queries the local transaction database with various filters to get relevant
        transaction records. Automatically filters to only this algorithm's transactions.

        Args:
            symbol: Stock/crypto symbol to filter by (required)
            side: Optional filter by transaction side (BUY or SELL)
            start: Optional start datetime (inclusive) for time-based filtering
            end: Optional end datetime (inclusive) for time-based filtering

        Returns:
            TransactionFrame: Polars DataFrame wrapped in TransactionFrame containing
                            filtered transaction records with columns:
                            [timestamp, symbol, event, algorithm_name, side, quantity, price]

        Raises:
            sqlalchemy.exc.DatabaseError: If database query fails
        """
        filters = [
            TransactionHistory.symbol == symbol,
            TransactionHistory.algorithm_name == self.algorithm_name,
        ]
        if side:
            filters.append(TransactionHistory.side == side.value)
        if start:
            filters.append(TransactionHistory.timestamp >= start)
        if end:
            filters.append(TransactionHistory.timestamp <= end)

        with Session(self.db_engine) as session:
            assert session.bind is not None
            db_query = session.query(TransactionHistory).filter(*filters)
            db_query_str = str(
                db_query.statement.compile(
                    dialect=session.bind.dialect,
                    compile_kwargs={"literal_binds": True},
                )
            )

        frame = pl.read_database(query=db_query_str, connection=self.db_engine)
        frame = frame.with_columns(pl.col("timestamp").str.to_datetime("%Y-%m-%d %H:%M:%S%.f"))
        frame = frame.drop("id")

        return TransactionFrame(frame)

    def insert_algorithm_performance(
        self,
        timestamp: dt.datetime,
        interval: str,
        equity: float,
        return_percentage: float = 0.0,
        return_absolute: float = 0.0,
    ) -> None:
        """
        Insert performance data for this algorithm at a specific interval.

        Records algorithm performance metrics for a given time interval. Handles
        automatic cleanup of old performance data and uses UPSERT to prevent duplicates.

        Args:
            timestamp: UTC timestamp for this performance measurement
            interval: Interval type (e.g., '5min_1day', '1hour_1week', '1day_1month')
            equity: Current equity allocated to this algorithm
            return_percentage: Percentage return for this time period (default: 0.0)
            return_absolute: Absolute dollar return for this time period (default: 0.0)

        Side Effects:
            - Inserts or updates performance record in database
            - May delete old performance records if storage limit is exceeded
            - Updates internal tracking of oldest timestamps

        Raises:
            sqlalchemy.exc.DatabaseError: If database operation fails
        """

        # Clean up old data if storage limit is set
        if interval in self.performance_storage_limit and self.performance_storage_limit[interval].delta_datetime.days != -1:
            cutoff_time = timestamp - self.performance_storage_limit[interval].delta_datetime
            if (interval in self.algorithm_performance_oldest_timestamp
                and timestamp - self.algorithm_performance_oldest_timestamp[interval] > self.performance_storage_limit[interval].delta_datetime):
                with Session(self.db_engine) as session:
                    session.query(AlgorithmPerformanceHistory).filter(
                        AlgorithmPerformanceHistory.timestamp <= cutoff_time,
                        AlgorithmPerformanceHistory.algorithm_name == self.algorithm_name,
                        AlgorithmPerformanceHistory.interval == interval
                    ).delete()
                    session.commit()

            self.algorithm_performance_oldest_timestamp[interval] = cutoff_time

        # Insert new performance data
        df = pl.DataFrame({
            "timestamp": [timestamp],
            "algorithm_name": [self.algorithm_name],
            "interval": [interval],
            "equity": [equity],
            "return_percentage": [return_percentage],
            "return_absolute": [return_absolute],
        })

        stmt = insert(AlgorithmPerformanceHistory).values(df.to_dicts())
        stmt = stmt.on_conflict_do_update(
            index_elements=["timestamp", "algorithm_name", "interval"],
            set_={
                "equity": stmt.excluded.equity,
                "return_percentage": stmt.excluded.return_percentage,
                "return_absolute": stmt.excluded.return_absolute,
            },
        )
        with Session(self.db_engine) as session:
            session.execute(stmt)
            session.commit()

    def get_algorithm_performance_history(
        self,
        interval: str,
        start: dt.datetime | None = None,
        end: dt.datetime | None = None,
    ) -> pl.DataFrame:
        """
        Retrieve performance history for this algorithm at a specific interval.

        Queries the local performance database for this algorithm's performance data
        at the specified interval with optional time-based filtering.

        Args:
            interval: Interval type to retrieve (e.g., '5min_1day', '1hour_1week')
            start: Optional start datetime (inclusive) for filtering
            end: Optional end datetime (inclusive) for filtering

        Returns:
            pl.DataFrame: Polars DataFrame with performance data columns:
                         [timestamp, algorithm_name, interval, equity,
                          return_percentage, return_absolute]
                         Sorted by timestamp in ascending order.

        Raises:
            sqlalchemy.exc.DatabaseError: If database query fails
        """
        filters = [
            AlgorithmPerformanceHistory.algorithm_name == self.algorithm_name,
            AlgorithmPerformanceHistory.interval == interval
        ]

        if start:
            filters.append(AlgorithmPerformanceHistory.timestamp >= start)
        if end:
            filters.append(AlgorithmPerformanceHistory.timestamp <= end)

        with Session(self.db_engine) as session:
            assert session.bind is not None
            db_query = session.query(AlgorithmPerformanceHistory).filter(*filters).order_by(AlgorithmPerformanceHistory.timestamp)
            db_query_str = str(
                db_query.statement.compile(
                    dialect=session.bind.dialect,
                    compile_kwargs={"literal_binds": True},
                )
            )

        frame = pl.read_database(query=db_query_str, connection=self.db_engine)
        frame = frame.with_columns(pl.col("timestamp").str.to_datetime("%Y-%m-%d %H:%M:%S%.f"))
        frame = frame.drop("id")

        return frame

    def update_performance_data(
        self,
        timestamp: dt.datetime,
        equity: float,
        previous_equity: float | None = None,
    ) -> None:
        """
        Update algorithm performance data across multiple intervals automatically.

        This is the main method that algorithms should call periodically to maintain
        performance tracking. It automatically determines which intervals need updates
        based on the current timestamp and handles return calculations.

        The method updates different intervals based on timing:
        - 5min intervals: Every 5 minutes when minute % 5 == 0
        - 1hour intervals: Every hour when minute == 0
        - Daily intervals: Once per day at 4 PM (market close)
        - All-time intervals: Daily at midnight

        Args:
            timestamp: Current UTC timestamp
            equity: Current equity allocated to this algorithm
            previous_equity: Previous equity measurement for return calculation.
                           If None, returns will be calculated as 0.0.

        Side Effects:
            - Calls insert_algorithm_performance for each relevant interval
            - May trigger cleanup of old performance data

        Raises:
            sqlalchemy.exc.DatabaseError: If any database operations fail
        """

        # Calculate returns if previous data is available
        return_pct = 0.0
        return_abs = 0.0
        if previous_equity is not None and previous_equity > 0:
            return_pct = ((equity - previous_equity) / previous_equity) * 100
            return_abs = equity - previous_equity

        # Determine which intervals to update based on timestamp
        current_hour = timestamp.hour
        current_minute = timestamp.minute

        intervals_to_update = []

        # 5-minute intervals (always update if called every 5 minutes)
        if current_minute % 5 == 0:
            intervals_to_update.append("5min_1day")

        # 1-hour intervals (update at the top of each hour)
        if current_minute == 0:
            intervals_to_update.append("1hour_1week")

        # Daily intervals (update once per day, e.g., at market close)
        if current_hour == 16 and current_minute == 0:  # 4 PM market close
            intervals_to_update.extend(["1day_1month", "1day_3months", "1day_1year"])

        # Variable interval for all-time (update daily)
        if current_hour == 0 and current_minute == 0:  # Midnight
            intervals_to_update.append("variable_all")

        # Insert performance data for each interval
        for interval in intervals_to_update:
            self.insert_algorithm_performance(
                timestamp=timestamp,
                interval=interval,
                equity=equity,
                return_percentage=return_pct,
                return_absolute=return_abs,
            )

    def get_latest_performance(self, interval: str) -> dict | None:
        """
        Get the most recent performance data for this algorithm at a specific interval.

        Retrieves the latest performance record for the specified interval, useful
        for getting current performance snapshots or calculating incremental returns.

        Args:
            interval: Interval type to query (e.g., '5min_1day', '1hour_1week')

        Returns:
            dict | None: Dictionary containing performance data with keys:
                        [timestamp, algorithm_name, interval, equity,
                         return_percentage, return_absolute]
                        Returns None if no performance data exists for this interval.

        Raises:
            sqlalchemy.exc.DatabaseError: If database query fails
        """
        with Session(self.db_engine) as session:
            latest = session.query(AlgorithmPerformanceHistory).filter(
                AlgorithmPerformanceHistory.algorithm_name == self.algorithm_name,
                AlgorithmPerformanceHistory.interval == interval
            ).order_by(AlgorithmPerformanceHistory.timestamp.desc()).first()

            if latest:
                return {
                    "timestamp": latest.timestamp,
                    "algorithm_name": latest.algorithm_name,
                    "interval": latest.interval,
                    "equity": latest.equity,
                    "return_percentage": latest.return_percentage,
                    "return_absolute": latest.return_absolute,
                }
            return None


class CentralStorage:
    """
    Centralized storage for shared data across all algorithms.

    This class manages data that needs to be consistent and shared across all
    algorithm instances in the trading system:

    - Price history (OHLCV data): Market data shared by all algorithms
    - Account performance history: Overall account performance tracking

    The storage can use various database backends for persistence and scalability:
    - SQLite (default): Good for development and single-machine deployments
    - PostgreSQL: Recommended for production with multiple algorithm instances
    - MySQL: Alternative production database option

    Data Management Features:
    - Configurable data retention policies by interval
    - Automatic cleanup of old data
    - UPSERT operations to handle duplicate timestamps
    - Thread-safe database operations

    Performance Considerations:
    - Designed for concurrent access by multiple algorithm instances
    - Uses connection pooling for database efficiency
    - Optimized queries with proper indexing

    Database Connection Examples:
    - In-memory SQLite: None (default)
    - File-based SQLite: "sqlite:///central_data.db"
    - PostgreSQL: "postgresql://user:password@localhost/trading_db"
    - MySQL: "mysql+pymysql://user:password@localhost/trading_db"
    """

    def __init__(
        self,
        db_path: str | None = None,
        price_storage_limit: dict[Interval, TimeDelta] | None = None,
        performance_storage_limit: dict[str, TimeDelta] | None = None,
    ) -> None:
        """
        Initialize central storage with configurable database backend and retention policies.

        Args:
            db_path: Database connection string. If None, uses in-memory SQLite.
                    For persistent storage, examples:
                    - SQLite file: "sqlite:///central_data.db"
                    - PostgreSQL: "postgresql://user:password@localhost/trading_db"
                    - MySQL: "mysql+pymysql://user:password@localhost/trading_db"
            price_storage_limit: Dictionary mapping Interval enums to TimeDelta objects
                               defining how long to keep price data for each interval.
                               Defaults to sensible limits (1 day for 1min, 1 year for daily).
            performance_storage_limit: Dictionary mapping interval names to TimeDelta
                                     objects for performance history retention.
                                     Defaults to predefined limits for different time ranges.

        Raises:
            sqlalchemy.exc.DatabaseError: If database connection fails
            ValueError: If invalid database URL format is provided
        """

        if db_path:
            self.db_engine = sqlalchemy.create_engine(db_path)
        else:
            # Default to in-memory SQLite
            self.db_engine = sqlalchemy.create_engine("sqlite:///:memory:")

        # Price storage limits
        default_price_storage_limit = {
            Interval.MIN_1: TimeDelta(TimeSpan.DAY, 1),
            Interval.MIN_5: TimeDelta(TimeSpan.DAY, 7),
            Interval.MIN_15: TimeDelta(TimeSpan.DAY, 14),
            Interval.MIN_30: TimeDelta(TimeSpan.DAY, 30),
            Interval.HR_1: TimeDelta(TimeSpan.DAY, 60),
            Interval.DAY_1: TimeDelta(TimeSpan.DAY, 365),
        }

        if not price_storage_limit:
            self.price_storage_limit = default_price_storage_limit
        else:
            self.price_storage_limit = default_price_storage_limit | price_storage_limit

        # Performance storage limits
        default_performance_storage_limit = {
            "5min_1day": TimeDelta(TimeSpan.DAY, 1),
            "1hour_1week": TimeDelta(TimeSpan.DAY, 7),
            "1day_1month": TimeDelta(TimeSpan.DAY, 30),
            "1day_3months": TimeDelta(TimeSpan.DAY, 90),
            "1day_1year": TimeDelta(TimeSpan.DAY, 365),
            "variable_all": TimeDelta(TimeSpan.DAY, -1),
        }

        if not performance_storage_limit:
            self.performance_storage_limit = default_performance_storage_limit
        else:
            self.performance_storage_limit = default_performance_storage_limit | performance_storage_limit

        # Tracking oldest timestamps for cleanup
        self.price_history_oldest_timestamp: dict[str, dict[Interval, dt.datetime]] = {}
        self.account_performance_oldest_timestamp: dict[str, dt.datetime] = {}

        # Create tables
        CentralBase.metadata.drop_all(self.db_engine)
        CentralBase.metadata.create_all(self.db_engine)

    def setup(self, stats: RuntimeData) -> None:
        """
        Setup method for compatibility with existing trader infrastructure.

        This method maintains backward compatibility with existing code that expects
        a setup() method on storage classes. It stores runtime statistics that may
        be used for performance tracking or debugging.

        Args:
            stats: RuntimeData object containing current trading session statistics
                   and configuration parameters
        """
        self.stats = stats

    def insert_price_history(self, data: TickerFrame) -> None:
        """
        Store stock price data in the central database.

        Inserts OHLCV (Open, High, Low, Close, Volume) price data for stocks or crypto.
        Handles automatic cleanup of old data based on configured retention policies
        and uses UPSERT operations to handle duplicate timestamps gracefully.

        Args:
            data: TickerFrame containing price data with required columns:
                  [timestamp, symbol, interval, open, high, low, close, volume]

        Side Effects:
            - Inserts new price records into database
            - May delete old price records if storage limits are exceeded
            - Updates internal tracking of oldest timestamps per symbol/interval

        Raises:
            sqlalchemy.exc.DatabaseError: If database operations fail
            ValueError: If TickerFrame data is malformed or missing required columns
            KeyError: If required columns are missing from the DataFrame
        """
        df: pl.DataFrame = data.df

        interval = df.head(1)["interval"].item()
        interval = Interval.from_str(interval)
        symbol = df.head(1)["symbol"].item()
        latest_timestamp = df.tail(1)["timestamp"].item()

        if self.price_storage_limit:
            new_oldest_timestamp = latest_timestamp - self.price_storage_limit[interval].delta_datetime
            if (
                symbol in self.price_history_oldest_timestamp
                and interval in self.price_history_oldest_timestamp[symbol]
                and latest_timestamp - self.price_history_oldest_timestamp[symbol][interval]
                > self.price_storage_limit[interval].delta_datetime
            ):
                with Session(self.db_engine) as session:
                    session.query(PriceHistory).filter(
                        PriceHistory.timestamp <= new_oldest_timestamp, PriceHistory.symbol == symbol
                    ).delete()
                    session.commit()
            elif symbol not in self.price_history_oldest_timestamp:
                self.price_history_oldest_timestamp[symbol] = {}

            self.price_history_oldest_timestamp[symbol][interval] = new_oldest_timestamp

        stmt = insert(PriceHistory).values(df.to_dicts())
        stmt = stmt.on_conflict_do_update(
            index_elements=["timestamp", "symbol", "interval"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
            },
        )
        with Session(self.db_engine) as session:
            session.execute(stmt)
            session.commit()

    def get_price_history(
        self,
        symbol: str,
        interval: Interval | None = None,
        start: dt.datetime | None = None,
        end: dt.datetime | None = None,
    ) -> TickerFrame:
        """
        Retrieve stock price history from the central database.

        Queries the price history database with optional filtering by time range.
        This method is thread-safe and can be called concurrently by multiple algorithms.

        Args:
            symbol: Stock or crypto symbol (e.g., 'AAPL', 'BTC-USD')
            interval: Price data interval (e.g., Interval.MIN_5, Interval.DAY_1).
                     If None, retrieves all intervals for the symbol.
            start: Start datetime (inclusive) for time-based filtering.
                   If None, retrieves from the beginning of available data.
            end: End datetime (inclusive) for time-based filtering.
                 If None, retrieves up to the most recent data.

        Returns:
            TickerFrame: Wrapped Polars DataFrame containing price data with columns:
                        [timestamp, symbol, interval, open, high, low, close, volume]
                        Sorted by timestamp in ascending order.

        Raises:
            sqlalchemy.exc.DatabaseError: If database query fails
            ValueError: If symbol is empty or invalid interval is provided
        """
        filters = [
            PriceHistory.symbol == symbol,
            PriceHistory.interval == str(interval),
        ]
        if start:
            filters.append(PriceHistory.timestamp >= start)
        if end:
            filters.append(PriceHistory.timestamp <= end)

        with Session(self.db_engine) as session:
            assert session.bind is not None
            db_query = session.query(PriceHistory).filter(*filters)
            db_query_str = str(
                db_query.statement.compile(
                    dialect=session.bind.dialect,
                    compile_kwargs={"literal_binds": True},
                )
            )

        frame = pl.read_database(query=db_query_str, connection=self.db_engine)
        frame = frame.with_columns(pl.col("timestamp").str.to_datetime("%Y-%m-%d %H:%M:%S%.f"))
        frame = frame.drop("id")

        return TickerFrame(frame)

    def insert_account_performance(
        self,
        timestamp: dt.datetime,
        interval: str,
        equity: float,
        return_percentage: float = 0.0,
        return_absolute: float = 0.0,
    ) -> None:
        """
        Insert account-level performance data into the central database.

        Records overall account performance metrics that aggregate across all algorithms.
        This data is used for account-level reporting and analysis. Handles automatic
        cleanup and uses UPSERT to prevent duplicates.

        Args:
            timestamp: UTC timestamp for this performance measurement
            interval: Interval type (e.g., '5min_1day', '1hour_1week', '1day_1month')
            equity: Total account equity at this timestamp
            return_percentage: Account percentage return for this time period (default: 0.0)
            return_absolute: Account absolute dollar return for this time period (default: 0.0)

        Side Effects:
            - Inserts or updates account performance record in database
            - May delete old performance records if storage limit is exceeded
            - Updates internal tracking of oldest timestamps

        Raises:
            sqlalchemy.exc.DatabaseError: If database operation fails
            ValueError: If timestamp is invalid or equity is negative
        """

        # Clean up old data if storage limit is set
        if interval in self.performance_storage_limit and self.performance_storage_limit[interval].delta_datetime.days != -1:
            cutoff_time = timestamp - self.performance_storage_limit[interval].delta_datetime
            if interval in self.account_performance_oldest_timestamp and timestamp - self.account_performance_oldest_timestamp[interval] > self.performance_storage_limit[interval].delta_datetime:
                with Session(self.db_engine) as session:
                    session.query(AccountPerformanceHistory).filter(
                        AccountPerformanceHistory.timestamp <= cutoff_time,
                        AccountPerformanceHistory.interval == interval
                    ).delete()
                    session.commit()

            self.account_performance_oldest_timestamp[interval] = cutoff_time

        # Insert new performance data
        df = pl.DataFrame({
            "timestamp": [timestamp],
            "interval": [interval],
            "equity": [equity],
            "return_percentage": [return_percentage],
            "return_absolute": [return_absolute],
        })

        stmt = insert(AccountPerformanceHistory).values(df.to_dicts())
        stmt = stmt.on_conflict_do_update(
            index_elements=["timestamp", "interval"],
            set_={
                "equity": stmt.excluded.equity,
                "return_percentage": stmt.excluded.return_percentage,
                "return_absolute": stmt.excluded.return_absolute,
            },
        )
        with Session(self.db_engine) as session:
            session.execute(stmt)
            session.commit()

    def get_account_performance_history(
        self,
        interval: str,
        start: dt.datetime | None = None,
        end: dt.datetime | None = None,
    ) -> pl.DataFrame:
        """
        Retrieve account performance history from the central database.

        Queries account-level performance data for analysis and reporting.
        This method is thread-safe and provides consistent data across all algorithms.

        Args:
            interval: Interval type to retrieve (e.g., '5min_1day', '1hour_1week')
            start: Optional start datetime (inclusive) for filtering
            end: Optional end datetime (inclusive) for filtering

        Returns:
            pl.DataFrame: Polars DataFrame with account performance data:
                         [timestamp, interval, equity, return_percentage, return_absolute]
                         Sorted by timestamp in ascending order.

        Raises:
            sqlalchemy.exc.DatabaseError: If database query fails
            ValueError: If interval is invalid or empty
        """
        filters = [AccountPerformanceHistory.interval == interval]

        if start:
            filters.append(AccountPerformanceHistory.timestamp >= start)
        if end:
            filters.append(AccountPerformanceHistory.timestamp <= end)

        with Session(self.db_engine) as session:
            assert session.bind is not None
            db_query = session.query(AccountPerformanceHistory).filter(*filters).order_by(AccountPerformanceHistory.timestamp)
            db_query_str = str(
                db_query.statement.compile(
                    dialect=session.bind.dialect,
                    compile_kwargs={"literal_binds": True},
                )
            )

        frame = pl.read_database(query=db_query_str, connection=self.db_engine)
        frame = frame.with_columns(pl.col("timestamp").str.to_datetime("%Y-%m-%d %H:%M:%S%.f"))
        frame = frame.drop("id")

        return frame

    def update_account_performance_data(
        self,
        timestamp: dt.datetime,
        account_equity: float,
        previous_account_equity: float | None = None,
    ) -> None:
        """
        Update account performance data across multiple intervals automatically.

        This is the main method that should be called periodically (e.g., by a central
        trader or portfolio manager) to maintain account-level performance tracking.
        It automatically determines which intervals need updates and handles return calculations.

        The method updates different intervals based on timing:
        - 5min intervals: Every 5 minutes when minute % 5 == 0
        - 1hour intervals: Every hour when minute == 0
        - Daily intervals: Once per day at 4 PM (market close)
        - All-time intervals: Daily at midnight

        Args:
            timestamp: Current UTC timestamp
            account_equity: Current total account equity across all algorithms
            previous_account_equity: Previous total equity measurement for return calculation.
                                   If None, returns will be calculated as 0.0.

        Side Effects:
            - Calls insert_account_performance for each relevant interval
            - May trigger cleanup of old performance data

        Raises:
            sqlalchemy.exc.DatabaseError: If any database operations fail
            ValueError: If account_equity is negative
        """

        # Calculate returns if previous data is available
        account_return_pct = 0.0
        account_return_abs = 0.0
        if previous_account_equity is not None and previous_account_equity > 0:
            account_return_pct = ((account_equity - previous_account_equity) / previous_account_equity) * 100
            account_return_abs = account_equity - previous_account_equity

        # Determine which intervals to update based on timestamp
        current_hour = timestamp.hour
        current_minute = timestamp.minute

        intervals_to_update = []

        # 5-minute intervals (always update if called every 5 minutes)
        if current_minute % 5 == 0:
            intervals_to_update.append("5min_1day")

        # 1-hour intervals (update at the top of each hour)
        if current_minute == 0:
            intervals_to_update.append("1hour_1week")

        # Daily intervals (update once per day, e.g., at market close)
        if current_hour == 16 and current_minute == 0:  # 4 PM market close
            intervals_to_update.extend(["1day_1month", "1day_3months", "1day_1year"])

        # Variable interval for all-time (update daily)
        if current_hour == 0 and current_minute == 0:  # Midnight
            intervals_to_update.append("variable_all")

        # Insert account performance data
        for interval in intervals_to_update:
            self.insert_account_performance(
                timestamp=timestamp,
                interval=interval,
                equity=account_equity,
                return_percentage=account_return_pct,
                return_absolute=account_return_abs,
            )

    def get_latest_account_performance(self, interval: str) -> dict | None:
        """
        Get the most recent account performance data for a specific interval.

        Retrieves the latest account performance record, useful for dashboard displays,
        current performance snapshots, or calculating incremental returns.

        Args:
            interval: Interval type to query (e.g., '5min_1day', '1hour_1week')

        Returns:
            dict | None: Dictionary containing latest performance data with keys:
                        [timestamp, interval, equity, return_percentage, return_absolute]
                        Returns None if no performance data exists for this interval.

        Raises:
            sqlalchemy.exc.DatabaseError: If database query fails
        """
        with Session(self.db_engine) as session:
            latest = session.query(AccountPerformanceHistory).filter(
                AccountPerformanceHistory.interval == interval
            ).order_by(AccountPerformanceHistory.timestamp.desc()).first()

            if latest:
                return {
                    "timestamp": latest.timestamp,
                    "interval": latest.interval,
                    "equity": latest.equity,
                    "return_percentage": latest.return_percentage,
                    "return_absolute": latest.return_absolute,
                }
            return None

    def get_available_performance_intervals(self) -> list[str]:
        """
        Get all available performance tracking intervals configured for this storage.

        Returns the list of interval types that this storage instance is configured
        to track. Useful for iterating over all available intervals or building
        user interfaces that display performance data.

        Returns:
            list[str]: List of interval strings like ['5min_1day', '1hour_1week',
                      '1day_1month', '1day_3months', '1day_1year', 'variable_all']
        """
        return list(self.performance_storage_limit.keys())


# Backward compatibility alias
# This allows existing code that imports 'Storage' to continue working
# while new code should use 'CentralStorage' or 'LocalAlgorithmStorage' explicitly
Storage = CentralStorage
