from harvest.algo import BaseAlgo
from harvest.trader import Trader
from harvest.broker.robinhood import RobinhoodBroker
from harvest.broker.dummy import DummyBroker

class TestLive(BaseAlgo):
    
    def main(self, _):
        prices = self.get_prices()
        candles = self.get_candles()
        sma_short = self.sma(period=20)
        sma_long = self.sma(period=50)
        
        print(f"{prices} {candles} {sma_short} {sma_long}")
        
if __name__ == "__main__":
    t = Trader( RobinhoodBroker(), DummyBroker() ) # This enables paper trading
    t.set_symbol('@BTC')
    t.set_algo( TestLive() )
    
    # Run the main() function once every day
    t.start('5MIN', ['15MIN', '1DAY'])

    