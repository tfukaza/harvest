"""Sanity tests for the phase 4.5 storage surfaces."""


import datetime as dt
from pathlib import Path

import polars as pl

from harvest.domain.definitions import OrderEvent, OrderSide, TickerCandleList, Transaction
from harvest.domain.enum import Interval
from harvest.services.central_storage_service import CentralStorageService
from harvest.storage import CSVStorage, FlexibleStorage
from harvest.storage.schema.algorithm import LocalAlgorithmStorage
from harvest.storage.schema.market import CentralStorage, PriceHistory


def test_flexible_storage_upserts_registered_sqlite_rows(tmp_path) -> None:
    storage = FlexibleStorage(database_url=f"sqlite:///{tmp_path / 'market.db'}")
    storage.register_table(PriceHistory)

    timestamp = dt.datetime(2026, 3, 12, 10, 0, 0)
    storage.upsert_rows(
        PriceHistory,
        [
            {
                "timestamp": timestamp,
                "symbol": "AAPL",
                "interval": str(Interval.MIN_1),
                "open": 100.0,
                "high": 101.0,
                "low": 99.5,
                "close": 100.5,
                "volume": 10_000.0,
            },
            {
                "timestamp": timestamp,
                "symbol": "AAPL",
                "interval": str(Interval.MIN_1),
                "open": 100.0,
                "high": 102.0,
                "low": 99.5,
                "close": 101.5,
                "volume": 12_000.0,
            },
        ],
    )

    frame = storage.fetch_rows(
        PriceHistory,
        filters={"symbol": "AAPL", "interval": str(Interval.MIN_1)},
        order_by=[("timestamp", True)],
    )

    assert frame.height == 1
    assert frame["close"].item() == 101.5
    assert frame["volume"].item() == 12_000.0


def test_local_algorithm_storage_uses_algorithm_directory(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    storage = LocalAlgorithmStorage("test_algo")

    assert Path("algorithms").exists()
    assert storage.db_engine is not None
    assert str(storage.db_engine.url) == "sqlite:///algorithms/test_algo.db"


def test_local_algorithm_storage_supports_csv_backend(tmp_path) -> None:
    backend = CSVStorage(str(tmp_path / "csv"))
    storage = LocalAlgorithmStorage("test_algo", storage=backend)

    storage.insert_transaction(
        Transaction(
            timestamp=dt.datetime(2026, 3, 12, 10, 0, 0),
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=2.0,
            price=101.25,
            event=OrderEvent.FILL,
            algorithm_name="test_algo",
        )
    )

    history = storage.get_transaction_history("AAPL")

    assert (tmp_path / "csv" / "transaction_history.csv").exists()
    assert history.df.height == 1
    assert history.df["symbol"].item() == "AAPL"
    assert history.df["price"].item() == 101.25


def test_central_storage_supports_csv_backend(tmp_path) -> None:
    backend = CSVStorage(str(tmp_path / "central_csv"))
    storage = CentralStorage(storage=backend)
    price_data = TickerCandleList(
        pl.DataFrame(
            {
                "timestamp": [dt.datetime(2026, 3, 12, 10, 0, 0)],
                "symbol": ["AAPL"],
                "interval": [str(Interval.MIN_1)],
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.5],
                "volume": [1_000.0],
            }
        )
    )

    storage.insert_price_history(price_data)
    storage.insert_account_performance(
        timestamp=dt.datetime(2026, 3, 12, 10, 0, 0),
        interval="5min_1day",
        equity=10_000.0,
        return_percentage=1.25,
        return_absolute=125.0,
    )

    history = storage.get_price_history("AAPL", Interval.MIN_1)
    performance = storage.get_account_performance_history("5min_1day")

    assert (tmp_path / "central_csv" / "price_history.csv").exists()
    assert (tmp_path / "central_csv" / "account_performance_history.csv").exists()
    assert history.df.height == 1
    assert history.df["close"].item() == 100.5
    assert performance.height == 1
    assert performance["equity"].item() == 10_000.0


def test_central_storage_service_exposes_shared_storage_capabilities(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    service = CentralStorageService()

    assert Path("shared").exists()
    assert service.service_name == "central_storage"
    assert "shared_database_access" in service.get_capabilities()
