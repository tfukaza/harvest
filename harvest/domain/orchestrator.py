"""Orchestrator — legacy (non-agent) runtime path for algorithmic trading.

This module is part of the original trading system that runs deterministic
algorithms via broker adapters.  It is **not** used by the agent sandbox.

For AI-agent-based workflows, use :class:`~harvest.agent_sandbox.basic_sandbox.BasicSandbox`
with ``harvest.services.*Service`` classes instead.
"""

import asyncio
import datetime as dt
from typing import List, Dict
from rich.console import Console

from harvest.domain.algorithm import Algorithm
from harvest.broker._base import Broker
from harvest.storage.schema.market import CentralStorage
from harvest.services import (
    ServiceRegistry,
    MarketDataService,
    BrokerService,
    AlgorithmService,
    CentralStorageService,
)
from harvest.util.helper import debugger
from harvest.events.event_bus import EventBus
from harvest.domain.definitions import RuntimeData
from harvest.interfaces.service import Service, ServiceRole


class Orchestrator:
    """
    Main orchestrator for the service-oriented trading system.

    This class manages the lifecycle of all services and coordinates
    algorithm execution through the service architecture.
    """

    def __init__(
        self,
        broker: Broker | Dict[str, Broker],
        storage: CentralStorage | Dict[str, CentralStorage],
        algorithm_list: List[Algorithm],
        secret_path: str = "./secret.yaml",
        debug: bool = False,
    ) -> None:
        """
        Initialize the orchestrator with required components.

        Args:
            broker: The broker instance(s) to use for trading
            storage: The storage instance(s) for data persistence
            algorithm_list: List of algorithms to manage
            secret_path: Path to secret configuration file
            debug: Enable debug logging
        """
        self.console = Console()
        self.algorithm_list = algorithm_list
        self.secret_path = secret_path

        if debug:
            debugger.setLevel("DEBUG")

        # Service-oriented architecture components
        self.service_registry = ServiceRegistry()
        self.event_bus = EventBus()
        self.resources: dict[str, Service] = {}

        # Phase 13: generalised external-world service registries (legacy)
        self.data_sources: dict = {}
        self.actions: dict = {}
        self.event_sources: dict = {}

        # Handle broker configuration
        if isinstance(broker, dict):
            # Multiple brokers provided
            brokers = broker
            primary_broker = next(iter(broker.values()))  # Use first broker for market data
        else:
            # Single broker provided - wrap in dictionary
            brokers = {"default": broker}
            primary_broker = broker

        # Handle storage configuration
        if isinstance(storage, dict):
            # Multiple storages provided
            storages = storage
        else:
            # Single storage provided - wrap in dictionary
            storages = {"default": storage}

        # Initialize services
        self.central_storage_service = CentralStorageService(storages)
        self.market_data_service = MarketDataService(primary_broker)
        self.broker_service = BrokerService(brokers)
        self.algorithm_service = AlgorithmService()

        # Setup services
        self._setup_services()

        # Initialize algorithms with services
        self._setup_algorithms()

    def _setup_services(self) -> None:
        """Initialize and configure all services"""
        # Register all services (we'll await these in start_services)
        self.services_to_register = [
            (self.central_storage_service.service_name, self.central_storage_service),
            (self.market_data_service.service_name, self.market_data_service),
            (self.broker_service.service_name, self.broker_service),
            (self.algorithm_service.service_name, self.algorithm_service),
        ]

        # Configure cross-service dependencies
        self.market_data_service.set_central_storage(self.central_storage_service)
        self.market_data_service.set_event_bus(self.event_bus)
        self.broker_service.set_event_bus(self.event_bus)
        self.register_resource(self.market_data_service)

        # Set shared event bus for algorithm service
        self.algorithm_service.event_bus = self.event_bus
        self.algorithm_service.service_registry = self.service_registry

    def _setup_algorithms(self) -> None:
        """Setup algorithms with service-oriented architecture"""
        for algorithm in self.algorithm_list:
            # Set up algorithm with services
            algorithm.service_registry = self.service_registry
            algorithm.event_bus = self.event_bus

            # Add algorithm to the algorithm service
            self.algorithm_service.add_algorithm(algorithm)

    def register_resource(self, resource: Service) -> None:
        """Register a resource exposed by the orchestrator-managed infrastructure."""
        self.resources[resource.resource_id] = resource

    def get_resource(self, resource_id: str) -> Service | None:
        """Retrieve a registered resource by identifier."""
        return self.resources.get(resource_id)

    def list_resources(self) -> list[str]:
        """List resource identifiers exposed by the orchestrator."""
        return list(self.resources.keys())

    # -- Phase 13: generalised service registry ------------------------------

    def register_data_source(self, source) -> None:
        """Register a DataSource with the orchestrator."""
        if source.source_id in self.data_sources:
            raise ValueError(f"DataSource already registered: {source.source_id}")
        self.data_sources[source.source_id] = source
        debugger.info("Registered DataSource: %s", source.source_id)

    def register_action(self, action) -> None:
        """Register an Action handler with the orchestrator."""
        if action.action_id in self.actions:
            raise ValueError(f"Action already registered: {action.action_id}")
        self.actions[action.action_id] = action
        debugger.info("Registered Action: %s", action.action_id)

    def register_event_source(self, source) -> None:
        """Register an EventSource with the orchestrator."""
        if source.source_id in self.event_sources:
            raise ValueError(f"EventSource already registered: {source.source_id}")
        self.event_sources[source.source_id] = source
        debugger.info("Registered EventSource: %s", source.source_id)

    def get_data_source(self, source_id: str):
        """Retrieve a registered DataSource by ID."""
        return self.data_sources.get(source_id)

    def get_action(self, action_id: str):
        """Retrieve a registered Action handler by ID."""
        return self.actions.get(action_id)

    def get_event_source(self, source_id: str):
        """Retrieve a registered EventSource by ID."""
        return self.event_sources.get(source_id)

    def list_data_sources(self) -> list[str]:
        """Return IDs of all registered DataSources."""
        return list(self.data_sources.keys())

    def list_actions(self) -> list[str]:
        """Return IDs of all registered Actions."""
        return list(self.actions.keys())

    def list_event_sources(self) -> list[str]:
        """Return IDs of all registered EventSources."""
        return list(self.event_sources.keys())

    async def start(self) -> None:
        """Start the orchestrator and all services"""
        debugger.info("Starting Harvest Orchestrator...")

        with self.console.status("[bold green] Starting services...[/bold green]") as _:
            # Start all services
            await self.start_services()
            self.console.print("- All services started")

            # Setup algorithms
            for algorithm in self.algorithm_list:
                await algorithm.discover_services()
                algorithm.setup_event_subscriptions()
                algorithm.setup()

                # Start algorithm execution
                await self.algorithm_service.start_algorithm(algorithm.__class__.__name__)

            self.console.print("- All algorithms initialized and started")

        self.console.print("> [bold green]Orchestrator initialization complete[/bold green]")

    async def start_services(self) -> None:
        """Start all required services"""
        debugger.info("Starting services...")

        # Register all services first
        for service_name, service_instance in self.services_to_register:
            await self.service_registry.register_service(service_name, service_instance)

        # Start central storage service
        await self.central_storage_service.start()
        debugger.info("- Central storage service started")

        # Start market data service
        await self.market_data_service.start()
        debugger.info("- Market data service started")

        # Start broker service
        await self.broker_service.start()
        debugger.info("- Broker service started")

        # Start algorithm service
        await self.algorithm_service.start()
        debugger.info("- Algorithm service started")

        debugger.info("All services started successfully")

    async def monitor_health(self) -> Dict[str, any]:  # type: ignore
        """Monitor health of all services"""
        return await self.service_registry.health_check_all()

    async def shutdown_services(self) -> None:
        """Gracefully shutdown all services"""
        debugger.info("Shutting down services...")

        # Stop services in reverse order
        await self.algorithm_service.stop()
        await self.broker_service.stop()
        await self.market_data_service.stop()
        await self.central_storage_service.stop()

        debugger.info("All services shut down")

    async def run(self) -> None:
        """Main execution loop"""
        try:
            await self.start()

            # Keep running until interrupted
            while True:
                # Monitor health periodically
                health_status = await self.monitor_health()
                if not all(service["status"] == "healthy" for service in health_status.values()):
                    debugger.warning(f"Service health issues detected: {health_status}")

                # Sleep for a bit before next health check
                await asyncio.sleep(30)

        except KeyboardInterrupt:
            debugger.info("Shutdown requested by user")
        except Exception as e:
            debugger.error(f"Orchestrator error: {e}")
        finally:
            await self.shutdown_services()

    def add_algorithm(self, algorithm: Algorithm) -> None:
        """Add a new algorithm to the system"""
        self.algorithm_list.append(algorithm)
        algorithm.service_registry = self.service_registry
        algorithm.event_bus = self.event_bus
        self.algorithm_service.add_algorithm(algorithm)

    async def remove_algorithm(self, algorithm_name: str) -> None:
        """Remove an algorithm from the system"""
        await self.algorithm_service.stop_algorithm(algorithm_name)
        self.algorithm_list = [algo for algo in self.algorithm_list if algo.__class__.__name__ != algorithm_name]

    def get_algorithm_status(self) -> Dict[str, any]:  # type: ignore
        """Get status of all algorithms"""
        return {
            "total_algorithms": len(self.algorithm_list),
            "running_algorithms": len(self.algorithm_service.running_tasks),
            "algorithm_names": [algo.__class__.__name__ for algo in self.algorithm_list],
        }

    async def get_service_status(self) -> Dict[str, any]:  # type: ignore
        """Get status of all services"""
        return await self.monitor_health()

    async def restart_service(self, service_name: str) -> None:
        """Restart a specific service"""
        service = self.service_registry.discover_service(service_name)
        if service:
            await service.stop()
            await service.start()
            debugger.info(f"Service {service_name} restarted")
        else:
            debugger.error(f"Service {service_name} not found")

    async def tick(self, market_data: Dict[str, any]) -> None:  # type: ignore
        """Process market data tick - legacy compatibility"""
        # In the new architecture, market data is handled by the MarketDataService
        # This method is kept for backward compatibility
        if hasattr(self.market_data_service, "publish_price_update"):
            # Convert market_data to the expected format for the service
            for symbol, data in market_data.items():
                if hasattr(data, "_df"):  # TickerFrame
                    self.market_data_service.publish_price_update(symbol, data)
                else:
                    debugger.warning(f"Unexpected market data format for {symbol}: {type(data)}")
