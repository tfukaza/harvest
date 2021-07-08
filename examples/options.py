from harvest.algo import BaseAlgo
from harvest.trader import Trader
from harvest.broker.robinhood import RobinhoodBroker

import datetime as dt

"""This algorithm trades options every 5 minutes.
To keep things simple, the logic is very basic, with emphasis on
introducing option-related functions.  
"""

sym = 'TWTR'

class Option(BaseAlgo):

    def setup(self):
        self.hold = False
        self.occ = ''
        self.buy_qty = 0
    
    def main(self, meta):

        price = self.get_price(sym)

        if not self.hold:
            # Get the option chain as a pandas dataframe
            chain = self.get_chain_data(sym)
            # Strike price should be greater than current price
            chain = chain[chain['strike'] > price]
            # Get calls
            chain = chain[chain['type'] == 'call']
            # Sort by strike price and expiration date
            chain = chain.sort_values(by=['strike', 'exp_date'])
            # Get the option with lowest strike price and the closest expiration date
            opt = chain.iloc[[0]]
            # Get the OCC symbol of the option. For details on OCC format, visit
            # https://en.wikipedia.org/wiki/Option_symbol
            occ = opt.index[0]
            self.occ = occ

            buy_pwr = self.get_account_buying_power()
            # Get the price of the option
            opt_price = self.get_option_market_data(occ)['price']
            buy_qty = int((buy_pwr/2)/(opt_price*100))
            self.buy_qty = buy_qty

            # Buy the option
            self.buy_option(occ, buy_qty)
            print(f"BUY: {self.timestamp}, {occ}, {opt_price}")

            self.hold = True

        elif self.hold:
            opt_price = self.get_option_market_data(self.occ)['price']
            print(f"SELL: {self.timestamp}, {self.occ}, {opt_price}")
            self.sell_option(self.occ, self.buy_qty)
            self.hold = False
            
if __name__ == "__main__":
    t = Trader( RobinhoodBroker() )
    t.set_symbol(sym)
    t.set_algo(Option())
    
    t.start(interval='5MIN')