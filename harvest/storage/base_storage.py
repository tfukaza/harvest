from numpy import ERR_CALL
import pandas as pd
import datetime as dt
from threading import Lock
from typing import Tuple
import re

from harvest.utils import *

"""
This module serves as a basic storage system for pandas dataframes in memory.
It is made to be a simplistic interface for the trader class to store various data,
such as stock price history and transaction history of the algorithm.

All implementations of Storage class must store the following data:
- Stock price history: Database of stock prices
    - Symbol: Stock symbol
    - Interval: Interval of the stock price
    - Date: Date of the price, adjusted to UTC timezone
    - Open: Opening price
    - High: Highest price
    - Low: Lowest price
    - Close: Closing price
- Transaction history: Database of *filled* orders
    - Symbol: Symbol of the stock
    - Timestamp: Date of the transaction, adjusted to UTC timezone
    - Algorithm name: Name of the algorithm that made the transaction
    - Side: Buy or sell
    - Quantity: Number of shares
    - Price: Price per share

The exact implementation of these databases is up to the classes that inherit from BaseStorage,
as long as they implement the API properly.
"""

class BaseStorage:
    """
    A basic storage that is thread safe and stores data in memory.
    """

    def __init__(
            self, 
            price_storage_size: int = 200, 
            price_storage_limit: bool = True,
            transaction_storage_size: int = 200,
            transaction_storage_limit: bool = True
        ):
        """
        queue_size: The maximum number of data points to store for asset price history. 
            This helps prevent the database from becoming infinitely large as time progresses.
        limit_size: Whether to limit the size of price history to queue_size. 
            This may be set to False if the storage is being used for backtesting, in which case
            you would want to store as much data as possible.
        """
        self.storage_lock = Lock()          # Lock

        self.price_storage_size = price_storage_size
        self.price_storage_limit = price_storage_limit
        self.transaction_storage_size = transaction_storage_size
        self.transaction_storage_limit = transaction_storage_limit

        # BaseStorage uses a python dictionary to store the data,
        # where key is asset symbol and value is a pandas dataframe.
        self.storage_price = {}       

        self.storage_transaction = pd.DataFrame(
            columns=["timestamp", "algorithm_name", "symbol", "side", "quantity", "price"]
        )

    def store(
        self, symbol: str, interval: Interval, data: pd.DataFrame, remove_duplicate=True
    ) -> None:
        """
        Stores the stock data in the storage dictionary.
        :symbol: a stock or crypto
        :interval: the interval between each data point, must be at least MIN_1
        :data: a pandas dataframe that has stock data and has a datetime index
        :remove_duplicate: whether to remove data with duplicate timestamps
        """
        # Do not create an entry if there is no data because it will
        # cause the data_range function to fail.
        if data.empty:
            return None

        self.storage_lock.acquire()

        if symbol in self.storage_price:
            # Handles if we already have data
            intervals = self.storage_price[symbol]
            if interval in intervals:
                try:
                    # Handles if we have stock data for the given interval
                    intervals[interval] = self._append(
                        intervals[interval], data, remove_duplicate=remove_duplicate
                    )
                    if self.price_storage_limit:
                        intervals[interval] = intervals[interval][-self.price_storage_size:]
                except:
                    raise Exception("Append Failure, case not found!")
            else:
                # Add the data as a new interval
                intervals[interval] = data
        else:
            if self.price_storage_limit:
                data = data[-self.price_storage_size :]
            if len(data) < self.price_storage_size:
                debugger.warning(
                    f"Symbol {symbol}, interval {interval} initialized with only {len(data)} data points"
                )
            # Add the data into storage
            self.storage_price[symbol] = {interval: data}

        cur_len = len(self.storage_price[symbol][interval])
        if self.price_storage_limit and cur_len > self.price_storage_size:
            # If we have more than N data points, remove the oldest data
            self.storage_price[symbol][interval] = self.storage_price[symbol][interval].iloc[
                -self.price_storage_size :
            ]

        self.storage_lock.release()


    def load(
        self,
        symbol: str,
        interval: Interval = None,
        start: dt.datetime = None,
        end: dt.datetime = None,
        slice_data=False,
    ) -> pd.DataFrame:
        """
        Loads the stock data given the symbol and interval. May return only
        a subset of the data if start and end are given.

        If the specified interval does not exist, it will attempt to generate it by
        aggregating data.
        :symbol: a stock or crypto
        :interval: the interval between each data point, must be at least MIN_1
        :start: a datetime object
        """
        self.storage_lock.acquire()

        if symbol not in self.storage_price:
            self.storage_lock.release()
            return None

        if interval is None:
            # If the interval is not given, return the data with the
            # smallest interval that has data in the range.
            intervals = [
                (interval, interval_to_timedelta(interval))
                for interval in self.storage_price[symbol]
            ]
            intervals.sort(key=lambda interval_timedelta: interval_timedelta[1])
            for interval_timedelta in intervals:
                data = self.load(symbol, interval_timedelta[0], start, end)
                if data is not None:
                    self.storage_lock.release()
                    return data
            self.storage_lock.release()
            return None

        data = self.storage_price[symbol][interval]

        if start is None and end is None:
            self.storage_lock.release()
            return data 

        # If the start and end are not defined, then set them to the
        # beginning and end of the data.
        if start is None:
            start = data.index[0]
        if end is None:
            end = data.index[-1]

        return data.loc[start:end]
    
    def store_transaction(
        self, 
        timestamp: dt.datetime,
        algorithm_name: str,
        symbol: str, 
        side: str,
        quantity: int,
        price: float
    ) -> None:
        self.storage_transaction.append(
            [timestamp, algorithm_name, symbol, side, quantity, price],
            ignore_index=True
        )
    

    def aggregate(
        self,
        symbol: str,
        base: Interval,
        target: Interval,
        remove_duplicate: bool = True,
    ):
        """
        Aggregates the stock data from the interval specified in 'from' to 'to'.
        """
        self.storage_lock.acquire()
        data = self.storage_price[symbol][base]
        self.storage_price[symbol][target] = self._append(
            self.storage_price[symbol][target], aggregate_df(data, target), remove_duplicate
        )
        cur_len = len(self.storage_price[symbol][target])
        if self.price_storage_limit and cur_len > self.price_storage_size:
            self.storage_price[symbol][target] = self.storage_price[symbol][target].iloc[
                -self.price_storage_size :
            ]
        self.storage_lock.release()


    def reset(self, symbol: str, interval: Interval):
        """
        Resets to an empty dataframe
        """
        self.storage_lock.acquire()
        self.storage_price[symbol][interval] = pd.DataFrame()
        self.storage_lock.release()


    def _append(
        self,
        current_data: pd.DataFrame,
        new_data: pd.DataFrame,
        remove_duplicate: bool = True,
    ) -> pd.DataFrame:
        """
        Appends the data as best it can with gaps in the data for weekends
        and time when no data is collected.
        :current_data: the current data that we have on the stock for
            the interval
        :new_data: data coming from the the broker's API call
        """

        new_df = current_data.append(new_data)
        if remove_duplicate:
            new_df = new_df[~new_df.index.duplicated(keep="last")].sort_index()
        return new_df
