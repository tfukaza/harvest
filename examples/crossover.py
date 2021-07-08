from harvest.algo import BaseAlgo
from harvest.trader import Trader
from harvest.broker.robinhood import RobinhoodBroker

class Crossover(BaseAlgo):

    def setup(self):
        pass
    
    def main(self, _):
        sma_short = self.sma(period=20)
        sma_long = self.sma(period=50)
        if self.crossover(sma_long, sma_short):
            self.buy(quantity=1)
        elif self.crossover(sma_short, sma_long):
            self.sell(quantity=1)

if __name__ == "__main__":
    t = Trader( RobinhoodBroker() )
    t.set_symbol('SPY')
    t.set_algo(Crossover()) 
    t.start()