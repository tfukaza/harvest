"""Shared market and account schema storage built on the flexible infrastructure layer."""

from __future__ import annotations

import datetime as dt
from typing import Any

import polars as pl
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from harvest.definitions import RuntimeData, TickerCandleList, TimeDelta, TimeSpan
from harvest.enum import Interval
from harvest.storage.base import FlexibleStorage, StorageRecord


class PriceHistory(StorageRecord):
    """Persisted OHLCV market data rows."""

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


class AccountPerformanceHistory(StorageRecord):
    """Persisted account-level performance rows."""

    __tablename__ = "account_performance_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[dt.datetime]
    interval: Mapped[str]
    equity: Mapped[float]
    return_percentage: Mapped[float]
    return_absolute: Mapped[float]

    __table_args__ = (UniqueConstraint("timestamp", "interval"),)


def get_default_price_storage_limit() -> dict[Interval, TimeDelta]:
    """Return the default market-data retention policy."""
    return {
        Interval.MIN_1: TimeDelta(TimeSpan.DAY, 1),
        Interval.MIN_5: TimeDelta(TimeSpan.DAY, 7),
        Interval.MIN_15: TimeDelta(TimeSpan.DAY, 14),
        Interval.MIN_30: TimeDelta(TimeSpan.DAY, 30),
        Interval.HR_1: TimeDelta(TimeSpan.DAY, 60),
        Interval.DAY_1: TimeDelta(TimeSpan.DAY, 365),
    }


def get_default_account_performance_storage_limit() -> dict[str, TimeDelta]:
    """Return the default account performance retention policy."""
    return {
        "5min_1day": TimeDelta(TimeSpan.DAY, 1),
        "1hour_1week": TimeDelta(TimeSpan.DAY, 7),
        "1day_1month": TimeDelta(TimeSpan.DAY, 30),
        "1day_3months": TimeDelta(TimeSpan.DAY, 90),
        "1day_1year": TimeDelta(TimeSpan.DAY, 365),
        "variable_all": TimeDelta(TimeSpan.DAY, -1),
    }


class CentralStorage:
    """Schema-specific storage API for shared market and account history."""

    def __init__(
        self,
        db_path: str | None = None,
        price_storage_limit: dict[Interval, TimeDelta] | None = None,
        performance_storage_limit: dict[str, TimeDelta] | None = None,
        storage: FlexibleStorage | None = None,
    ) -> None:
        """Initialize central storage.

        Args:
            db_path: Optional SQLite database URL for the default SQL backend.
            price_storage_limit: Per-interval price retention policy.
            performance_storage_limit: Account performance retention policy.
            storage: Optional injected flexible storage backend.
        """
        self.storage = storage or FlexibleStorage(database_url=db_path or "sqlite:///:memory:")
        self.storage.register_table(PriceHistory)
        self.storage.register_table(AccountPerformanceHistory)

        default_price_storage_limit = get_default_price_storage_limit()
        self.price_storage_limit = (
            default_price_storage_limit
            if price_storage_limit is None
            else default_price_storage_limit | price_storage_limit
        )

        default_performance_storage_limit = get_default_account_performance_storage_limit()
        self.performance_storage_limit = (
            default_performance_storage_limit
            if performance_storage_limit is None
            else default_performance_storage_limit | performance_storage_limit
        )

        self.price_history_oldest_timestamp: dict[str, dict[Interval, dt.datetime]] = {}
        self.account_performance_oldest_timestamp: dict[str, dt.datetime] = {}
        self.stats: RuntimeData | None = None

    @property
    def db_engine(self):
        """Expose the SQLAlchemy engine for SQL-backed diagnostics."""
        return self.storage.db_engine

    def setup(self, stats: RuntimeData) -> None:
        """Store runtime metadata for compatibility with existing callers."""
        self.stats = stats

    def insert_price_history(self, data: TickerCandleList) -> None:
        """Insert or update OHLCV market data."""
        frame = data.df
        if frame.is_empty():
            return

        interval_name = frame.head(1)["interval"].item()
        interval = Interval.from_str(interval_name)
        symbol = frame.head(1)["symbol"].item()
        latest_timestamp = frame.tail(1)["timestamp"].item()

        new_oldest_timestamp = latest_timestamp - self.price_storage_limit[interval].delta_datetime
        if (
            symbol in self.price_history_oldest_timestamp
            and interval in self.price_history_oldest_timestamp[symbol]
            and latest_timestamp - self.price_history_oldest_timestamp[symbol][interval]
            > self.price_storage_limit[interval].delta_datetime
        ):
            self.storage.delete_before(
                PriceHistory,
                cutoff=new_oldest_timestamp,
                filters={"symbol": symbol, "interval": str(interval)},
            )
        elif symbol not in self.price_history_oldest_timestamp:
            self.price_history_oldest_timestamp[symbol] = {}

        self.price_history_oldest_timestamp[symbol][interval] = new_oldest_timestamp
        self.storage.upsert_rows(PriceHistory, frame.to_dicts())

    def get_price_history(
        self,
        symbol: str,
        interval: Interval | None = None,
        start: dt.datetime | None = None,
        end: dt.datetime | None = None,
    ) -> TickerCandleList:
        """Retrieve OHLCV history for a symbol."""
        filters: dict[str, Any] = {"symbol": symbol}
        if interval is not None:
            filters["interval"] = str(interval)

        frame = self.storage.fetch_rows(
            PriceHistory,
            filters=filters,
            start=start,
            end=end,
            order_by=[("timestamp", True)],
        )
        return TickerCandleList(frame)

    def insert_account_performance(
        self,
        timestamp: dt.datetime,
        interval: str,
        equity: float,
        return_percentage: float = 0.0,
        return_absolute: float = 0.0,
    ) -> None:
        """Insert or update account performance for a time bucket."""
        if interval in self.performance_storage_limit and self.performance_storage_limit[interval].delta_datetime.days != -1:
            cutoff_time = timestamp - self.performance_storage_limit[interval].delta_datetime
            if (
                interval in self.account_performance_oldest_timestamp
                and timestamp - self.account_performance_oldest_timestamp[interval]
                > self.performance_storage_limit[interval].delta_datetime
            ):
                self.storage.delete_before(
                    AccountPerformanceHistory,
                    cutoff=cutoff_time,
                    filters={"interval": interval},
                )

            self.account_performance_oldest_timestamp[interval] = cutoff_time

        self.storage.upsert_rows(
            AccountPerformanceHistory,
            [
                {
                    "timestamp": timestamp,
                    "interval": interval,
                    "equity": equity,
                    "return_percentage": return_percentage,
                    "return_absolute": return_absolute,
                }
            ],
        )

    def get_account_performance_history(
        self,
        interval: str,
        start: dt.datetime | None = None,
        end: dt.datetime | None = None,
    ) -> pl.DataFrame:
        """Retrieve account performance history for an interval."""
        return self.storage.fetch_rows(
            AccountPerformanceHistory,
            filters={"interval": interval},
            start=start,
            end=end,
            order_by=[("timestamp", True)],
        )

    def update_account_performance_data(
        self,
        timestamp: dt.datetime,
        account_equity: float,
        previous_account_equity: float | None = None,
    ) -> None:
        """Update all applicable account performance buckets for the timestamp."""
        account_return_pct = 0.0
        account_return_abs = 0.0
        if previous_account_equity is not None and previous_account_equity > 0:
            account_return_pct = ((account_equity - previous_account_equity) / previous_account_equity) * 100
            account_return_abs = account_equity - previous_account_equity

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
            self.insert_account_performance(
                timestamp=timestamp,
                interval=performance_interval,
                equity=account_equity,
                return_percentage=account_return_pct,
                return_absolute=account_return_abs,
            )

    def get_latest_account_performance(self, interval: str) -> dict[str, Any] | None:
        """Return the latest account performance row for an interval."""
        frame = self.storage.fetch_rows(
            AccountPerformanceHistory,
            filters={"interval": interval},
            order_by=[("timestamp", False)],
        )
        if frame.is_empty():
            return None
        return dict(frame.row(0, named=True))

    def get_available_performance_intervals(self) -> list[str]:
        """Return the configured account performance interval keys."""
        return list(self.performance_storage_limit.keys())


Storage = CentralStorage
