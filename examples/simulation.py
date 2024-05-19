# HARVEST_SKIP
from harvest.algo import BaseAlgo
from harvest.trader import PaperTrader
from harvest.broker.robinhood import Robinhood
from harvest.broker.paper import PaperBroker

"""
"""

# Constants
N = 3


class Crypto(BaseAlgo):
    def config(self):
        self.watchlist = ["@ETH"]
        self.interval = "1MIN"
        self.aggregations = []

    def setup(self):
        self.buy("@ETH", 1)

    def main(self):
        print(self.get_account_crypto_positions())
        if self.get_asset_quantity() > 0:
            self.sell()
        else:
            self.buy()


if __name__ == "__main__":
    t = PaperTrader(debug=True)
    t.set_algo(Crypto())

    t.start()
