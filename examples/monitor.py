"""
This code monitors a given stock/crypto symbol.
"""
from harvest.algo import BaseAlgo
from harvest.trader import Trader
from harvest.api.robinhood import Robinhood

class Watch(BaseAlgo):
    def main(self, meta):
        print( self.get_asset_price() )

if __name__ == "__main__":
    t = Trader( Robinhood() )
    t.set_symbol('@BTC')
    t.set_algo(Watch())

    t.start('1MIN')