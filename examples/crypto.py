from harvest.algo import BaseAlgo
from harvest.trader import Trader
from harvest.broker.robinhood import RobinhoodBroker

import datetime as dt

"""This algorithm trades everyone's favorite cryptocurrency, Dogecoin. 
It also demonstrates some built-in functions such as self.sma() and self.bbands()
"""

sym = '@DOGE'   # Crypto assets must start with an '@'
inter='30MIN'   # Interval to run the algorithm
# Constants
N_r=3

class Crypto(BaseAlgo):
    
    def setupt(self):
        self.hold = False
        self.ret = 0
        self.cutoff = 0.0
    
    def main(self, meta):
        
        # Get the current time as a datetime object
        self.timestamp = self.get_datetime()

        # Get a list of price history for Dogecoin, at 30MIN intervals
        prices = self.get_price_list(sym, interval=inter)
        # Get the price history as a pandas Dataframe
        candles = self.get_candle_list(sym, interval=inter)

        if len(prices) < N_r:
            return

        # Get the Bollinger Band based on Dogecoin prices, at 30MIN intervals
        top_s, avg_s, btm_s = self.bbands(symbol=sym, period=8, dev=0.8, interval=inter)
        top_l, avg_l, btm_l = self.bbands(symbol=sym, period=8, dev=1.6, interval=inter)

        candles = candles[-N_r:]
        prices = prices[-N_r:]
        top_s = top_s[-N_r:]
        avg_s = avg_s[-N_r:]
        btm_s = btm_s[-N_r:]
        top_l = top_l[-N_r:]
        avg_l = avg_l[-N_r:]
        btm_l = btm_l[-N_r:]

        trends = []
        for i in range(N_r):
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
            if  self.buy_eval(trends, prices, candles):

                print(f"BUY: {self.timestamp}, {sym}, {prices[-1]}")

                # Get how much cash is availible for trading
                buy_pwr = self.get_account_buying_power()
                price = prices[-1]
                buy_qty = int((buy_pwr/price) / 1.5)
                self.buy_qty = buy_qty

                # Buy the coins
                self.buy(sym, buy_qty)

                self.hold = True
                self.cutoff = 0.0
            else:
                print("Wait")

        elif self.hold:

            # Get how much returns you have made in Dogecoin so far
            ret = self.get_returns(sym)
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
        c = bool(trends[-1] > 0 and candles.iloc[[-1]]['open'][0] < candles.iloc[[-1]]['close'][0])
        return c
    
    def sell_eval(self, ret):
        c = bool(ret > self.cutoff+0.02 or ret < self.cutoff-0.001)
        return c
       
if __name__ == "__main__":
    t = Trader( RobinhoodBroker())
    t.set_symbol(sym)
    t.set_algo(Crypto())
    
    t.start(interval=inter)