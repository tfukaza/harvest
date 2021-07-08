from harvest.algo import BaseAlgo
from harvest.trader import Trader
from harvest.broker.robinhood import RobinhoodBroker

sym = 'TWTR'

class Crossover(BaseAlgo):

    def algo_init(self):
        pass
    
    def handler(self, _):
        sma_short = self.sma(period=20)
        sma_long = self.sma(period=50)
        if self.crossover(sma_long, sma_short):
            self.buy(sym, 1)
        elif self.crossover(sma_short, sma_long):
            self.sell(sym, 1)

if __name__ == "__main__":
    t = Trader( RobinhoodBroker() )
    t.add_ticker(sym)
    t.set_algo(Crossover())
    t.run()