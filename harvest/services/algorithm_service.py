import asyncio
import dataclasses
import datetime as dt
from typing import TYPE_CHECKING

from .service_interface import Service
from .discovery import ServiceRegistry
from ..events.event_bus import EventBus
from ..util.helper import debugger

if TYPE_CHECKING:
    from ..algorithm import Algorithm, AlgorithmHealth, AlgorithmStatus


def check_interval(current_time: dt.datetime, interval_str: str) -> bool:
    """
    Check if algorithm should run based on its interval

    Args:
        current_time: Current UTC datetime
        interval_str: Interval string (e.g., "5min", "1hour", "1day")

    Returns:
        True if algorithm should run, False otherwise
    """
    minute = current_time.minute
    hour = current_time.hour

    if interval_str == "1min":
        return True  # Run every minute
    elif interval_str == "5min":
        return minute % 5 == 0
    elif interval_str == "15min":
        return minute % 15 == 0
    elif interval_str == "30min":
        return minute % 30 == 0
    elif interval_str == "1hour":
        return minute == 0
    elif interval_str == "1day":
        return hour == 9 and minute == 30  # Market open
    else:
        return False


class AlgorithmService(Service):
    """
    Service for managing algorithm lifecycle and execution.
    Handles algorithm registration, scheduling, and monitoring.
    """

    def __init__(self):
        super().__init__("algorithm_manager")
        self.algorithms: dict[str, "Algorithm"] = {}
        self.event_bus = EventBus()
        self.service_registry = ServiceRegistry()
        self.running_tasks: dict[str, asyncio.Task] = {}
        self._is_running = False
        self._monitoring_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the algorithm service"""
        self.is_running = True
        self._start_time = dt.datetime.utcnow().timestamp()

        # Start monitoring task
        self._monitoring_task = asyncio.create_task(self._monitor_algorithms())

    async def stop(self) -> None:
        """Stop the algorithm service"""
        # Stop all running algorithms
        for algorithm_name in list(self.running_tasks.keys()):
            await self.stop_algorithm(algorithm_name)

        # Stop monitoring task
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        self.is_running = False

    def health_check(self) -> dict[str, any]:  # type: ignore
        """Perform health check on the algorithm service"""
        return {
            "status": "healthy" if self.is_running else "stopped",
            "total_algorithms": len(self.algorithms),
            "running_algorithms": len(self.running_tasks),
            "event_bus_active": self.event_bus is not None,
            "service_registry_active": self.service_registry is not None,
            "uptime_seconds": dt.datetime.utcnow().timestamp() - (self._start_time or 0)
        }

    def get_capabilities(self) -> list[str]:
        """Get list of service capabilities"""
        return [
            "algorithm_management",
            "algorithm_scheduling",
            "lifecycle_management",
            "event_coordination",
            "service_discovery"
        ]

    def add_algorithm(self, algorithm: "Algorithm") -> None:
        """
        Add algorithm to be managed

        Args:
            algorithm: Algorithm instance to add
        """
        algorithm_name = algorithm.__class__.__name__
        self.algorithms[algorithm_name] = algorithm

        # Set up algorithm with shared services
        algorithm.event_bus = self.event_bus
        algorithm.service_registry = self.service_registry

        debugger.info(f"Added algorithm: {algorithm_name}")

    def remove_algorithm(self, algorithm_name: str) -> None:
        """
        Remove an algorithm from management

        Args:
            algorithm_name: Name of algorithm to remove
        """
        if algorithm_name in self.algorithms:
            # Stop if running
            if algorithm_name in self.running_tasks:
                asyncio.create_task(self.stop_algorithm(algorithm_name))

            del self.algorithms[algorithm_name]
            debugger.info(f"Removed algorithm: {algorithm_name}")

    async def start_algorithm(self, algorithm_name: str) -> None:
        """
        Start a specific algorithm

        Args:
            algorithm_name: Name of algorithm to start
        """
        if algorithm_name not in self.algorithms:
            raise ValueError(f"Algorithm {algorithm_name} not found")

        if algorithm_name in self.running_tasks:
            debugger.warning(f"Algorithm {algorithm_name} is already running")
            return

        algorithm = self.algorithms[algorithm_name]

        try:
            # Reset health status
            algorithm.health = AlgorithmHealth(
                status=AlgorithmStatus.STARTING,
                last_update=dt.datetime.utcnow(),
            )
            # Initialize algorithm
            await algorithm.discover_services()
            algorithm.setup_event_subscriptions()
            algorithm.setup()

            # Start algorithm main loop
            task = asyncio.create_task(self._run_algorithm_loop(algorithm))
            self.running_tasks[algorithm_name] = task

            debugger.info(f"Started algorithm: {algorithm_name}")

        except Exception as e:
            debugger.error(f"Failed to start algorithm {algorithm_name}: {e}")
            raise

    async def stop_algorithm(self, algorithm_name: str) -> None:
        """
        Stop a specific algorithm

        Args:
            algorithm_name: Name of algorithm to stop
        """
        if algorithm_name not in self.running_tasks:
            debugger.warning(f"Algorithm {algorithm_name} is not running")
            return

        task = self.running_tasks[algorithm_name]
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        del self.running_tasks[algorithm_name]
        debugger.info(f"Stopped algorithm: {algorithm_name}")

    async def _run_algorithm_loop(self, algorithm: "Algorithm") -> None:
        """
        Run algorithm main loop based on its interval

        Args:
            algorithm: Algorithm instance to run
        """
        algorithm_name = algorithm.__class__.__name__
        algorithm.health.status = AlgorithmStatus.RUNNING
        algorithm.health.last_update = dt.datetime.utcnow()

        while True:
            try:
                current_time = dt.datetime.utcnow()

                # Check if algorithm should run based on its interval
                if self._should_run_algorithm(algorithm, current_time):
                    debugger.debug(f"Running algorithm: {algorithm_name}")

                    # Update algorithm stats if available
                    if algorithm.stats:
                        algorithm.stats.utc_timestamp = current_time

                    # Run algorithm main method
                    await algorithm.main()
                    algorithm.health.last_update = dt.datetime.utcnow()

                # Sleep until next check (every minute)
                await asyncio.sleep(60)

            except asyncio.CancelledError:
                debugger.info(f"Algorithm {algorithm_name} loop cancelled")
                algorithm.health.status = AlgorithmStatus.CANCELLED
                algorithm.health.last_update = dt.datetime.utcnow()
                break
            except Exception as e:
                debugger.error(f"Algorithm {algorithm_name} error: {e}")
                algorithm.health.status = AlgorithmStatus.CRASHED
                algorithm.health.error_count += 1
                algorithm.health.last_error = str(e)
                algorithm.health.last_update = dt.datetime.utcnow()
                # Stop the algorithm
                break

    def _should_run_algorithm(self, algorithm: "Algorithm", current_time: dt.datetime) -> bool:
        """
        Check if algorithm should run based on its interval

        Args:
            algorithm: Algorithm to check
            current_time: Current UTC time

        Returns:
            True if algorithm should run, False otherwise
        """
        return check_interval(current_time, algorithm.interval.value)

    async def _monitor_algorithms(self) -> None:
        """
        Background task to monitor algorithm health and performance
        """
        while True:
            try:
                current_time = dt.datetime.utcnow()

                # Check each running algorithm
                for algorithm_name, task in list(self.running_tasks.items()):
                    algorithm = self.algorithms[algorithm_name]
                    if task.done():
                        debugger.warning(f"Algorithm {algorithm_name} task completed unexpectedly")

                        # Check if it was cancelled or had an exception
                        try:
                            result = task.result()
                            debugger.info(f"Algorithm {algorithm_name} result: {result}")
                            algorithm.health.status = AlgorithmStatus.COMPLETED
                        except asyncio.CancelledError:
                            debugger.info(f"Algorithm {algorithm_name} was cancelled")
                            algorithm.health.status = AlgorithmStatus.CANCELLED
                        except Exception as e:
                            debugger.error(f"Algorithm {algorithm_name} failed: {e}")
                            # The status is already set to CRASHED in the run loop.
                            # No need to update it here, just log it.

                            # Optionally restart the algorithm
                            # await self.start_algorithm(algorithm_name)

                        algorithm.health.last_update = current_time

                        # Clean up the task reference
                        if algorithm_name in self.running_tasks:
                            del self.running_tasks[algorithm_name]
                    else:
                        # Update health status for running algorithms
                        algorithm.health.status = AlgorithmStatus.RUNNING
                        algorithm.health.last_update = current_time

                # Sleep for 30 seconds before next check
                await asyncio.sleep(30)

            except asyncio.CancelledError:
                debugger.info("Algorithm monitoring cancelled")
                break
            except Exception as e:
                debugger.error(f"Algorithm monitoring error: {e}")
                await asyncio.sleep(30)

    def get_algorithm_status(self, algorithm_name: str) -> dict:
        """
        Get status information for a specific algorithm

        Args:
            algorithm_name: Name of algorithm

        Returns:
            Status dictionary
        """
        if algorithm_name not in self.algorithms:
            return {"status": "not_found"}

        is_running = algorithm_name in self.running_tasks
        algorithm = self.algorithms[algorithm_name]

        return {
            "status": "running" if is_running else "stopped",
            "interval": algorithm.interval.value,
            "watchlist": algorithm.watch_list,
            "aggregations": [agg.value for agg in algorithm.aggregations],
            "services_discovered": all([
                algorithm.market_data_service,
                algorithm.broker_services,
                algorithm.central_storage_services
            ]),
            "health": dataclasses.asdict(algorithm.health),
        }

    def get_all_algorithm_status(self) -> dict:
        """
        Get status for all algorithms

        Returns:
            Dictionary mapping algorithm names to their status
        """
        return {
            name: self.get_algorithm_status(name)
            for name in self.algorithms.keys()
        }
