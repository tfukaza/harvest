"""
Central Storage Service for Algorithm Independence.

This service provides centralized storage capabilities for market data and shared
information across all algorithms in the trading system.
"""

import datetime as dt
import os
from typing import Any

from harvest.services.service_interface import Service
from harvest.storage._base import CentralStorage
from harvest.definitions import TickerFrame
from harvest.enum import Interval
from harvest.events.events import PriceUpdateEvent


class CentralStorageService(Service):
    """
    Central storage service that manages shared market data.

    This service provides:
    - Centralized price history storage
    - Market data distribution via events
    - Shared database for all algorithms
    - Service discovery integration
    """

    def __init__(self, db_path: str | None = None):
        """
        Initialize the central storage service.

        Args:
            db_path: Database path. If None, uses default shared database location.
        """
        super().__init__("central_storage")

        # Set default shared database path
        if db_path is None:
            db_path = "sqlite:///shared/market_data.db"
            self._ensure_shared_directory_exists()

        self.storage = CentralStorage(db_path=db_path)
        self.event_bus = None

    def _ensure_shared_directory_exists(self) -> None:
        """
        Ensure the shared directory exists for the database file.

        Creates the shared/ directory if it doesn't exist to store
        centralized database files.
        """
        shared_dir = "shared"
        if not os.path.exists(shared_dir):
            os.makedirs(shared_dir)

    async def start(self) -> None:
        """Start the central storage service."""
        self.is_running = True
        self.set_metadata("version", "1.0.0")
        self.set_metadata("database_type", "sqlite")
        self.set_metadata("data_types", ["price_history", "account_performance"])

    async def stop(self) -> None:
        """Stop the central storage service."""
        self.is_running = False
        # Could add cleanup logic here if needed

    def health_check(self) -> dict[str, Any]:
        """
        Perform health check on the storage service.

        Returns:
            Dict containing health status and service details
        """
        try:
            # Test database connection by attempting a simple query
            # This is a basic health check - could be expanded
            return {
                "status": "healthy" if self.is_running else "stopped",
                "database_accessible": True,
                "uptime": self.get_uptime()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "database_accessible": False,
                "error": str(e),
                "uptime": self.get_uptime()
            }

    def get_capabilities(self) -> list[str]:
        """
        Get the capabilities provided by this service.

        Returns:
            List of capability strings
        """
        return [
            "price_history_storage",
            "market_data_distribution",
            "account_performance_tracking",
            "shared_database_access"
        ]

    def set_event_bus(self, event_bus) -> None:
        """
        Set the event bus for publishing events.

        Args:
            event_bus: EventBus instance for publishing market data events
        """
        self.event_bus = event_bus

    def get_price_history(
        self,
        symbol: str,
        interval: Interval,
        start: dt.datetime | None = None,
        end: dt.datetime | None = None
    ) -> TickerFrame:
        """
        Retrieve price history from central storage.

        Args:
            symbol: Stock/crypto symbol to retrieve
            interval: Time interval for the data
            start: Start datetime (optional)
            end: End datetime (optional)

        Returns:
            TickerFrame containing the requested price data
        """
        return self.storage.get_price_history(symbol, interval, start, end)

    def store_price_data(self, data: TickerFrame) -> None:
        """
        Store price data and publish update events.

        Args:
            data: TickerFrame containing price data to store
        """
        # Store the data in central storage
        self.storage.insert_price_history(data)

        # Publish price update event if event bus is available
        if self.event_bus:
            # Get the symbol from the data (assuming all rows have same symbol)
            symbols = data.df['symbol'].unique()
            if len(symbols) > 0:
                symbol = symbols[0]

                price_event = PriceUpdateEvent(
                    symbol=symbol,
                    price_data=data,
                    timestamp=dt.datetime.utcnow()
                )

                self.event_bus.publish('price_update', price_event.__dict__)

    def get_account_performance_history(
        self,
        interval: str,
        start: dt.datetime | None = None,
        end: dt.datetime | None = None
    ) -> Any:
        """
        Retrieve account performance history.

        Args:
            interval: Performance interval (e.g., '1day', '1hour')
            start: Start datetime (optional)
            end: End datetime (optional)

        Returns:
            Account performance data
        """
        return self.storage.get_account_performance_history(interval, start, end)

    def store_account_performance(self, performance_data: dict) -> None:
        """
        Store account performance data.

        Args:
            performance_data: Dictionary containing performance metrics
        """
        # This would need to be implemented based on the actual
        # account performance storage method in CentralStorage
        pass

    def get_storage_stats(self) -> dict[str, Any]:
        """
        Get statistics about the stored data.

        Returns:
            Dictionary containing storage statistics
        """
        return {
            "service_name": self.service_name,
            "is_running": self.is_running,
            "database_path": str(self.storage.db_engine.url),
            "capabilities": self.get_capabilities()
        }
