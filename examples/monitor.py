"""
This code monitors a given stock/crypto symbol.
"""
from harvest.algo import BaseAlgo
from harvest.trader import Trader
from harvest.api.robinhood import Robinhood

class Watch(BaseAlgo):

    def config(self):
        self.watchlist = ['@BTC']
        self.interval = "1MIN"

    def main(self):
        print(self.get_asset_price())

if __name__ == "__main__":
    t = Trader(Robinhood())
    t.set_algo(Watch())

    t.start()
