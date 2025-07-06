import asyncio
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

from .service_interface import Service, ServiceError, ServiceNotFoundError

logger = logging.getLogger(__name__)


class ServiceRegistry:
    """
    Service registry for managing and discovering services in the system.
    Supports service registration, discovery, health monitoring, and dependency management.
    """

    def __init__(self):
        self._services: Dict[str, Dict[str, Any]] = {}
        self._health_check_interval: float = 30.0  # seconds
        self._health_check_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def register_service(
        self,
        service_name: str,
        service_instance: Service,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Register a service with the registry.

        Args:
            service_name: Unique name for the service
            service_instance: The service instance
            metadata: Optional metadata for the service
        """
        async with self._lock:
            if service_name in self._services:
                logger.warning(f"Service {service_name} already registered, updating...")

            service_data = {
                "instance": service_instance,
                "metadata": metadata or {},
                "registration_time": datetime.now(),
                "last_health_check": None,
                "health_status": "unknown",
                "health_details": {},
                "capabilities": service_instance.get_capabilities()
            }

            self._services[service_name] = service_data
            logger.info(f"Service {service_name} registered successfully")

            # Start health monitoring if this is the first service
            if len(self._services) == 1 and self._health_check_task is None:
                self._health_check_task = asyncio.create_task(self._health_monitor())

    async def unregister_service(self, service_name: str) -> None:
        """
        Unregister a service from the registry.

        Args:
            service_name: Name of the service to unregister
        """
        async with self._lock:
            if service_name not in self._services:
                raise ServiceNotFoundError(f"Service {service_name} not found")

            service_data = self._services[service_name]
            service_instance = service_data["instance"]

            # Stop the service if it's running
            if service_instance.is_running:
                try:
                    await service_instance._internal_stop()
                except Exception as e:
                    logger.error(f"Error stopping service {service_name}: {e}")

            del self._services[service_name]
            logger.info(f"Service {service_name} unregistered")

            # Stop health monitoring if no services remain
            if len(self._services) == 0 and self._health_check_task:
                self._health_check_task.cancel()
                self._health_check_task = None

    def discover_service(self, service_name: str) -> Optional[Service]:
        """
        Discover a service by name.

        Args:
            service_name: Name of the service to discover

        Returns:
            Service instance or None if not found
        """
        service_data = self._services.get(service_name)
        if service_data:
            return service_data["instance"]
        return None

    def discover_services_by_capability(self, capability: str) -> List[Service]:
        """
        Discover services that provide a specific capability.

        Args:
            capability: Capability to search for

        Returns:
            List of service instances that provide the capability
        """
        matching_services = []
        for service_data in self._services.values():
            if capability in service_data["capabilities"]:
                matching_services.append(service_data["instance"])
        return matching_services

    def list_services(self) -> Dict[str, Dict[str, Any]]:
        """
        List all registered services with their metadata.

        Returns:
            Dict mapping service names to service information
        """
        service_info = {}
        for name, data in self._services.items():
            service_info[name] = {
                "name": name,
                "is_running": data["instance"].is_running,
                "capabilities": data["capabilities"],
                "metadata": data["metadata"],
                "registration_time": data["registration_time"],
                "last_health_check": data["last_health_check"],
                "health_status": data["health_status"],
                "health_details": data["health_details"]
            }
        return service_info

    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Perform health checks on all registered services.

        Returns:
            Dict mapping service names to health check results
        """
        health_results = {}

        for name, data in self._services.items():
            service_instance = data["instance"]
            try:
                health_result = service_instance.health_check()
                health_status = "healthy" if health_result.get("status") == "healthy" else "unhealthy"

                # Update stored health data
                data["last_health_check"] = datetime.now()
                data["health_status"] = health_status
                data["health_details"] = health_result

                health_results[name] = {
                    "status": health_status,
                    "details": health_result,
                    "timestamp": data["last_health_check"]
                }

            except Exception as e:
                logger.error(f"Health check failed for service {name}: {e}")
                data["health_status"] = "error"
                data["health_details"] = {"error": str(e)}
                health_results[name] = {
                    "status": "error",
                    "details": {"error": str(e)},
                    "timestamp": datetime.now()
                }

        return health_results

    async def start_service(self, service_name: str) -> None:
        """
        Start a registered service.

        Args:
            service_name: Name of the service to start
        """
        service_data = self._services.get(service_name)
        if not service_data:
            raise ServiceNotFoundError(f"Service {service_name} not found")

        service_instance = service_data["instance"]
        if service_instance.is_running:
            logger.warning(f"Service {service_name} is already running")
            return

        try:
            await service_instance._internal_start()
        except Exception as e:
            logger.error(f"Failed to start service {service_name}: {e}")
            raise ServiceError(f"Failed to start service {service_name}: {e}")

    async def stop_service(self, service_name: str) -> None:
        """
        Stop a registered service.

        Args:
            service_name: Name of the service to stop
        """
        service_data = self._services.get(service_name)
        if not service_data:
            raise ServiceNotFoundError(f"Service {service_name} not found")

        service_instance = service_data["instance"]
        if not service_instance.is_running:
            logger.warning(f"Service {service_name} is not running")
            return

        try:
            await service_instance._internal_stop()
        except Exception as e:
            logger.error(f"Failed to stop service {service_name}: {e}")
            raise ServiceError(f"Failed to stop service {service_name}: {e}")

    async def start_all_services(self) -> None:
        """Start all registered services."""
        for service_name in self._services:
            try:
                await self.start_service(service_name)
            except Exception as e:
                logger.error(f"Failed to start service {service_name}: {e}")

    async def stop_all_services(self) -> None:
        """Stop all registered services."""
        for service_name in self._services:
            try:
                await self.stop_service(service_name)
            except Exception as e:
                logger.error(f"Failed to stop service {service_name}: {e}")

    def get_service_count(self) -> int:
        """Get the number of registered services."""
        return len(self._services)

    def get_running_service_count(self) -> int:
        """Get the number of running services."""
        return sum(1 for data in self._services.values() if data["instance"].is_running)

    def set_health_check_interval(self, interval: float) -> None:
        """
        Set the health check interval.

        Args:
            interval: Interval in seconds
        """
        self._health_check_interval = interval
        logger.info(f"Health check interval set to {interval} seconds")

    async def _health_monitor(self) -> None:
        """Background task for periodic health checks."""
        while True:
            try:
                await asyncio.sleep(self._health_check_interval)
                if self._services:  # Only check if we have services
                    await self.health_check_all()
            except asyncio.CancelledError:
                logger.info("Health monitor cancelled")
                break
            except Exception as e:
                logger.error(f"Error in health monitor: {e}")

    async def shutdown(self) -> None:
        """Shutdown the service registry."""
        logger.info("Shutting down service registry...")

        # Cancel health monitoring
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        # Stop all services
        await self.stop_all_services()

        # Clear service registry
        self._services.clear()

        logger.info("Service registry shutdown complete")


# Global service registry instance
_global_registry: Optional[ServiceRegistry] = None


def get_service_registry() -> ServiceRegistry:
    """Get the global service registry instance."""
    global _global_registry
    if _global_registry is None:
        _global_registry = ServiceRegistry()
    return _global_registry


async def register_service(
    service_name: str,
    service_instance: Service,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """Convenience function to register a service with the global registry."""
    registry = get_service_registry()
    await registry.register_service(service_name, service_instance, metadata)


def discover_service(service_name: str) -> Optional[Service]:
    """Convenience function to discover a service from the global registry."""
    registry = get_service_registry()
    return registry.discover_service(service_name)
