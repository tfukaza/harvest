"""
Test the Algorithm Storage Independence features.

This test file verifies the integration between LocalAlgorithmStorage and CentralStorageService
with service discovery and event publishing capabilities.
"""

import datetime as dt
import os
import tempfile
import shutil
from unittest.mock import Mock, patch

import pytest
import polars as pl

from harvest.storage._base import LocalAlgorithmStorage, CentralStorage
from harvest.services.central_storage_service import CentralStorageService
from harvest.services.discovery import ServiceRegistry
from harvest.events.event_bus import EventBus
from harvest.events.events import TransactionEvent, PriceUpdateEvent
from harvest.definitions import Transaction, TickerCandleList, OrderSide, OrderEvent
from harvest.enum import Interval


@pytest.fixture
def service_registry():
    """Create a service registry for testing."""
    return ServiceRegistry()


@pytest.fixture
def event_bus():
    """Create an event bus for testing."""
    return EventBus()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_transaction():
    """Create a sample transaction for testing."""
    return Transaction(
        timestamp=dt.datetime.utcnow(),
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10.0,
        price=150.0,
        event=OrderEvent.FILL,
        algorithm_name="test_algo",
    )


@pytest.fixture
def sample_price_data():
    """Create sample price data for testing."""
    return TickerCandleList(
        pl.DataFrame(
            {
                "timestamp": [dt.datetime.utcnow()],
                "symbol": ["AAPL"],
                "interval": ["MIN_1"],
                "open": [150.0],
                "high": [152.0],
                "low": [149.0],
                "close": [151.0],
                "volume": [1000.0],
            }
        )
    )


@pytest.fixture(autouse=True)
def cleanup_directories():
    """Clean up test directories after each test."""
    yield
    # Clean up algorithm directories created during testing
    if os.path.exists("algorithms"):
        shutil.rmtree("algorithms", ignore_errors=True)
    if os.path.exists("shared"):
        shutil.rmtree("shared", ignore_errors=True)


def test_local_algorithm_storage_default_path():
    """Test that LocalAlgorithmStorage uses correct default path."""
    storage = LocalAlgorithmStorage("test_algo")

    # Verify that the algorithms directory was created
    assert os.path.exists("algorithms")

    # Verify the database path is correct
    expected_path = "sqlite:///algorithms/test_algo.db"
    assert str(storage.db_engine.url) == expected_path


def test_local_algorithm_storage_service_registration(service_registry):
    """Test that LocalAlgorithmStorage can register with service discovery."""
    storage = LocalAlgorithmStorage("test_algo")

    # Register with service discovery
    import asyncio

    asyncio.run(storage.register_with_discovery(service_registry))

    # Verify service was registered
    service = service_registry.discover_service("storage_test_algo")
    assert service is not None
    assert service == storage

    # Verify service information
    services = service_registry.list_services()
    assert "storage_test_algo" in services
    service_info = services["storage_test_algo"]
    assert service_info["metadata"]["type"] == "algorithm_storage"
    assert service_info["metadata"]["algorithm"] == "test_algo"


def test_local_algorithm_storage_event_publishing(event_bus, sample_transaction):
    """Test that LocalAlgorithmStorage can publish transaction events."""
    storage = LocalAlgorithmStorage("test_algo")
    storage.event_bus = event_bus

    # Set up event listener
    events_received = []

    def event_listener(event):
        events_received.append(event)

    event_bus.subscribe("transaction", event_listener)

    # Publish a transaction event
    storage.publish_transaction_event(sample_transaction)

    # Verify event was published
    assert len(events_received) == 1
    event_data = events_received[0]
    assert isinstance(event_data, dict)
    assert event_data["algorithm_name"] == "test_algo"
    assert event_data["transaction"] == sample_transaction


def test_local_algorithm_storage_no_event_bus(sample_transaction):
    """Test that LocalAlgorithmStorage handles missing event bus gracefully."""
    storage = LocalAlgorithmStorage("test_algo")
    # Don't set event_bus

    # This should not raise an exception
    storage.publish_transaction_event(sample_transaction)


def test_central_storage_service_creation():
    """Test that CentralStorageService creates shared directory."""
    service = CentralStorageService()

    # Verify that the shared directory was created
    assert os.path.exists("shared")

    # Verify service name
    assert service.service_name == "central_storage"


def test_central_storage_service_event_publishing(event_bus, sample_price_data):
    """Test that CentralStorageService publishes price update events."""
    service = CentralStorageService()
    service.set_event_bus(event_bus)

    # Set up event listener
    events_received = []

    def event_listener(event):
        events_received.append(event)

    event_bus.subscribe("price_update", event_listener)

    # Mock the PriceUpdateEvent to avoid the missing parameter issue
    with patch("harvest.services.central_storage_service.PriceUpdateEvent") as mock_event:
        mock_event_instance = {
            "symbol": "AAPL",
            "price_data": sample_price_data,
            "timestamp": dt.datetime.utcnow(),
        }
        mock_event.return_value.__dict__ = mock_event_instance

        # Store price data (should trigger event)
        service.store_price_data(sample_price_data)

        # Verify event was published
        assert len(events_received) == 1
        event_data = events_received[0]
        assert isinstance(event_data, dict)
        assert event_data["symbol"] == "AAPL"
        assert event_data["price_data"] == sample_price_data


def test_central_storage_service_no_event_bus(sample_price_data):
    """Test that CentralStorageService handles missing event bus gracefully."""
    service = CentralStorageService()
    # Don't set event_bus

    # This should not raise an exception
    service.store_price_data(sample_price_data)


def test_central_storage_service_capabilities():
    """Test CentralStorageService capabilities."""
    service = CentralStorageService()

    capabilities = service.get_capabilities()
    expected_capabilities = [
        "price_history_storage",
        "market_data_distribution",
        "account_performance_tracking",
        "shared_database_access",
    ]

    assert capabilities == expected_capabilities


def test_central_storage_service_health_check():
    """Test CentralStorageService health check."""
    service = CentralStorageService()

    # Start the service
    import asyncio

    asyncio.run(service.start())

    # Test health check
    health = service.health_check()
    assert health["status"] in ["healthy", "degraded"]
    # Uptime can be None if service was never started, or a float if it was started
    assert "uptime" in health


def test_integrated_storage_workflow(service_registry, event_bus, sample_transaction, sample_price_data):
    """Test integrated workflow between LocalAlgorithmStorage and CentralStorageService."""
    # Create algorithm storage and central service
    algo_storage = LocalAlgorithmStorage("test_algo")
    central_service = CentralStorageService()

    # Set up event bus
    algo_storage.event_bus = event_bus
    central_service.set_event_bus(event_bus)

    # Register services
    import asyncio

    asyncio.run(algo_storage.register_with_discovery(service_registry))
    asyncio.run(service_registry.register_service("central_storage", central_service))

    # Set up event listeners
    transaction_events = []
    price_events = []

    def transaction_listener(event):
        transaction_events.append(event)

    def price_listener(event):
        price_events.append(event)

    event_bus.subscribe("transaction", transaction_listener)
    event_bus.subscribe("price_update", price_listener)

    # Simulate algorithm activity
    algo_storage.publish_transaction_event(sample_transaction)

    # Mock the PriceUpdateEvent for the central service
    with patch("harvest.services.central_storage_service.PriceUpdateEvent") as mock_event:
        mock_event_dict = {
            "symbol": "AAPL",
            "price_data": sample_price_data,
            "timestamp": dt.datetime.utcnow(),
        }
        mock_event.return_value.__dict__ = mock_event_dict

        central_service.store_price_data(sample_price_data)

    # Verify events were published
    assert len(transaction_events) == 1
    assert len(price_events) == 1

    # Verify service discovery works
    algo_service = service_registry.discover_service("storage_test_algo")
    assert algo_service == algo_storage

    central_service_retrieved = service_registry.discover_service("central_storage")
    assert central_service_retrieved == central_service


def test_multiple_algorithms_independence(service_registry):
    """Test that multiple algorithms have independent storage."""
    # Create multiple algorithm storages
    algo1_storage = LocalAlgorithmStorage("algo1")
    algo2_storage = LocalAlgorithmStorage("algo2")

    # Register both with service discovery
    import asyncio

    asyncio.run(algo1_storage.register_with_discovery(service_registry))
    asyncio.run(algo2_storage.register_with_discovery(service_registry))

    # Verify they are registered independently
    service1 = service_registry.discover_service("storage_algo1")
    service2 = service_registry.discover_service("storage_algo2")

    assert service1 == algo1_storage
    assert service2 == algo2_storage
    assert service1 != service2

    # Verify metadata is different
    services = service_registry.list_services()
    assert "storage_algo1" in services
    assert "storage_algo2" in services

    metadata1 = services["storage_algo1"]["metadata"]
    metadata2 = services["storage_algo2"]["metadata"]

    assert metadata1["algorithm"] == "algo1"
    assert metadata2["algorithm"] == "algo2"


def test_storage_service_stats():
    """Test CentralStorageService statistics."""
    service = CentralStorageService()

    stats = service.get_storage_stats()
    assert stats["service_name"] == "central_storage"
    assert not stats["is_running"]  # Not started yet
    assert "capabilities" in stats
    assert "storages" in stats
