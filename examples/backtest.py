from harvest.algo import BaseAlgo
from harvest.trader import BackTester


class BackTest(BaseAlgo):
    def main(self):
        prices = self.get_asset_price_list()
        sma_short = self.sma(period=20)
        sma_long = self.sma(period=50)

        print(f"{prices} {sma_short} {sma_long}")

        if self.crossover(sma_long, sma_short):
            self.buy(quantity=1)
        elif self.crossover(sma_short, sma_long):
            self.sell(quantity=1)


if __name__ == "__main__":
    t = BackTester()
    t.set_symbol("SPY")
    t.set_algo(BackTest())
    t.start("5MIN")
