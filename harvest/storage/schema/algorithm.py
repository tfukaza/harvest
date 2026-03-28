"""Algorithm-local schema storage built on the flexible infrastructure layer."""


import datetime as dt
from typing import Any

import polars as pl
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from harvest.domain.definitions import OrderSide, TimeDelta, TimeSpan, Transaction, TransactionFrame
from harvest.storage.base import FlexibleStorage, StorageRecord


class TransactionHistory(StorageRecord):
    """Persisted transaction rows for a single algorithm."""

    __tablename__ = "transaction_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[dt.datetime]
    symbol: Mapped[str]
    side: Mapped[str]
    quantity: Mapped[float]
    price: Mapped[float]
    event: Mapped[str]
    algorithm_name: Mapped[str]


class AlgorithmPerformanceHistory(StorageRecord):
    """Persisted performance rows for a single algorithm."""

    __tablename__ = "algorithm_performance_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[dt.datetime]
    algorithm_name: Mapped[str]
    interval: Mapped[str]
    equity: Mapped[float]
    return_percentage: Mapped[float]
    return_absolute: Mapped[float]

    __table_args__ = (UniqueConstraint("timestamp", "algorithm_name", "interval"),)


def get_default_transaction_storage_limit() -> TimeDelta:
    """Return the default transaction retention limit."""
    return TimeDelta(TimeSpan.DAY, 14)


def get_default_algorithm_performance_storage_limit() -> dict[str, TimeDelta]:
    """Return the default algorithm performance retention limits."""
    return {
        "5min_1day": TimeDelta(TimeSpan.DAY, 1),
        "1hour_1week": TimeDelta(TimeSpan.DAY, 7),
        "1day_1month": TimeDelta(TimeSpan.DAY, 30),
        "1day_3months": TimeDelta(TimeSpan.DAY, 90),
        "1day_1year": TimeDelta(TimeSpan.DAY, 365),
        "variable_all": TimeDelta(TimeSpan.DAY, -1),
    }


class LocalAlgorithmStorage:
    """Schema-specific storage API for algorithm-local transactions and performance."""

    def __init__(
        self,
        algorithm_name: str,
        db_path: str | None = None,
        transaction_storage_limit: TimeDelta | None = None,
        performance_storage_limit: dict[str, TimeDelta] | None = None,
        storage: FlexibleStorage | None = None,
    ) -> None:
        """Initialize algorithm-local storage.

        Args:
            algorithm_name: Algorithm identifier.
            db_path: Optional SQLite database URL for the default SQL backend.
            transaction_storage_limit: Retention window for transaction history.
            performance_storage_limit: Retention windows for performance data.
            storage: Optional injected flexible storage backend.
        """
        self.algorithm_name = algorithm_name
        self.event_bus: Any | None = None
        self.is_running = True
        self.storage = storage or FlexibleStorage(
            database_url=db_path or f"sqlite:///algorithms/{algorithm_name}.db"
        )
        self.storage.register_table(TransactionHistory)
        self.storage.register_table(AlgorithmPerformanceHistory)

        self.transaction_storage_limit = transaction_storage_limit or get_default_transaction_storage_limit()

        default_performance_storage_limit = get_default_algorithm_performance_storage_limit()
        self.performance_storage_limit = (
            default_performance_storage_limit
            if performance_storage_limit is None
            else default_performance_storage_limit | performance_storage_limit
        )

        self.transaction_history_oldest_timestamp: dict[str, dt.datetime] = {}
        self.algorithm_performance_oldest_timestamp: dict[str, dt.datetime] = {}

    @property
    def db_engine(self):
        """Expose the SQLAlchemy engine for SQL-backed diagnostics."""
        return self.storage.db_engine

    def get_capabilities(self) -> list[str]:
        """Return the capability list for this storage surface."""
        capabilities = ["algorithm_storage", "transaction_history", "performance_tracking"]
        capabilities.append("csv_backend" if self.storage.is_csv_backend else "local_database")
        return capabilities

    async def register_with_discovery(self, service_registry: Any) -> None:
        """Register this storage instance with service discovery."""
        await service_registry.register_service(
            f"storage_{self.algorithm_name}",
            self,
            {"type": "algorithm_storage", "algorithm": self.algorithm_name},
        )

    def insert_transaction(self, transaction: Transaction) -> None:
        """Insert a transaction row for this algorithm."""
        latest_timestamp = transaction.timestamp
        symbol = transaction.symbol
        new_oldest_timestamp = latest_timestamp - self.transaction_storage_limit.delta_datetime

        if (
            symbol in self.transaction_history_oldest_timestamp
            and latest_timestamp - self.transaction_history_oldest_timestamp[symbol]
            > self.transaction_storage_limit.delta_datetime
        ):
            self.storage.delete_before(
                TransactionHistory,
                cutoff=new_oldest_timestamp,
                filters={"symbol": symbol, "algorithm_name": self.algorithm_name},
            )

        self.transaction_history_oldest_timestamp[symbol] = new_oldest_timestamp
        self.storage.upsert_rows(
            TransactionHistory,
            [
                {
                    "timestamp": transaction.timestamp,
                    "symbol": transaction.symbol,
                    "side": transaction.side.value,
                    "quantity": transaction.quantity,
                    "price": transaction.price,
                    "event": transaction.event,
                    "algorithm_name": transaction.algorithm_name,
                }
            ],
        )

    def get_transaction_history(
        self,
        symbol: str,
        side: OrderSide | None = None,
        start: dt.datetime | None = None,
        end: dt.datetime | None = None,
    ) -> TransactionFrame:
        """Retrieve transaction history for this algorithm."""
        filters: dict[str, Any] = {
            "symbol": symbol,
            "algorithm_name": self.algorithm_name,
        }
        if side is not None:
            filters["side"] = side.value

        frame = self.storage.fetch_rows(
            TransactionHistory,
            filters=filters,
            start=start,
            end=end,
            order_by=[("timestamp", True)],
        )
        return TransactionFrame(frame)

    def insert_algorithm_performance(
        self,
        timestamp: dt.datetime,
        interval: str,
        equity: float,
        return_percentage: float = 0.0,
        return_absolute: float = 0.0,
    ) -> None:
        """Insert or update algorithm performance for a time bucket."""
        if interval in self.performance_storage_limit and self.performance_storage_limit[interval].delta_datetime.days != -1:
            cutoff_time = timestamp - self.performance_storage_limit[interval].delta_datetime
            if (
                interval in self.algorithm_performance_oldest_timestamp
                and timestamp - self.algorithm_performance_oldest_timestamp[interval]
                > self.performance_storage_limit[interval].delta_datetime
            ):
                self.storage.delete_before(
                    AlgorithmPerformanceHistory,
                    cutoff=cutoff_time,
                    filters={"algorithm_name": self.algorithm_name, "interval": interval},
                )

            self.algorithm_performance_oldest_timestamp[interval] = cutoff_time

        self.storage.upsert_rows(
            AlgorithmPerformanceHistory,
            [
                {
                    "timestamp": timestamp,
                    "algorithm_name": self.algorithm_name,
                    "interval": interval,
                    "equity": equity,
                    "return_percentage": return_percentage,
                    "return_absolute": return_absolute,
                }
            ],
        )

    def get_algorithm_performance_history(
        self,
        interval: str,
        start: dt.datetime | None = None,
        end: dt.datetime | None = None,
    ) -> pl.DataFrame:
        """Retrieve algorithm performance history for an interval."""
        return self.storage.fetch_rows(
            AlgorithmPerformanceHistory,
            filters={"algorithm_name": self.algorithm_name, "interval": interval},
            start=start,
            end=end,
            order_by=[("timestamp", True)],
        )

    def update_performance_data(
        self,
        timestamp: dt.datetime,
        equity: float,
        previous_equity: float | None = None,
    ) -> None:
        """Update all applicable performance buckets for the given timestamp."""
        return_pct = 0.0
        return_abs = 0.0
        if previous_equity is not None and previous_equity > 0:
            return_pct = ((equity - previous_equity) / previous_equity) * 100
            return_abs = equity - previous_equity

        current_hour = timestamp.hour
        current_minute = timestamp.minute

        intervals_to_update: list[str] = []
        if current_minute % 5 == 0:
            intervals_to_update.append("5min_1day")
        if current_minute == 0:
            intervals_to_update.append("1hour_1week")
        if current_hour == 16 and current_minute == 0:
            intervals_to_update.extend(["1day_1month", "1day_3months", "1day_1year"])
        if current_hour == 0 and current_minute == 0:
            intervals_to_update.append("variable_all")

        for performance_interval in intervals_to_update:
            self.insert_algorithm_performance(
                timestamp=timestamp,
                interval=performance_interval,
                equity=equity,
                return_percentage=return_pct,
                return_absolute=return_abs,
            )

    def get_latest_performance(self, interval: str) -> dict[str, Any] | None:
        """Return the latest performance row for an interval."""
        frame = self.storage.fetch_rows(
            AlgorithmPerformanceHistory,
            filters={"algorithm_name": self.algorithm_name, "interval": interval},
            order_by=[("timestamp", False)],
        )
        if frame.is_empty():
            return None
        return dict(frame.row(0, named=True))
