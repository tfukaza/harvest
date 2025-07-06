"""
Unit tests for the Algorithm Independence Infrastructure.
"""

import asyncio
import pytest
import datetime as dt
from unittest.mock import Mock, AsyncMock

from harvest.events import EventBus, EventTypes
from harvest.events.events import PriceUpdateEvent, OrderPlacedEvent, LogEvent
from harvest.services import ServiceRegistry, Service
from harvest.services.service_interface import ServiceError, ServiceNotFoundError
from harvest.definitions import OrderSide


class TestEventBus:
    """Test cases for EventBus functionality."""

    def test_event_bus_creation(self):
        """Test EventBus can be created."""
        event_bus = EventBus()
        assert event_bus._event_handlers == {}
        assert event_bus.get_subscription_count() == 0

    def test_subscribe_and_publish(self):
        """Test basic subscribe and publish functionality."""
        event_bus = EventBus()
        received_events = []

        def handler(data):
            received_events.append(data)

        # Subscribe
        sub_id = event_bus.subscribe("test_event", handler)
        assert isinstance(sub_id, str)
        assert event_bus.get_subscription_count() == 1

        # Publish
        test_data = {"message": "test"}
        event_bus.publish("test_event", test_data)

        # Verify
        assert len(received_events) == 1
        assert received_events[0] == test_data

    def test_unsubscribe(self):
        """Test unsubscribe functionality."""
        event_bus = EventBus()
        received_events = []

        def handler(data):
            received_events.append(data)

        # Subscribe and publish
        sub_id = event_bus.subscribe("test_event", handler)
        event_bus.publish("test_event", {"message": "first"})

        # Unsubscribe
        event_bus.unsubscribe(sub_id)
        assert event_bus.get_subscription_count() == 0

        # Publish again
        event_bus.publish("test_event", {"message": "second"})

        # Should only have first event
        assert len(received_events) == 1
        assert received_events[0]["message"] == "first"

    def test_multiple_subscribers(self):
        """Test multiple subscribers to same event."""
        event_bus = EventBus()
        received_events_1 = []
        received_events_2 = []

        def handler_1(data):
            received_events_1.append(data)

        def handler_2(data):
            received_events_2.append(data)

        # Subscribe multiple handlers
        event_bus.subscribe("test_event", handler_1)
        event_bus.subscribe("test_event", handler_2)

        # Publish
        test_data = {"message": "broadcast"}
        event_bus.publish("test_event", test_data)

        # Both should receive
        assert len(received_events_1) == 1
        assert len(received_events_2) == 1
        assert received_events_1[0] == test_data
        assert received_events_2[0] == test_data

    def test_event_filtering(self):
        """Test event filtering functionality."""
        event_bus = EventBus()
        received_events = []

        def handler(data):
            received_events.append(data)

        # Subscribe with filter
        filters = {"symbol": "AAPL"}
        event_bus.subscribe("price_update", handler, filters)

        # Publish matching event
        event_bus.publish("price_update", {"symbol": "AAPL", "price": 150.0})

        # Publish non-matching event
        event_bus.publish("price_update", {"symbol": "GOOGL", "price": 2500.0})

        # Should only receive matching event
        assert len(received_events) == 1
        assert received_events[0]["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_async_publish(self):
        """Test asynchronous event publishing."""
        event_bus = EventBus()
        received_events = []

        async def async_handler(data):
            await asyncio.sleep(0.01)  # Simulate async work
            received_events.append(data)

        # Subscribe async handler
        event_bus.subscribe("async_event", async_handler)

        # Publish async
        await event_bus.publish_async("async_event", {"message": "async"})

        # Verify
        assert len(received_events) == 1
        assert received_events[0]["message"] == "async"

    def test_clear_all_subscriptions(self):
        """Test clearing all subscriptions."""
        event_bus = EventBus()

        def handler(data):
            pass

        # Add multiple subscriptions
        event_bus.subscribe("event1", handler)
        event_bus.subscribe("event2", handler)

        assert event_bus.get_subscription_count() == 2

        # Clear all
        event_bus.clear_all_subscriptions()
        assert event_bus.get_subscription_count() == 0


class MockService(Service):
    """Mock service for testing."""

    def __init__(self, name="mock_service"):
        super().__init__(name)
        self.start_called = False
        self.stop_called = False

    async def start(self):
        self.start_called = True
        self.is_running = True

    async def stop(self):
        self.stop_called = True
        self.is_running = False

    def health_check(self):
        return {"status": "healthy" if self.is_running else "stopped"}

    def get_capabilities(self):
        return ["mock_capability"]


class TestServiceRegistry:
    """Test cases for ServiceRegistry functionality."""

    @pytest.mark.asyncio
    async def test_service_registration(self):
        """Test service registration."""
        registry = ServiceRegistry()
        service = MockService()

        await registry.register_service("test_service", service)

        # Check service is registered
        assert registry.get_service_count() == 1
        discovered = registry.discover_service("test_service")
        assert discovered == service

    @pytest.mark.asyncio
    async def test_service_start_stop(self):
        """Test service start and stop."""
        registry = ServiceRegistry()
        service = MockService()

        await registry.register_service("test_service", service)

        # Start service
        await registry.start_service("test_service")
        assert service.start_called
        assert service.is_running
        assert registry.get_running_service_count() == 1

        # Stop service
        await registry.stop_service("test_service")
        assert service.stop_called
        assert not service.is_running
        assert registry.get_running_service_count() == 0

    @pytest.mark.asyncio
    async def test_service_discovery_by_capability(self):
        """Test service discovery by capability."""
        registry = ServiceRegistry()
        service1 = MockService("service1")
        service2 = MockService("service2")

        await registry.register_service("service1", service1)
        await registry.register_service("service2", service2)

        # Discover by capability
        services = registry.discover_services_by_capability("mock_capability")
        assert len(services) == 2
        assert service1 in services
        assert service2 in services

    @pytest.mark.asyncio
    async def test_service_not_found(self):
        """Test service not found error."""
        registry = ServiceRegistry()

        with pytest.raises(ServiceNotFoundError):
            await registry.start_service("nonexistent_service")

    @pytest.mark.asyncio
    async def test_health_check_all(self):
        """Test health check for all services."""
        registry = ServiceRegistry()
        service = MockService()

        await registry.register_service("test_service", service)
        await registry.start_service("test_service")

        # Check health
        health_results = await registry.health_check_all()
        assert "test_service" in health_results
        assert health_results["test_service"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_service_unregistration(self):
        """Test service unregistration."""
        registry = ServiceRegistry()
        service = MockService()

        await registry.register_service("test_service", service)
        assert registry.get_service_count() == 1

        # Unregister
        await registry.unregister_service("test_service")
        assert registry.get_service_count() == 0

        # Should not be discoverable
        discovered = registry.discover_service("test_service")
        assert discovered is None

    @pytest.mark.asyncio
    async def test_start_all_services(self):
        """Test starting all registered services."""
        registry = ServiceRegistry()
        service1 = MockService("service1")
        service2 = MockService("service2")

        await registry.register_service("service1", service1)
        await registry.register_service("service2", service2)

        # Start all
        await registry.start_all_services()

        assert service1.start_called
        assert service2.start_called
        assert registry.get_running_service_count() == 2

    @pytest.mark.asyncio
    async def test_shutdown(self):
        """Test registry shutdown."""
        registry = ServiceRegistry()
        service = MockService()

        await registry.register_service("test_service", service)
        await registry.start_service("test_service")

        # Shutdown
        await registry.shutdown()

        assert service.stop_called
        assert registry.get_service_count() == 0


class TestEvents:
    """Test cases for event classes."""

    def test_price_update_event(self):
        """Test PriceUpdateEvent creation."""
        event = PriceUpdateEvent(
            symbol="AAPL",
            price_data=Mock(),
            timestamp=dt.datetime.now()
        )

        assert event.symbol == "AAPL"
        assert event.price_data is not None
        assert isinstance(event.timestamp, dt.datetime)

    def test_order_placed_event(self):
        """Test OrderPlacedEvent creation."""
        event = OrderPlacedEvent(
            order_id="123",
            algorithm_name="test_algo",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
            order_type="market",
            timestamp=dt.datetime.now()
        )

        assert event.order_id == "123"
        assert event.algorithm_name == "test_algo"
        assert event.symbol == "AAPL"
        assert event.quantity == 100.0

    def test_log_event(self):
        """Test LogEvent creation."""
        event = LogEvent(
            level="INFO",
            message="Test message",
            component="test",
            timestamp=dt.datetime.now()
        )

        assert event.level == "INFO"
        assert event.message == "Test message"
        assert event.component == "test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
