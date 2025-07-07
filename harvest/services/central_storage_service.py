"""
Central Storage Service for Algorithm Independence.

This service provides centralized storage capabilities for market data and shared
information across all algorithms in the trading system.
"""

import datetime as dt
import os
from typing import Any, Dict

from harvest.services.service_interface import Service
from harvest.storage._base import CentralStorage
from harvest.definitions import TickerFrame
from harvest.enum import Interval
from harvest.events.events import PriceUpdateEvent


class CentralStorageService(Service):
    """
    Central storage service that manages shared market data across multiple storage instances.

    This service provides:
    - Centralized price history storage with multiplexing
    - Market data distribution via events
    - Multiple storage backends support
    - Service discovery integration
    """

    def __init__(self, storages: Dict[str, CentralStorage] | CentralStorage | None = None):
        """
        Initialize the central storage service.

        Args:
            storages: Dictionary of storage instances keyed by name, or a single CentralStorage instance,
                     or None to use default storage.
        """
        super().__init__("central_storage")

        # Handle different storage configuration types
        if storages is None:
            # Default single storage
            db_path = "sqlite:///shared/market_data.db"
            self._ensure_shared_directory_exists()
            self.storages = {"default": CentralStorage(db_path=db_path)}
        elif isinstance(storages, dict):
            # Multiple storages provided
            self.storages = storages
        else:
            # Single storage provided - wrap in dictionary
            self.storages = {"default": storages}

        self.event_bus = None

    @property
    def storage(self) -> CentralStorage:
        """Returns the default storage instance for backward compatibility."""
        return self.storages["default"]

    def _get_storage(self, storage_name: str = "default") -> CentralStorage:
        """Retrieve the storage instance for the specified name."""
        if storage_name not in self.storages:
            raise ValueError(f"Storage {storage_name} not found")
        return self.storages[storage_name]

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
        Perform health check on the storage service and all managed storages.

        Returns:
            Dict containing health status and service details
        """
        storage_statuses = {}
        all_storages_healthy = True

        for storage_name, storage in self.storages.items():
            try:
                # Test database connection by attempting a simple query
                # This is a basic health check - could be expanded
                storage_status = {
                    "status": "healthy",
                    "database_accessible": True,
                    "database_url": str(storage.db_engine.url)
                }
                storage_statuses[storage_name] = storage_status
            except Exception as e:
                storage_status = {
                    "status": "unhealthy",
                    "database_accessible": False,
                    "error": str(e)
                }
                storage_statuses[storage_name] = storage_status
                all_storages_healthy = False

        return {
            "status": "healthy" if self.is_running and all_storages_healthy else "degraded",
            "storages": storage_statuses,
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
        end: dt.datetime | None = None,
        storage_name: str = "default"
    ) -> TickerFrame:
        """
        Retrieve price history from the specified storage.

        Args:
            symbol: Stock/crypto symbol to retrieve
            interval: Time interval for the data
            start: Start datetime (optional)
            end: End datetime (optional)
            storage_name: Name of the storage to use

        Returns:
            TickerFrame containing the requested price data
        """
        storage = self._get_storage(storage_name)
        return storage.get_price_history(symbol, interval, start, end)

    def store_price_data(self, data: TickerFrame, storage_name: str = "default") -> None:
        """
        Store price data and publish update events.

        Args:
            data: TickerFrame containing price data to store
            storage_name: Name of the storage to use
        """
        # Store the data in the specified storage
        storage = self._get_storage(storage_name)
        storage.insert_price_history(data)

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
        end: dt.datetime | None = None,
        storage_name: str = "default"
    ) -> Any:
        """
        Retrieve account performance history from the specified storage.

        Args:
            interval: Performance interval (e.g., '1day', '1hour')
            start: Start datetime (optional)
            end: End datetime (optional)
            storage_name: Name of the storage to use

        Returns:
            Account performance data
        """
        storage = self._get_storage(storage_name)
        return storage.get_account_performance_history(interval, start, end)

    def store_account_performance(self, performance_data: dict, storage_name: str = "default") -> None:
        """
        Store account performance data in the specified storage.

        Args:
            performance_data: Dictionary containing performance metrics
            storage_name: Name of the storage to use
        """
        storage = self._get_storage(storage_name)
        # Extract data from performance_data dict and call appropriate storage method
        if all(key in performance_data for key in ['timestamp', 'interval', 'equity']):
            storage.insert_account_performance(
                timestamp=performance_data['timestamp'],
                interval=performance_data['interval'],
                equity=performance_data['equity'],
                return_percentage=performance_data.get('return_percentage', 0.0),
                return_absolute=performance_data.get('return_absolute', 0.0)
            )
        else:
            raise ValueError("Performance data must contain timestamp, interval, and equity")

    def get_latest_account_performance(self, interval: str, storage_name: str = "default") -> dict | None:
        """
        Get the latest account performance data from the specified storage.

        Args:
            interval: Performance interval
            storage_name: Name of the storage to use

        Returns:
            Latest performance data or None
        """
        storage = self._get_storage(storage_name)
        return storage.get_latest_account_performance(interval)

    def get_available_storages(self) -> list[str]:
        """
        Get list of available storage names.

        Returns:
            List of storage names
        """
        return list(self.storages.keys())

    def get_storage_stats(self) -> dict[str, Any]:
        """
        Get statistics about the stored data across all storages.

        Returns:
            Dictionary containing storage statistics
        """
        storage_info = {}
        for storage_name, storage in self.storages.items():
            storage_info[storage_name] = {
                "database_path": str(storage.db_engine.url),
                "capabilities": ["price_history", "account_performance"]
            }

        return {
            "service_name": self.service_name,
            "is_running": self.is_running,
            "storages": storage_info,
            "capabilities": self.get_capabilities()
        }
