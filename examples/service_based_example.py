"""
Example demonstrating the new service-based architecture.

This example shows how to:
1. Create algorithms using the new Algorithm class
2. Set up the service infrastructure
3. Run algorithms in the microservices environment
"""

import asyncio
from harvest.algorithm import Algorithm
from harvest.enum import Interval
from harvest.services import create_trading_system
from harvest.broker.mock import MockBroker  # Assuming this exists
from harvest.util.helper import debugger


class SimpleAlgorithm(Algorithm):
    """
    A simple example algorithm using the new service-based architecture.
    """

    def __init__(self):
        # Initialize with watchlist and intervals
        super().__init__(
            watch_list=["AAPL", "MSFT", "GOOGL"],
            interval=Interval.MIN_5,
            aggregations=[Interval.MIN_1, Interval.MIN_5, Interval.DAY_1]
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
                debugger.warning(f"Failed to get data for {symbol}: {e}")


class TradingAlgorithm(Algorithm):
    """
    A more advanced algorithm that actually places trades.
    """

    def __init__(self):
        super().__init__(
            watch_list=["SPY"],
            interval=Interval.MIN_15,
            aggregations=[Interval.MIN_5, Interval.MIN_15, Interval.DAY_1]
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
    Main function demonstrating the service-based architecture.
    """
    debugger.info("Starting service-based trading system...")

    # Create a mock broker for demonstration
    # In production, this would be a real broker instance
    broker = MockBroker()

    # Create algorithms
    simple_algo = SimpleAlgorithm()
    trading_algo = TradingAlgorithm()

    # Create and start the trading system
    coordinator = await create_trading_system(
        broker_instance=broker,
        algorithms=[simple_algo, trading_algo]
    )

    # Start the algorithms
    await coordinator.start_algorithm("SimpleAlgorithm")
    await coordinator.start_algorithm("TradingAlgorithm")

    # Get system status
    status = coordinator.get_service_status()
    debugger.info(f"System status: {status}")

    # Run for a specific time for demonstration
    debugger.info("Running system for 5 minutes...")
    await asyncio.sleep(300)  # 5 minutes

    # Stop algorithms
    await coordinator.stop_algorithm("SimpleAlgorithm")
    await coordinator.stop_algorithm("TradingAlgorithm")

    # Stop the system
    await coordinator.stop_all_services()

    debugger.info("System shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
