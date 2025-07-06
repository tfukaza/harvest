"""
Service Coordinator for the Harvest Trading System.

This module provides the main coordinator that sets up and manages all services
in the microservices architecture. It handles service registration, startup,
and coordination between different services.
"""

import asyncio
import datetime as dt
from typing import TYPE_CHECKING

from .service_interface import Service
from .discovery import ServiceRegistry
from .market_data_service import MarketDataService
from .broker_service import BrokerService
from .algorithm_service import AlgorithmService
from .central_storage_service import CentralStorageService
from ..events.event_bus import EventBus
from ..util.helper import debugger

if TYPE_CHECKING:
    from ..algorithm import Algorithm


class ServiceCoordinator:
    """
    Main coordinator for all services in the trading system.
    
    This class is responsible for:
    - Setting up all services
    - Managing service lifecycle
    - Coordinating communication between services
    - Providing a unified interface for system management
    """

    def __init__(self):
        self.service_registry = ServiceRegistry()
        self.event_bus = EventBus()
        self.services: dict[str, Service] = {}
        self.is_running = False

    async def setup_services(self, broker_instance, storage_db_path: str | None = None) -> None:
        """
        Set up all core services
        
        Args:
            broker_instance: Broker instance to use for market data and trading
            storage_db_path: Path for central storage database
        """
        debugger.info("Setting up services...")

        # Create core services
        market_data_service = MarketDataService(broker_instance)
        broker_service = BrokerService(broker_instance)
        algorithm_service = AlgorithmService()
        central_storage_service = CentralStorageService(storage_db_path)

        # Set up inter-service dependencies
        market_data_service.set_event_bus(self.event_bus)
        market_data_service.set_central_storage(central_storage_service)
        broker_service.set_event_bus(self.event_bus)

        # Set up algorithm service with shared resources
        algorithm_service.event_bus = self.event_bus
        algorithm_service.service_registry = self.service_registry

        # Store services
        self.services = {
            "market_data": market_data_service,
            "broker": broker_service,
            "algorithm_manager": algorithm_service,
            "central_storage": central_storage_service
        }

        # Register all services
        for service_name, service in self.services.items():
            await self.service_registry.register_service(service_name, service)

        debugger.info("Services setup completed")

    async def start_all_services(self) -> None:
        """Start all registered services"""
        debugger.info("Starting all services...")

        for service_name, service in self.services.items():
            try:
                await service.start()
                debugger.info(f"Started service: {service_name}")
            except Exception as e:
                debugger.error(f"Failed to start service {service_name}: {e}")

        self.is_running = True
        debugger.info("All services started")

    async def stop_all_services(self) -> None:
        """Stop all services gracefully"""
        debugger.info("Stopping all services...")

        # Stop services in reverse order
        for service_name, service in reversed(list(self.services.items())):
            try:
                await service.stop()
                debugger.info(f"Stopped service: {service_name}")
            except Exception as e:
                debugger.error(f"Failed to stop service {service_name}: {e}")

        self.is_running = False
        debugger.info("All services stopped")

    def add_algorithm(self, algorithm: "Algorithm") -> None:
        """
        Add an algorithm to the system
        
        Args:
            algorithm: Algorithm instance to add
        """
        if "algorithm_manager" in self.services:
            algorithm_service = self.services["algorithm_manager"]
            if isinstance(algorithm_service, AlgorithmService):
                algorithm_service.add_algorithm(algorithm)
                debugger.info(f"Added algorithm: {algorithm.__class__.__name__}")
        else:
            debugger.error("Algorithm manager service not available")

    async def start_algorithm(self, algorithm_name: str) -> None:
        """
        Start a specific algorithm
        
        Args:
            algorithm_name: Name of algorithm to start
        """
        if "algorithm_manager" in self.services:
            algorithm_service = self.services["algorithm_manager"]
            if isinstance(algorithm_service, AlgorithmService):
                await algorithm_service.start_algorithm(algorithm_name)
        else:
            debugger.error("Algorithm manager service not available")

    async def stop_algorithm(self, algorithm_name: str) -> None:
        """
        Stop a specific algorithm
        
        Args:
            algorithm_name: Name of algorithm to stop
        """
        if "algorithm_manager" in self.services:
            algorithm_service = self.services["algorithm_manager"]
            if isinstance(algorithm_service, AlgorithmService):
                await algorithm_service.stop_algorithm(algorithm_name)
        else:
            debugger.error("Algorithm manager service not available")

    def get_service_status(self) -> dict:
        """
        Get status of all services
        
        Returns:
            Dictionary with service status information
        """
        status = {
            "system_running": self.is_running,
            "total_services": len(self.services),
            "services": {}
        }

        for service_name, service in self.services.items():
            try:
                health = service.health_check()
                status["services"][service_name] = {
                    "status": health.get("status", "unknown"),
                    "capabilities": service.get_capabilities(),
                    "health_details": health
                }
            except Exception as e:
                status["services"][service_name] = {
                    "status": "error",
                    "error": str(e)
                }

        return status

    async def start_market_data_feed(self, symbols: list[str], interval) -> str:
        """
        Start market data feed for symbols
        
        Args:
            symbols: List of symbols to track
            interval: Data update interval
            
        Returns:
            Feed ID
        """
        if "market_data" in self.services:
            market_data_service = self.services["market_data"]
            if isinstance(market_data_service, MarketDataService):
                return await market_data_service.start_data_feed(symbols, interval)
        
        raise Exception("Market data service not available")

    async def run_forever(self) -> None:
        """
        Run the service coordinator indefinitely
        This is the main event loop for the system
        """
        debugger.info("Service coordinator running forever...")
        
        try:
            while self.is_running:
                # Perform periodic health checks
                status = self.get_service_status()
                
                # Log any unhealthy services
                for service_name, service_status in status["services"].items():
                    if service_status["status"] not in ["healthy", "running"]:
                        debugger.warning(f"Service {service_name} status: {service_status['status']}")

                # Sleep for 30 seconds before next check
                await asyncio.sleep(30)
                
        except KeyboardInterrupt:
            debugger.info("Received shutdown signal")
        except Exception as e:
            debugger.error(f"Service coordinator error: {e}")
        finally:
            await self.stop_all_services()


# Example usage function
async def create_trading_system(broker_instance, algorithms: list["Algorithm"] | None = None) -> ServiceCoordinator:
    """
    Create and start a complete trading system
    
    Args:
        broker_instance: Broker instance to use
        algorithms: List of algorithms to add (optional)
        
    Returns:
        Running ServiceCoordinator instance
    """
    coordinator = ServiceCoordinator()
    
    # Setup and start services
    await coordinator.setup_services(broker_instance)
    await coordinator.start_all_services()
    
    # Add algorithms if provided
    if algorithms:
        for algorithm in algorithms:
            coordinator.add_algorithm(algorithm)
    
    return coordinator
