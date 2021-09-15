from harvest.algo import BaseAlgo
from harvest.trader import Trader


class Crossover(BaseAlgo):
    def main(self):
        # Get a list of sma values
        sma_short = self.sma(period=20)
        sma_long = self.sma(period=50)
        # Check if the different sma values cross over
        if self.crossover(sma_long, sma_short):
            self.buy(quantity=1)
        elif self.crossover(sma_short, sma_long):
            self.sell(quantity=1)


if __name__ == "__main__":
    t = Trader()
    t.set_symbol("SPY")
    t.set_algo(Crossover())

    # Run the main() function once every 1 minute
    t.start(interval="1MIN")
