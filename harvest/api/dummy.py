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
    default_now = dt.datetime(year=2000, month=1, day=1, hour=0, minute=0)

    def __init__(self, path: str=None, now: dt.datetime=default_now, realistic_times: bool=False):
        self.trader = None
        self.trader_main = None
        self.realistic_times = realistic_times

        # Set the current time
        self._set_now(now)
        # Used so `fetch_price_history` can work without running `setup`
        self.interval = self.interval_list[0]
        # Store random values and generates for each asset tot make `fetch_price_history` fixed
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

    # -------------- Streamer methods -------------- #

    def fetch_price_history(self,
        symbol: str,
        interval: str,
        start: dt.datetime=None, 
        end: dt.datetime=None
        ) -> pd.DataFrame:

        if start is None:  
            if interval in ['1MIN', '5MIN', '15MIN', '30MIN']:
                start = self.now - dt.timedelta(days=2)
            elif interval == '1HR':
                start = self.now - dt.timedelta(days=14)
            else:
                start = self.now - dt.timedelta(days=365)

        if end is None:
            end = self.now

        if start.tzinfo is None or start.tzinfo.utcoffset(start) is None:
            start = pytz.utc.localize(start)

        if end.tzinfo is None or end.tzinfo.utcoffset(end) is None:
            end = pytz.utc.localize(end)

        # Convert datetime to indices
        start_index = int((start - epoch_zero()).total_seconds() // 60)
        end_index = 1 + int((end - epoch_zero()).total_seconds() // 60)

        if symbol in self.randomness:
            # If we already generated data from this asset

            num_of_random = 1 + end_index

            if len(self.randomness[symbol]) < num_of_random:
                # If the new end index is greater than the data we have

                # Get the rng for this symbol
                rng = self.randomness[symbol + '_rng'] 

                # Generate a bunch of random numbers from -0.5 to 0.5
                increments = rng.random(num_of_random - len(self.randomness[symbol])) - 0.499

                # Get sum of the previous price changes
                latest_price_change = self.randomness[symbol][-1]

                # Calculate the change in price since the first price
                new_price_changes = latest_price_change + np.cumsum(increments) 

                # Store the new prices
                self.randomness[symbol] = np.append(self.randomness[symbol], new_price_changes)
            
        else:
            # If there is no information about the asset 

            # Create an rng using the asset's symbol as a seed
            rng = np.random.default_rng(int.from_bytes(symbol.encode('ascii'), 'big'))
            num_of_random = 1 + end_index
            increments = rng.random(num_of_random) - 0.499

            # Store the price change since the first price
            self.randomness[symbol] = np.cumsum(increments)
            self.randomness[symbol + '_rng'] = rng

        # The inital price is arbitarly calculated from the first change in price
        start_price = 1000 * (self.randomness[symbol][0] + 0.51)     

        times = []
        current_time = start

        # Get the prices for the current interval
        prices = start_price + self.randomness[symbol][start_index:end_index]
        # Prevent prices from going negative
        prices[prices < 0] = 0.01

        # Calculate olhcv from the prices
        open_s = 0.95 * prices
        low = 0.8 * prices 
        high = 1.2 * prices 
        close = 1.05 * prices 
        volume = (1000 * (prices + 20)).astype(int)


        # Fake the timestamps 
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

        if self.realistic_times:
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
        price = float(hash((symbol, self.now))) / (2**64)
        price = (price+1) * 1.5
        return {
            'price': price,
            'ask': price*1.05, 
            'bid': price*0.95,
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

    # ------------- Helper methods ------------- #

    def _set_now(self, current_datetime: dt.datetime) -> None:
        if current_datetime.tzinfo is None or current_datetime.tzinfo.utcoffset(current_datetime) is None:
            self.now = pytz.utc.localize(current_datetime)
        else: 
            self.now = current_datetime

    def tick(self) -> None:
        self.now += interval_to_timedelta(self.interval)
        if not self.trader_main == None:
            self.main()