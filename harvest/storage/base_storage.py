import pandas as pd
import datetime as dt
from threading import Lock
from typing import Tuple
from logging import debug
import re

from harvest.utils import *


"""
This module serves as a basic storage system for pandas dataframes in memory.
It is made to be a simplistic interface for the broker to store data and to
be expanded to save data on disk either as files or in databases which child
classes. Allows for gaps in data longer that the set interval for cases such
as the gap between the last stock data for a day and the first stock data for
the following day.
"""

class BaseStorage:
    """
    A basic storage that is thread safe and stores data in memory.
    """

    def __init__(self, N: int=200, limit_size: bool=True):
        """
        Initialize a lock used to make this class thread safe since it is 
        expected that multiple users will be reading and writing to this 
        storage simultaneously.
        """
        self.storage_lock = Lock()
        self.storage = {}
        self.N = N
        self.limit_size = limit_size

    def store(self, symbol: str, interval: str, data: pd.DataFrame, remove_duplicate=True) -> None:
        """
        Stores the stock data in the storage dictionary.
        :symbol: a stock or crypto
        :interval: the interval between each data point, must be at least
             1 minute
        :data: a pandas dataframe that has stock data and has a datetime 
            index
        """

        if data.empty:
            # Do not create an entry if there is no data because it will 
            # cause the data_range function to error.
            return None

        # Removes the seconds and milliseconds
        data.index = normalize_pandas_dt_index(data)

        self.storage_lock.acquire()

        if symbol in self.storage:
            # Handles if we already have stock data
            intervals = self.storage[symbol]
            if interval in intervals:
                try:
                    # Handles if we have stock data for the given interval
                    intervals[interval] = self._append(intervals[interval], data, remove_duplicate=remove_duplicate)
                except:
                    raise Exception('Append Failure, case not found!')
            else:
                # Add the data as a new interval
                intervals[interval] = data
        else:
            # Just add the data into storage
            self.storage[symbol] = {
                interval: data
            }

        cur_len = len(self.storage[symbol][interval])
        if self.limit_size and cur_len > self.N:
            # If we have more than N data points, remove the oldest data
            self.storage[symbol][interval] = self.storage[symbol][interval].iloc[-self.N:]

        self.storage_lock.release()

    def aggregate(self, symbol: str, base: str, target: str, remove_duplicate: bool=True):
        """
        Aggregates the stock data from the interval specified in 'from' to 'to'.

        """
        self.storage_lock.acquire()
        data = self.storage[symbol][base]
        self.storage[symbol][target] = self._append(self.storage[symbol][target], aggregate_df(data, target), remove_duplicate)
        cur_len = len(self.storage[symbol][target])
        if self.limit_size and cur_len > self.N:
            self.storage[symbol][target] = self.storage[symbol][target].iloc[-self.N:]
        self.storage_lock.release()
    
    def reset(self, symbol: str, interval: str):
        """
        Resets to an empty dataframe
        """
        self.storage_lock.acquire()
        self.storage[symbol][interval] = pd.DataFrame()
        self.storage_lock.release()


    def load(self, symbol: str, interval: str='', start: dt.datetime=None, end: dt.datetime=None, no_slice=False) -> pd.DataFrame:
        """
        Loads the stock data given the symbol and interval. May return only
        a subset of the data if start and end are given and there is a gap 
        between the last data point and the given end datetime.

        If the specified interval does not exist, it will attempt to generate it by
        aggregating data. 
        :symbol: a stock or crypto
        :interval: the interval between each data point, must be at least
             1 minute
        :start: a datetime object 
        """
        self.storage_lock.acquire()

        if symbol not in self.storage:
            self.storage_lock.release()
            return None 

        self.storage_lock.release()

        if interval == '':
            # If the interval is not given, return the data with the 
            # smallest interval that has data in the range.
            intervals = [(interval, interval_to_timedelta(interval)) for interval in self.storage[symbol].keys()]
            intervals.sort(key=lambda interval_timedelta: interval_timedelta[1])
            for interval_timedelta in intervals:
                data = self.load(symbol, interval_timedelta[0], start, end)
                if not data is None:
                    return data 
            return None

        dt_interval = interval_to_timedelta(interval)

        self.storage_lock.acquire()
        if interval not in self.storage[symbol]:
            # If we don't have the given interval but we a smaller one,
            # then aggregate the data
            intervals = [(interval, interval_to_timedelta(interval)) for interval in self.storage[symbol].keys() if interval_to_timedelta(interval) < dt_interval] 
            if len(intervals) == 0:
                self.storage_lock.release()
                return None

            data = self.storage[symbol][intervals[-1][0]]
            data = aggregate_df(data, interval)
        else:
            data = self.storage[symbol][interval]
        self.storage_lock.release()
    
        if no_slice:
            return data

        # If the start and end are not defined, then set them to the 
        # beginning and end of the data.
        if start is None:
            start = data.index[0]
        if end is None:
            end = data.index[-1]

        return data.loc[start:end]

    def data_range(self, symbol: str, interval: str) -> Tuple[dt.datetime]:
        """
        Returns the oldest and latest datetime of a particular symbol.
        :symbol: a stock or crypto
        :interval: the interval between each data point, must be atleast
             1 minute
        """
        data = self.load(symbol, interval)
        if data is None:
            return None, None
        return data.index[0], data.index[-1]

    def _append(self, current_data: pd.DataFrame, new_data: pd.DataFrame, remove_duplicate: bool=True) -> pd.DataFrame:
        """
        Appends the data as best it can with gaps in the data for weekends 
        and time when no data is collected. 
        :current_data: the current data that we have on the stock for 
            the interval
        :new_data: data coming from the the broker's API call
        """

        new_df = current_data.append(new_data)
        if remove_duplicate:
            new_df = new_df[~new_df.index.duplicated(keep='last')].sort_index()
        return new_df