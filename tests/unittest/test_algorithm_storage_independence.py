"""
Test the Algorithm Storage Independence features.

This test file verifies the integration between LocalAlgorithmStorage and CentralStorageService
with service discovery and event publishing capabilities.
"""

import datetime as dt
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from harvest.storage._base import LocalAlgorithmStorage, CentralStorage
from harvest.services.central_storage_service import CentralStorageService
from harvest.services.discovery import ServiceRegistry
from harvest.events.event_bus import EventBus
from harvest.events.events import TransactionEvent, PriceUpdateEvent
from harvest.definitions import Transaction, TickerFrame, OrderSide, OrderEvent
from harvest.enum import Interval
import polars as pl


class TestAlgorithmStorageIndependence(unittest.TestCase):
    """Test the algorithm storage independence features."""

    def setUp(self):
        """Set up test fixtures."""
        self.service_registry = ServiceRegistry()
        self.event_bus = EventBus()
        self.temp_dir = tempfile.mkdtemp()

        # Create a sample transaction for testing
        self.sample_transaction = Transaction(
            timestamp=dt.datetime.utcnow(),
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=10.0,
            price=150.0,
            event=OrderEvent.FILL,
            algorithm_name="test_algo"
        )

        # Create sample price data for testing
        self.sample_price_data = TickerFrame(pl.DataFrame({
            "timestamp": [dt.datetime.utcnow()],
            "symbol": ["AAPL"],
            "interval": ["MIN_1"],
            "open": [150.0],
            "high": [152.0],
            "low": [149.0],
            "close": [151.0],
            "volume": [1000.0]
        }))

    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up temporary files
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

        # Clean up algorithm directories created during testing
        if os.path.exists("algorithms"):
            shutil.rmtree("algorithms", ignore_errors=True)
        if os.path.exists("shared"):
            shutil.rmtree("shared", ignore_errors=True)

    def test_local_algorithm_storage_default_path(self):
        """Test that LocalAlgorithmStorage uses correct default path."""
        storage = LocalAlgorithmStorage("test_algo")

        # Verify that the algorithms directory was created
        self.assertTrue(os.path.exists("algorithms"))

        # Verify the database path is correct
        expected_path = "sqlite:///algorithms/test_algo.db"
        self.assertEqual(str(storage.db_engine.url), expected_path)

    def test_local_algorithm_storage_service_registration(self):
        """Test that LocalAlgorithmStorage can register with service discovery."""
        storage = LocalAlgorithmStorage("test_algo")

        # Register with service discovery
        import asyncio
        asyncio.run(storage.register_with_discovery(self.service_registry))

        # Verify service was registered
        service = self.service_registry.discover_service("storage_test_algo")
        self.assertIsNotNone(service)
        self.assertEqual(service, storage)

        # Verify service information
        services = self.service_registry.list_services()
        self.assertIn("storage_test_algo", services)
        service_info = services["storage_test_algo"]
        self.assertEqual(service_info["metadata"]["type"], "algorithm_storage")
        self.assertEqual(service_info["metadata"]["algorithm"], "test_algo")

    def test_local_algorithm_storage_event_publishing(self):
        """Test that LocalAlgorithmStorage can publish transaction events."""
        storage = LocalAlgorithmStorage("test_algo")
        storage.event_bus = self.event_bus

        # Set up event listener
        events_received = []
        def event_listener(event):
            events_received.append(event)

        self.event_bus.subscribe("transaction", event_listener)

        # Publish a transaction event
        storage.publish_transaction_event(self.sample_transaction)

        # Verify event was published
        self.assertEqual(len(events_received), 1)
        event_data = events_received[0]
        self.assertIsInstance(event_data, dict)
        self.assertEqual(event_data["algorithm_name"], "test_algo")
        self.assertEqual(event_data["transaction"], self.sample_transaction)

    def test_local_algorithm_storage_no_event_bus(self):
        """Test that LocalAlgorithmStorage handles missing event bus gracefully."""
        storage = LocalAlgorithmStorage("test_algo")
        # Don't set event_bus

        # This should not raise an exception
        storage.publish_transaction_event(self.sample_transaction)

    def test_central_storage_service_creation(self):
        """Test that CentralStorageService creates shared directory."""
        service = CentralStorageService()

        # Verify that the shared directory was created
        self.assertTrue(os.path.exists("shared"))

        # Verify service name
        self.assertEqual(service.service_name, "central_storage")

    def test_central_storage_service_event_publishing(self):
        """Test that CentralStorageService publishes price update events."""
        service = CentralStorageService()
        service.set_event_bus(self.event_bus)

        # Set up event listener
        events_received = []
        def event_listener(event):
            events_received.append(event)

        self.event_bus.subscribe("price_update", event_listener)

        # Store price data (should trigger event)
        service.store_price_data(self.sample_price_data)

        # Verify event was published
        self.assertEqual(len(events_received), 1)
        event_data = events_received[0]
        self.assertIsInstance(event_data, dict)
        self.assertEqual(event_data["symbol"], "AAPL")
        self.assertEqual(event_data["price_data"], self.sample_price_data)

    def test_central_storage_service_no_event_bus(self):
        """Test that CentralStorageService handles missing event bus gracefully."""
        service = CentralStorageService()
        # Don't set event_bus

        # This should not raise an exception
        service.store_price_data(self.sample_price_data)

    def test_central_storage_service_capabilities(self):
        """Test CentralStorageService capabilities."""
        service = CentralStorageService()

        capabilities = service.get_capabilities()
        expected_capabilities = [
            "price_history_storage",
            "market_data_distribution",
            "account_performance_tracking",
            "shared_database_access"
        ]

        self.assertEqual(capabilities, expected_capabilities)

    def test_central_storage_service_health_check(self):
        """Test CentralStorageService health check."""
        service = CentralStorageService()

        # Start the service
        import asyncio
        asyncio.run(service.start())

        # Test health check
        health = service.health_check()
        self.assertEqual(health["status"], "healthy")
        self.assertTrue(health["database_accessible"])
        # Uptime can be None if service was never started, or a float if it was started
        self.assertIsNotNone(health["uptime"] if health["uptime"] is not None else 0)

    def test_integrated_storage_workflow(self):
        """Test integrated workflow between LocalAlgorithmStorage and CentralStorageService."""
        # Create algorithm storage and central service
        algo_storage = LocalAlgorithmStorage("test_algo")
        central_service = CentralStorageService()

        # Set up event bus
        algo_storage.event_bus = self.event_bus
        central_service.set_event_bus(self.event_bus)

        # Register services
        import asyncio
        asyncio.run(algo_storage.register_with_discovery(self.service_registry))
        asyncio.run(self.service_registry.register_service("central_storage", central_service))

        # Set up event listeners
        transaction_events = []
        price_events = []

        def transaction_listener(event):
            transaction_events.append(event)

        def price_listener(event):
            price_events.append(event)

        self.event_bus.subscribe("transaction", transaction_listener)
        self.event_bus.subscribe("price_update", price_listener)

        # Simulate algorithm activity
        algo_storage.publish_transaction_event(self.sample_transaction)
        central_service.store_price_data(self.sample_price_data)

        # Verify events were published
        self.assertEqual(len(transaction_events), 1)
        self.assertEqual(len(price_events), 1)

        # Verify service discovery works
        algo_service = self.service_registry.discover_service("storage_test_algo")
        self.assertEqual(algo_service, algo_storage)

        central_service_retrieved = self.service_registry.discover_service("central_storage")
        self.assertEqual(central_service_retrieved, central_service)

    def test_multiple_algorithms_independence(self):
        """Test that multiple algorithms have independent storage."""
        # Create multiple algorithm storages
        algo1_storage = LocalAlgorithmStorage("algo1")
        algo2_storage = LocalAlgorithmStorage("algo2")

        # Register both with service discovery
        import asyncio
        asyncio.run(algo1_storage.register_with_discovery(self.service_registry))
        asyncio.run(algo2_storage.register_with_discovery(self.service_registry))

        # Verify they are registered independently
        service1 = self.service_registry.discover_service("storage_algo1")
        service2 = self.service_registry.discover_service("storage_algo2")

        self.assertEqual(service1, algo1_storage)
        self.assertEqual(service2, algo2_storage)
        self.assertNotEqual(service1, service2)

        # Verify metadata is different
        services = self.service_registry.list_services()
        self.assertIn("storage_algo1", services)
        self.assertIn("storage_algo2", services)

        metadata1 = services["storage_algo1"]["metadata"]
        metadata2 = services["storage_algo2"]["metadata"]

        self.assertEqual(metadata1["algorithm"], "algo1")
        self.assertEqual(metadata2["algorithm"], "algo2")

    def test_storage_service_stats(self):
        """Test CentralStorageService statistics."""
        service = CentralStorageService()

        stats = service.get_storage_stats()
        self.assertEqual(stats["service_name"], "central_storage")
        self.assertFalse(stats["is_running"])  # Not started yet
        self.assertTrue(stats["database_path"].startswith("sqlite:///"))
        self.assertIn("capabilities", stats)


if __name__ == '__main__':
    unittest.main()
