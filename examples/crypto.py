from harvest.algo import BaseAlgo
from harvest.trader import Trader
from harvest.broker.robinhood import RobinhoodBroker

"""This algorithm trades everyone's favorite cryptocurrency, Dogecoin. 
It also demonstrates some built-in functions.
"""

# Constants
N=3

class Crypto(BaseAlgo):
    
    def setup(self):
        self.hold = False
        self.ret = 0
        self.cutoff = 0.0
    
    def main(self, _):
        
        # Get the current time as a datetime object
        self.timestamp = self.get_datetime()

        # Get a list of price history for Dogecoin
        # When a symbol is not specified, it defaults to the first symbol on 
        # our watchlist (DOGE)
        # If an interval is not specified, it defaults to the interval of the algorithm (30MIN)
        prices = self.get_price_list()
        # Get the price history as a pandas Dataframe
        candles = self.get_candle_list()

        # Get the Bollinger Band based on Dogecoin prices, at 30MIN intervals
        top_s, avg_s, btm_s = self.bbands(period=8, dev=0.8)
        top_l, avg_l, btm_l = self.bbands(period=8, dev=1.6)

        candles = candles[-N:]
        prices = prices[-N:]
        top_s = top_s[-N:]
        avg_s = avg_s[-N:]
        btm_s = btm_s[-N:]
        top_l = top_l[-N:]
        avg_l = avg_l[-N:]
        btm_l = btm_l[-N:]

        trends = []
        for i in range(N):
            price = prices[i]
            if price > top_s[i]:
                if price > top_l[i]:
                    trends.append(2)
                else:
                    trends.append(1)
            elif price < btm_s[i]:
                if price < btm_l[i]:
                    trends.append(-2)
                else:
                    trends.append(-1)
            else:
                trends.append(0)

        if not self.hold:
            if self.buy_eval(trends, prices, candles):
                print(f"BUY: {self.timestamp}, {sym}, {prices[-1]}")
                # Get how much Dogecoin we can buy
                buy_qty = self.get_max_quantity(round=False)
                self.buy_qty = buy_qty
                # Buy the coins
                self.buy(quantity=buy_qty)

                self.hold = True
                self.cutoff = 0.0
            else:
                print("Wait")

        elif self.hold:
            # Get how much returns you have made in Dogecoin so far
            ret = self.get_returns()
            if self.sell_eval(ret):
                print(f"SELL: {self.timestamp}, {sym}, {prices[-1]}")
                # Sell Dogecoin
                self.sell(sym, self.buy_qty)
                self.hold = False
            else:
                print(f"HOLD: {ret}")
        
            if ret > self.cutoff:
                self.cutoff = int(ret*100)/100.0 + 0.01
            

    def buy_eval(self, trends, prices, candles):
        c = bool(trends[-1] > 0 and candles['open'][-1] < candles['close'][-1])
        return c
    
    def sell_eval(self, ret):
        c = bool(ret > self.cutoff+0.02 or ret < self.cutoff-0.001)
        return c
       
if __name__ == "__main__":
    t = Trader( RobinhoodBroker())
    t.set_symbol('@DOGE')   # Cryptocurrencies are prepended with an '@'
    t.set_algo(Crypto())
    
    t.start(interval='30MIN') # Run the algorithm once every 30 minutes