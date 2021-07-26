# Builtins
import datetime as dt
from typing import Any, Dict, List, Tuple
from logging import critical, error, info, warning, debug

# External libraries
import pytz
import pandas as pd
import numpy as np

# Submodule imports
from harvest.api._base import API
from harvest.utils import *

class DummyStreamer(API):
    """DummyStreamer, as its name implies, is a dummy broker class that can 
    be useful for testing algorithms. When used as a streamer, it will return
    randomly generated prices. 
    """

    interval_list = ['1MIN', '5MIN', '15MIN', '30MIN', '1HR', '1DAY']
    default_now = dt.datetime(year=2021, month=7, day=19, hour=13, minute=30)

    def __init__(self, path: str=None, now: dt.datetime=default_now):
        self.trader = None

        self._set_now(now)
        self.interval = self.interval_list[0]
        self.randomness = {}

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
        today = self.now
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
        today = self.now
        last = today - dt.timedelta(days=3)
        for symbol in self.watch:
            if is_crypto(symbol):
                results[symbol] = self.fetch_price_history(symbol, self.interval, last, today).iloc[[-1]]
        return results


    # def _generate_fake_stock_data(self):
    #     """
    #     Generates fake open, close, low, high, and volume data points for stock and crypto data.
    #     Each data point is dependent on the previous one and there is no bias to whether the
    #     stock will go up or down over time. Uses a seed and timestamp to make the PRNG predictable.
    #     """

    #     open_s = random.uniform(2, 1000)
    #     volume = random.randint(1, 1e7)

    #     while True: 
    #         open_s = max(open_s + random.uniform(-1, 1), 0.001)
    #         close = open_s + random.uniform(-1, 1)
    #         low = max(min(open_s, close) - random.uniform(0.001, 1), 0)
    #         high = max(open_s, close) + random.uniform(0.001, 1)
    #         volume = max(volume + random.randint(-5, 5), 1)  
    #         yield open_s, high, low, close, volume

    def _set_now(self, current_datetime: dt.datetime) -> None:
        self.now = pytz.utc.localize(current_datetime)

    def _tick(self) -> None:
        self.now += interval_to_timedelta(self.interval)

    # -------------- Streamer methods -------------- #

    def fetch_price_history(self,
        symbol: str,
        interval: str,
        start: dt.datetime=None, 
        end: dt.datetime=None
        ) -> pd.DataFrame:

        if start is None:  
            if interval in ['1MIN', '5MIN', '15MIN', '30MIN']:
                start = self.now - dt.timedelta(days=7)
            elif interval == '1HR':
                start = self.now - dt.timedelta(days=31)
            else:
                start = self.now - dt.timedelta(days=365)
        if end is None:
            end = self.now

        start_index = int((start - epoch_zero()).total_seconds() // 60)
        end_index = 1 + int((end - epoch_zero()).total_seconds() // 60)

        if symbol in self.randomness:
            num_of_random = 1 + end_index

            if len(self.randomness[symbol]) < num_of_random:
                rng = self.randomness[symbol + '_rng']
                increments = rng(num_of_random - len(self.randomness[symbol]))
                latest_price_change = self.randomness[symbol][-1]
                new_price_changes = latest_price_change + np.cumsum(increments)
                self.randomness[symbol] = np.append(self.randomness[symbol], new_price_changes)
            
        else:
            rng = np.random.default_rng(int.from_bytes(symbol.encode('ascii'), 'big'))
            num_of_random = 1 + end_index
            increments = rng.random(num_of_random) - 0.5
            self.randomness[symbol] = np.cumsum(increments)
            self.randomness[symbol + '_rng'] = rng

        start_price = 100 * (self.randomness[symbol][0] + 0.51)     

        times = []
        current_time = start

        prices = start_price + self.randomness[symbol][start_index:end_index]
        prices[prices < 0] = 0.01

        open_s = 0.95 * prices
        low = 0.8 * prices 
        high = 1.2 * prices 
        close = 1.05 * prices 
        volume = (1000 * (prices + 20)).astype(int)


        # Fake the data 
        while current_time <= end:
            times.append(current_time)
            current_time += dt.timedelta(minutes=1)

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

        # Removes datapoints when the stock marked is closed. Does not handle holidays.
        results = results.loc[(open_time < results.index.time) & (results.index.time < close_time)]
        results = results[(results.index.dayofweek != 5) & (results.index.dayofweek != 6)]
        
        results.columns = pd.MultiIndex.from_product([[symbol], results.columns])
        results = aggregate_df(results, interval)

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

