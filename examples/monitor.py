"""
This code monitors a given stock/crypto symbol.
"""
from harvest.algo import BaseAlgo
from harvest.trader import Trader
from harvest.broker.robinhood import RobinhoodBroker

sym = 'TWTR'

class Watch(algo.BaseAlgo):

    def setup(self):
        pass
    
    def main(self, meta):
        print( self.get_price() )

if __name__ == "__main__":
    t = trader.TestTrader( RobinhoodBroker() )
    t.add_ticker(sym)
    t.set_algo(Watch())
    
    t.start()