"""
Example demonstrating the new service-oriented architecture with the Orchestrator class.

This example shows how to use the Orchestrator to manage algorithms through
services rather than direct broker/storage access.
"""

import asyncio
from harvest.algorithm import Algorithm
from harvest.orchestrator import Orchestrator
from harvest.broker.mock import MockBroker
from harvest.storage.pickle_storage import PickleStorage
from harvest.enum import Interval
from harvest.util.helper import debugger


class SimpleMonitoringAlgorithm(Algorithm):
    """
    A simple algorithm that monitors prices using the service-oriented architecture.
    """

    def __init__(self):
        super().__init__(
            watch_list=["AAPL", "MSFT", "GOOGL"],
            interval=Interval.MIN_5,
            aggregations=[Interval.MIN_5, Interval.MIN_15]
        )

    def setup(self) -> None:
        """Setup method called before algorithm starts"""
        debugger.info(f"Setting up {self.__class__.__name__}")
        debugger.info(f"Watching: {self.watch_list}")
        debugger.info(f"Interval: {self.interval}")

    async def main(self) -> None:
        """Main algorithm logic"""
        debugger.info(f"Running {self.__class__.__name__} at {self.get_datetime()}")

        # Example: Get current prices using the new service-based approach
        for symbol in self.watch_list:
            try:
                # Get price history from central storage service
                price_history = self.get_price_history(symbol, self.interval)
                if len(price_history._df) > 0:
                    current_price = price_history._df["close"][-1]
                    debugger.info(f"{symbol}: ${current_price:.2f}")

                    # Example technical analysis
                    sma_20 = self.sma(symbol, period=20)
                    if sma_20 is not None and len(sma_20) > 0:
                        debugger.info(f"{symbol} SMA(20): {sma_20[-1]:.2f}")

            except Exception as e:
                debugger.warning(f"Error processing {symbol}: {e}")


class TradingAlgorithm(Algorithm):
    """
    A more advanced algorithm that performs actual trading operations.
    """

    def __init__(self):
        super().__init__(
            watch_list=["SPY"],
            interval=Interval.MIN_5,
            aggregations=[Interval.MIN_5, Interval.MIN_15, Interval.MIN_30]
        )
        self.position_size = 100

    def setup(self) -> None:
        """Setup trading algorithm"""
        debugger.info(f"Setting up trading algorithm for {self.watch_list}")

    async def main(self) -> None:
        """Main trading logic"""
        symbol = self.watch_list[0]  # SPY

        try:
            # Get current position
            current_quantity = await self.get_asset_quantity(symbol)

            # Get current price and moving averages
            prices = self.get_asset_price_list(symbol, ref="close")
            if not prices or len(prices) < 50:
                debugger.info("Not enough price data")
                return

            sma_20 = self.sma(symbol, period=20)
            sma_50 = self.sma(symbol, period=50)

            if sma_20 is None or sma_50 is None:
                debugger.info("Technical indicators not ready")
                return

            current_sma_20 = sma_20[-1]
            current_sma_50 = sma_50[-1]

            # Simple moving average crossover strategy
            if current_sma_20 > current_sma_50 and current_quantity == 0:
                # Buy signal
                debugger.info(f"Buy signal: SMA20({current_sma_20:.2f}) > SMA50({current_sma_50:.2f})")

                buying_power = self.get_account_buying_power()
                if buying_power > 1000:  # Minimum buying power check
                    order = await self.buy(symbol, self.position_size)
                    if order:
                        debugger.info(f"Placed buy order: {order}")

            elif current_sma_20 < current_sma_50 and current_quantity > 0:
                # Sell signal
                debugger.info(f"Sell signal: SMA20({current_sma_20:.2f}) < SMA50({current_sma_50:.2f})")

                order = await self.sell(symbol, int(current_quantity))
                if order:
                    debugger.info(f"Placed sell order: {order}")

        except Exception as e:
            debugger.error(f"Trading algorithm error: {e}")


async def main():
    """
    Main function demonstrating the service-oriented architecture.
    """
    debugger.info("Starting Service-Oriented Trading System")

    # Create broker and storage instances
    broker = MockBroker(
        current_time="2024-01-15 09:30",
        realistic_simulation=False
    )

    storage = PickleStorage()

    # Create algorithms
    algorithms = [
        SimpleMonitoringAlgorithm(),
        TradingAlgorithm()
    ]

    # Create the orchestrator (replaces the old Client class)
    orchestrator = Orchestrator(
        broker=broker,
        storage=storage,
        algorithm_list=algorithms,
        debug=True
    )

    try:
        # Start the orchestrator and all services
        await orchestrator.start()

        # Monitor system health
        health_status = await orchestrator.get_service_status()
        debugger.info(f"System health: {health_status}")

        # Get algorithm status
        algo_status = orchestrator.get_algorithm_status()
        debugger.info(f"Algorithm status: {algo_status}")

        # Run for a limited time for demonstration
        debugger.info("Running for 60 seconds...")
        await asyncio.sleep(60)

        # Demonstrate adding a new algorithm dynamically
        new_algo = SimpleMonitoringAlgorithm()
        orchestrator.add_algorithm(new_algo)
        debugger.info("Added new algorithm dynamically")

        # Run for another 30 seconds
        await asyncio.sleep(30)

    except KeyboardInterrupt:
        debugger.info("Received interrupt signal")
    finally:
        # Graceful shutdown
        await orchestrator.shutdown_services()
        debugger.info("System shutdown complete")


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
