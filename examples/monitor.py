"""
This code monitors a given stock/crypto symbol.
"""
from harvest.algo import BaseAlgo
from harvest.trader import PaperTrader

class Watch(BaseAlgo):
    def config(self):
        self.watchlist = ["@BTC"]
        self.interval = "1MIN"

    def main(self):
        print(self.get_asset_price())


if __name__ == "__main__":
    t = PaperTrader()
    t.set_algo(Watch())

    t.start()
