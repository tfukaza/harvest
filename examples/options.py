# HARVEST_SKIP
import datetime as dt

from harvest.algo import BaseAlgo
from harvest.broker.robinhood import RobinhoodBroker
from harvest.trader import Trader

"""This algorithm trades options every 5 minutes.
To keep things simple, the logic is very basic, with emphasis on
introducing option-related functions.
"""


class Option(BaseAlgo):
    def config(self):
        self.watchlist = ["SPY"]
        self.interval = "5MIN"

    def setup(self):
        self.hold = False
        self.occ = ""
        self.buy_qty = 0

    def main(self):
        price = self.get_asset_price()

        if not self.hold:
            self.eval_buy(price)
        else:
            opt_price = self.get_option_market_data(self.occ)["price"]
            print(f"SELL: {self.occ}, {opt_price}")
            # Sell all options
            self.sell_option(self.occ)
            self.hold = False

    def eval_buy(self, price):
        # Get the expiration dates for this stock's option chain
        dates = self.get_chain_info("TWTR")["exp_dates"]
        # Sort so the earliest expiration date is first
        dates.sort()
        # Filter out expiration dates that within 5 days (since they are VERY risky)
        dates = filter(lambda x: x > self.timestamp.date() + dt.timedelta(days=5), dates)
        # Get the option chain
        chain = self.get_option_chain("TWTR", dates[0])
        # Strike price should be greater than current price
        chain = chain[chain["strike"] > price]
        # Only get calls
        chain = chain[chain["type"] == "call"]
        # Sort by strike price and expiration date
        chain = chain.sort_values(by=["strike", "exp_date"])
        # Get the option with lowest strike price and the closest expiration date
        opt = chain.iloc[[0]]
        # Get the OCC symbol of the option. For details on OCC format, visit
        # https://en.wikipedia.org/wiki/Option_symbol
        occ = opt.index[0]

        self.occ = occ

        # Buy as many options as possible
        self.buy_option(occ)
        print(f"BUY: {occ}")

        self.hold = True


if __name__ == "__main__":
    t = Trader(RobinhoodBroker())
    t.set_algo(Option())

    t.start()
