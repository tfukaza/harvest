# Builtins
import datetime as dt
import random
from typing import Any, Dict, List, Tuple
from logging import critical, error, info, warning, debug

# External libraries
import pandas as pd

# Submodule imports
from harvest.api._base import API
from harvest.utils import *

class DummyStreamer(API):
    """DummyStreamer, as its name implies, is a dummy broker class that can 
    be useful for testing algorithms. When used as a streamer, it will return
    randomly generated prices. 
    """

    interval_list = ['1MIN', '5MIN', '15MIN', '30MIN', '1HR', '1DAY']

    def __init__(self, path: str=None):
        self.trader = None

    def setup(self, watch: List[str], interval, trader=None, trader_main=None):
        super().setup(watch, interval, interval, trader, trader_main)

    def main(self):
        df_dict = {}
        df_dict.update(self.fetch_latest_stock_price())
        df_dict.update(self.fetch_latest_crypto_price())
      
        self.trader_main(df_dict)
    
    def fetch_latest_stock_price(self) -> Dict[str, pd.DataFrame]:
        """
        Gets fake stock data in the last three day interval and  returns the last 
        value. The reason the last three days are needed is because no data is returned
        when the stock market is closed, e.g. weekends.
        """

        results = {}
        today = now()
        last = today - dt.timedelta(days=3)
        
        for symbol in self.watch:
            if not is_crypto(symbol):
                results[symbol] = self.fetch_price_history(symbol, self.interval, last, today).iloc[[-1]]
        return results
        
    def fetch_latest_crypto_price(self) -> Dict[str, pd.DataFrame]:
        """
        Gets fake crypto data in the last three day interval and  returns the last 
        value. The reason the last three days are needed is because no data is returned
        when the stock market is closed, e.g. weekends.
        """

        results = {}
        today = dt.datetime.now()
        last = today - dt.timedelta(days=3)
        for symbol in self.watch:
            if is_crypto(symbol):
                results[symbol] = self.fetch_price_history(symbol, self.interval, last, today).iloc[[-1]]
        return results

    def _generate_fake_stock_data(self):
        """
        Generates fake open, close, low, high, and volume data points for stock and crypto data.
        Each data point is dependent on the previous one and there is no bias to whether the
        stock will go up or down over time.
        """

        open_s = random.uniform(2, 1000)
        volume = random.randint(1, 1e7)

        while True: 
            open_s = max(open_s + random.uniform(-1, 1), 0.001)
            close = open_s + random.uniform(-1, 1)
            low = max(min(open_s, close) - random.uniform(0.001, 1), 0)
            high = max(open_s, close) + random.uniform(0.001, 1)
            volume = max(volume + random.randint(-5, 5), 1)  
            yield open_s, high, low, close, volume

    # -------------- Streamer methods -------------- #

    def fetch_price_history(self,
        symbol: str,
        interval: str,
        start: dt.datetime=None, 
        end: dt.datetime=None
        ) -> pd.DataFrame:

        if start is None:  
            if interval in ['1MIN', '5MIN', '15MIN', '30MIN']:
                start = now() - dt.timedelta(days=7)
            elif interval == '1HR':
                start = now() - dt.timedelta(days=31)
            else:
                start = now() - dt.timedelta(days=365)
        if end is None:
            end = now()

        value, unit = expand_interval(interval)
        if unit == 'MIN':
            interval = dt.timedelta(minutes=int(value))
        elif unit == 'HR':
            interval = dt.timedelta(hours=int(value))
        elif unit == 'DAY':
            interval = dt.timedelta(days=int(value))
        else:
            error(f'Interval unit was {unit} not MIN, HR, or DAY!')

        times = []
        current = start

        stock_gen = self._generate_fake_stock_data()
        open_s = []
        high = []
        low = []
        close = []
        volume = []

        # Fake the data 
        while current < end + interval:
            times.append(current)
            current += interval

            o, h, l, c, v = next(stock_gen)
            open_s.append(o)
            high.append(h)
            low.append(l)
            close.append(c)
            volume.append(v)         

        d = {
            'timestamp': times,
            'open': open_s,
            'high': high,
            'low': low, 
            'close': close,
            'volume': volume
        }

        results = pd.DataFrame(data=d).set_index('timestamp')
        open_time = dt.time(hour=13, minute=30)
        close_time = dt.time(hour=20)

        results.index = times
        results.index.rename('timestamp', inplace=True)

        # Removes datapoints when the stock marked is closed. Does not handle holidays.
        results = results.loc[(open_time < results.index.time) & (results.index.time < close_time)]
        results = results[(results.index.dayofweek != 5) & (results.index.dayofweek != 6)]

        results.columns = pd.MultiIndex.from_product([[symbol], results.columns])

        return results
    
    # TODO: Generate dummy option data
    def fetch_chain_info(self, symbol: str):
        raise Exception("Not implemented")
    
    def fetch_chain_data(self, symbol: str):
        raise Exception("Not implemented")
    
    def fetch_option_market_data(self, symbol: str):
        # This is a placeholder so Trader doesn't crash
        price = random.uniform(2, 1000)
        return {
            'price': price,
            'ask': price, 
            'bid': price,
        }

    # ------------- Broker methods ------------- #

    def fetch_stock_positions(self) -> List[Dict[str, Any]]:
        raise Exception("Not implemented")

    def fetch_option_positions(self) -> List[Dict[str, Any]]:
        raise Exception("Not implemented")

    def fetch_crypto_positions(self) -> List[Dict[str, Any]]:
        raise Exception("Not implemented")
    
    def update_option_positions(self, positions) -> List[Dict[str, Any]]:
        raise Exception("Not implemented")

    def fetch_account(self) -> Dict[str, Any]:
        raise Exception("Not implemented")
    
    def fetch_stock_order_status(self, id: int) -> Dict[str, Any]:
        raise Exception("Not implemented")

    def fetch_option_order_status(self, id: int) -> Dict[str, Any]:
        raise Exception("Not implemented")

    def fetch_crypto_order_status(self, id: int) -> Dict[str, Any]:
        raise Exception("Not implemented")
    
    def fetch_order_queue(self) -> List[Dict[str, Any]]:
        raise Exception("Not implemented")

