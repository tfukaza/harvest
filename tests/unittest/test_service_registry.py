"""
Unit tests for Service Discovery and Registry functionality.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

from harvest.services import ServiceRegistry, Service
from harvest.services.service_interface import ServiceError, ServiceNotFoundError


class MockService(Service):
    """Mock service for testing."""

    def __init__(self, name="mock_service"):
        super().__init__(name)
        self.start_called = False
        self.stop_called = False
        self.should_fail_health_check = False

    async def start(self):
        self.start_called = True
        self.is_running = True

    async def stop(self):
        self.stop_called = True
        self.is_running = False

    def health_check(self):
        if self.should_fail_health_check:
            raise Exception("Mock health check failure")
        return {"status": "healthy" if self.is_running else "stopped"}

    def get_capabilities(self):
        return ["mock_capability"]


class TestServiceRegistry:
    """Test cases for ServiceRegistry functionality."""

    async def test_service_registration(self):
        """Test service registration."""
        registry = ServiceRegistry()
        service = MockService()

        await registry.register_service("test_service", service)

        # Check service is registered
        assert registry.get_service_count() == 1
        discovered = registry.discover_service("test_service")
        assert discovered == service

    async def test_service_registration_with_metadata(self):
        """Test service registration with metadata."""
        registry = ServiceRegistry()
        service = MockService()
        metadata = {"version": "1.0.0", "description": "Test service"}

        await registry.register_service("test_service", service, metadata)

        # Check service is registered with metadata
        services = registry.list_services()
        assert "test_service" in services
        assert services["test_service"]["metadata"] == metadata

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

    async def test_service_discovery_by_nonexistent_capability(self):
        """Test service discovery by non-existent capability."""
        registry = ServiceRegistry()
        service = MockService()

        await registry.register_service("test_service", service)

        # Discover by non-existent capability
        services = registry.discover_services_by_capability("nonexistent_capability")
        assert len(services) == 0

    async def test_service_not_found(self):
        """Test service not found error."""
        registry = ServiceRegistry()

        with pytest.raises(ServiceNotFoundError):
            await registry.start_service("nonexistent_service")

        with pytest.raises(ServiceNotFoundError):
            await registry.stop_service("nonexistent_service")

    async def test_health_check_all(self):
        """Test health check for all services."""
        registry = ServiceRegistry()
        service1 = MockService("service1")
        service2 = MockService("service2")

        await registry.register_service("service1", service1)
        await registry.register_service("service2", service2)
        await registry.start_service("service1")
        await registry.start_service("service2")

        # Check health
        health_results = await registry.health_check_all()
        assert "service1" in health_results
        assert "service2" in health_results
        assert health_results["service1"]["status"] == "healthy"
        assert health_results["service2"]["status"] == "healthy"

    async def test_health_check_failure(self):
        """Test health check failure handling."""
        registry = ServiceRegistry()
        service = MockService()
        service.should_fail_health_check = True

        await registry.register_service("test_service", service)
        await registry.start_service("test_service")

        # Health check should handle failure gracefully
        health_results = await registry.health_check_all()
        assert "test_service" in health_results
        assert health_results["test_service"]["status"] == "error"

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

    async def test_unregister_running_service(self):
        """Test unregistering a running service."""
        registry = ServiceRegistry()
        service = MockService()

        await registry.register_service("test_service", service)
        await registry.start_service("test_service")

        # Unregister running service
        await registry.unregister_service("test_service")
        assert service.stop_called
        assert not service.is_running
        assert registry.get_service_count() == 0

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

    async def test_stop_all_services(self):
        """Test stopping all registered services."""
        registry = ServiceRegistry()
        service1 = MockService("service1")
        service2 = MockService("service2")

        await registry.register_service("service1", service1)
        await registry.register_service("service2", service2)
        await registry.start_all_services()

        # Stop all
        await registry.stop_all_services()

        assert service1.stop_called
        assert service2.stop_called
        assert registry.get_running_service_count() == 0

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

    async def test_already_running_service_start(self):
        """Test starting a service that's already running."""
        registry = ServiceRegistry()
        service = MockService()

        await registry.register_service("test_service", service)
        await registry.start_service("test_service")

        # Try to start again - should not raise error
        await registry.start_service("test_service")
        assert service.is_running

    async def test_already_stopped_service_stop(self):
        """Test stopping a service that's already stopped."""
        registry = ServiceRegistry()
        service = MockService()

        await registry.register_service("test_service", service)

        # Try to stop without starting - should not raise error
        await registry.stop_service("test_service")
        assert not service.is_running

    def test_set_health_check_interval(self):
        """Test setting health check interval."""
        registry = ServiceRegistry()

        # Default interval should be 30 seconds
        assert registry._health_check_interval == 30.0

        # Set new interval
        registry.set_health_check_interval(60.0)
        assert registry._health_check_interval == 60.0


class TestService:
    """Test cases for Service base class functionality."""

    async def test_service_metadata(self):
        """Test service metadata functionality."""
        service = MockService("test_service")

        # Test initial metadata
        metadata = service.get_metadata()
        assert metadata["service_name"] == "test_service"
        assert metadata["is_running"] is False
        assert metadata["dependencies"] == []

        # Test setting metadata
        service.set_metadata("version", "1.0.0")
        metadata = service.get_metadata()
        assert metadata["version"] == "1.0.0"

    async def test_service_dependencies(self):
        """Test service dependency management."""
        service = MockService("test_service")

        # Add dependencies
        service.add_dependency("data_service")
        service.add_dependency("trading_service")

        # Check dependencies
        metadata = service.get_metadata()
        assert "data_service" in metadata["dependencies"]
        assert "trading_service" in metadata["dependencies"]

        # Adding same dependency again should not duplicate
        service.add_dependency("data_service")
        assert len(metadata["dependencies"]) == 2

    async def test_service_uptime(self):
        """Test service uptime tracking."""
        service = MockService("test_service")

        # Before starting, uptime should be None
        assert service.get_uptime() is None

        # Start service
        await service._internal_start()

        # After starting, uptime should be a positive number
        await asyncio.sleep(0.01)  # Small delay
        uptime = service.get_uptime()
        assert uptime is not None
        assert uptime > 0

        # Stop service
        await service._internal_stop()

        # After stopping, uptime should be None again
        assert service.get_uptime() is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
