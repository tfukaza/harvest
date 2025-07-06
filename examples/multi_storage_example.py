"""
Example demonstrating multi-storage support in the service-oriented architecture.

This example shows how to use multiple storage backends simultaneously through the
Orchestrator and CentralStorageService.
"""

import asyncio
from harvest.algorithm import Algorithm
from harvest.orchestrator import Orchestrator
from harvest.broker.mock import MockBroker
from harvest.storage.pickle_storage import PickleStorage
from harvest.storage._base import CentralStorage
from harvest.enum import Interval
from harvest.definitions import OrderSide
from harvest.util.helper import debugger


class MultiStorageAlgorithm(Algorithm):
    """
    An algorithm that demonstrates using multiple storage backends.
    """

    def __init__(self):
        super().__init__(
            watch_list=["AAPL", "MSFT"],
            interval=Interval.MIN_5,
            aggregations=[Interval.MIN_5, Interval.MIN_15]
        )

    def setup(self) -> None:
        """Setup multi-storage algorithm"""
        debugger.info(f"Setting up multi-storage algorithm for {self.watch_list}")

    async def main(self) -> None:
        """Main logic using multiple storage backends"""
        debugger.info(f"Running {self.__class__.__name__} at {self.get_datetime()}")

        # Example: Get price history from different storage backends
        symbol = self.watch_list[0]  # AAPL

        try:
            if self.central_storage_service:
                # Get price history from default storage
                price_history_default = self.central_storage_service.get_price_history(
                    symbol, self.interval, storage_name="default"
                )
                debugger.info(f"Default storage price data points: {len(price_history_default.df)}")

                # Get price history from backup storage (if available)
                try:
                    price_history_backup = self.central_storage_service.get_price_history(
                        symbol, self.interval, storage_name="backup"
                    )
                    debugger.info(f"Backup storage price data points: {len(price_history_backup.df)}")
                except ValueError:
                    debugger.info("Backup storage not available")

                # Example: Store price data to specific storage
                # (In a real scenario, you'd have actual market data)
                debugger.info("Example multi-storage operations completed")

        except Exception as e:
            debugger.error(f"Multi-storage algorithm error: {e}")


async def main():
    """
    Main function demonstrating multi-storage architecture.
    """
    debugger.info("Starting Multi-Storage Trading System")

    # Create broker
    broker = MockBroker(
        current_time="2024-01-15 09:30",
        realistic_simulation=False
    )

    # Create multiple storage instances
    default_storage = PickleStorage()
    backup_storage = CentralStorage(db_path="sqlite:///backup_data.db")

    # Create algorithms
    algorithms: list[Algorithm] = [
        MultiStorageAlgorithm()
    ]

    # Create orchestrator with multiple storage backends
    storages = {
        "default": default_storage,
        "backup": backup_storage
    }

    orchestrator = Orchestrator(
        broker=broker,
        storage=storages,  # Pass multiple storages
        algorithm_list=algorithms,
        debug=True
    )

    try:
        # Start the orchestrator and all services
        await orchestrator.start()

        # Monitor system health
        health_status = await orchestrator.get_service_status()
        debugger.info(f"System health: {health_status}")

        # Get storage service stats
        storage_stats = orchestrator.central_storage_service.get_storage_stats()
        debugger.info(f"Storage stats: {storage_stats}")

        # Run for a limited time for demonstration
        debugger.info("Running for 30 seconds...")
        await asyncio.sleep(30)

    except KeyboardInterrupt:
        debugger.info("Received interrupt signal")
    finally:
        # Graceful shutdown
        await orchestrator.shutdown_services()
        debugger.info("Multi-storage system shutdown complete")


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
