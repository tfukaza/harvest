"""
Example demonstrating multi-broker and multi-storage support in the service-oriented architecture.

This example shows how to use multiple brokers and storage backends simultaneously through the
Orchestrator and service layer.
"""

import asyncio
from harvest.algorithm import Algorithm
from harvest.orchestrator import Orchestrator
from harvest.broker.mock import MockBroker
from harvest.broker.paper import PaperBroker
from harvest.storage.pickle_storage import PickleStorage
from harvest.storage._base import CentralStorage
from harvest.enum import Interval
from harvest.definitions import OrderSide
from harvest.util.helper import debugger


class MultiBrokerStorageAlgorithm(Algorithm):
    """
    An algorithm that demonstrates using multiple brokers and storage backends.
    """

    def __init__(self):
        super().__init__(
            watch_list=["AAPL", "MSFT"],
            interval=Interval.MIN_5,
            aggregations=[Interval.MIN_5, Interval.MIN_15]
        )

    def setup(self) -> None:
        """Setup multi-broker and multi-storage algorithm"""
        debugger.info(f"Setting up multi-broker/storage algorithm for {self.watch_list}")

    async def main(self) -> None:
        """Main trading logic using multiple brokers and storage backends"""
        debugger.info(f"Running {self.__class__.__name__} at {self.get_datetime()}")

        # Example: Use multiple brokers and storage backends
        symbol = self.watch_list[0]  # AAPL

        try:
            # Get positions from different brokers
            if self.broker_service:
                # Get positions from default broker
                default_positions = await self.broker_service.get_positions("default")
                debugger.info(f"Default broker positions: {len(default_positions)}")

                # Get positions from paper broker (if available)
                try:
                    paper_positions = await self.broker_service.get_positions("paper")
                    debugger.info(f"Paper broker positions: {len(paper_positions)}")
                except ValueError:
                    debugger.info("Paper broker not available")

            # Get price history from different storage backends
            if self.central_storage_service:
                # Get price history from default storage
                price_history_default = self.central_storage_service.get_price_history(
                    symbol, self.interval, storage_name="default"
                )
                debugger.info(f"Default storage price data points: {len(price_history_default.df)}")

                # Get price history from analytical storage (if available)
                try:
                    price_history_analytical = self.central_storage_service.get_price_history(
                        symbol, self.interval, storage_name="analytical"
                    )
                    debugger.info(f"Analytical storage price data points: {len(price_history_analytical.df)}")
                except ValueError:
                    debugger.info("Analytical storage not available")

                # Example: Place a buy order on specific broker
                if self.broker_service:
                    order = await self.broker_service.place_order(
                        symbol=symbol,
                        side=OrderSide.BUY,
                        quantity=10,
                        order_type="market",
                        brokerage="default"
                    )

                    if order:
                        debugger.info(f"Placed order on default broker: {order}")

        except Exception as e:
            debugger.error(f"Multi-broker/storage algorithm error: {e}")


async def main():
    """
    Main function demonstrating multi-broker and multi-storage architecture.
    """
    debugger.info("Starting Multi-Broker/Storage Trading System")

    # Create multiple broker instances
    mock_broker = MockBroker(
        current_time="2024-01-15 09:30",
        realistic_simulation=False
    )

    paper_broker = PaperBroker()

    # Create multiple storage instances
    pickle_storage = PickleStorage()
    analytical_storage = CentralStorage(db_path="sqlite:///analytical_data.db")

    # Create algorithms
    algorithms: list[Algorithm] = [
        MultiBrokerStorageAlgorithm()
    ]

    # Create orchestrator with multiple brokers and storages
    brokers = {
        "default": mock_broker,
        "paper": paper_broker
    }

    storages = {
        "default": pickle_storage,
        "analytical": analytical_storage
    }

    orchestrator = Orchestrator(
        broker=brokers,  # Pass multiple brokers
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

        # Get service statistics
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
        debugger.info("Multi-broker/storage system shutdown complete")


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
