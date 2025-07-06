import asyncio
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class Service(ABC):
    """
    Base class for all services in the system.
    Provides common functionality for service lifecycle management.
    """

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.is_running = False
        self._start_time: Optional[float] = None
        self._metadata: Dict[str, Any] = {}
        self._dependencies: List[str] = []

    @abstractmethod
    async def start(self) -> None:
        """
        Start the service. Must be implemented by subclasses.
        Should set self.is_running = True when successfully started.
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """
        Stop the service. Must be implemented by subclasses.
        Should set self.is_running = False when successfully stopped.
        """
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the service.

        Returns:
            Dict containing health status and metadata
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """
        Get the capabilities this service provides.

        Returns:
            List of capability strings
        """
        pass

    def get_metadata(self) -> Dict[str, Any]:
        """
        Get service metadata.

        Returns:
            Dict containing service metadata
        """
        return {
            "service_name": self.service_name,
            "is_running": self.is_running,
            "start_time": self._start_time,
            "uptime": self.get_uptime(),
            "dependencies": self._dependencies,
            **self._metadata
        }

    def set_metadata(self, key: str, value: Any) -> None:
        """
        Set a metadata value for the service.

        Args:
            key: Metadata key
            value: Metadata value
        """
        self._metadata[key] = value

    def add_dependency(self, service_name: str) -> None:
        """
        Add a service dependency.

        Args:
            service_name: Name of the dependent service
        """
        if service_name not in self._dependencies:
            self._dependencies.append(service_name)

    def get_uptime(self) -> Optional[float]:
        """
        Get the service uptime in seconds.

        Returns:
            Uptime in seconds or None if not started
        """
        if self._start_time is None:
            return None
        return asyncio.get_event_loop().time() - self._start_time

    async def _internal_start(self) -> None:
        """Internal start method that handles common startup tasks."""
        self._start_time = asyncio.get_event_loop().time()
        await self.start()
        logger.info(f"Service {self.service_name} started successfully")

    async def _internal_stop(self) -> None:
        """Internal stop method that handles common shutdown tasks."""
        await self.stop()
        self._start_time = None
        logger.info(f"Service {self.service_name} stopped")

    def __str__(self) -> str:
        return f"Service({self.service_name}, running={self.is_running})"

    def __repr__(self) -> str:
        return self.__str__()


class ServiceError(Exception):
    """Base exception for service-related errors."""
    pass


class ServiceNotFoundError(ServiceError):
    """Raised when a requested service is not found."""
    pass


class ServiceStartupError(ServiceError):
    """Raised when a service fails to start."""
    pass


class ServiceShutdownError(ServiceError):
    """Raised when a service fails to stop."""
    pass
