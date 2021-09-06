import re
from os import listdir, makedirs
from os.path import isfile, join
import pandas as pd
import datetime as dt
from typing import Tuple

from harvest.storage import BaseStorage


"""
This module serves as a storage system for pandas dataframes in with csv files.
"""

class CSVStorage(BaseStorage):
    """
    An extension of the basic storage that saves data in csv files.
    """

    def __init__(self, save_dir: str='data'):
        super().__init__()
        """
        Adds a directory to save data to. Loads any data that is currently in the
        directory.
        """
        self.save_dir = save_dir

         # if the data dir does not exists, create it
        makedirs(self.save_dir, exist_ok=True)

        files = [f for f in listdir(self.save_dir) if isfile(join(self.save_dir, f))]

        for file in files:
            file_search = re.search('^([\w]+)-([\w]+).csv$', file)
            symbol, interval = file_search.group(1), file_search.group(2)
            data = pd.read_csv(join(self.save_dir, file), index_col=0, parse_dates=True)
            data.index = pd.to_datetime(data.index, unit='s')
            data.columns = pd.MultiIndex.from_product([[symbol], data.columns])
            super().store(symbol, interval, data)

    def store(self, symbol: str, interval: str, data: pd.DataFrame, remove_duplicate: bool=True) -> None:
        """
        Stores the stock data in the storage dictionary as a csv file.
        :symbol: a stock or crypto
        :interval: the interval between each data point, must be atleast
             1 minute
        :data: a pandas dataframe that has stock data and has a datetime 
            index
        """
        super().store(symbol, interval, data, remove_duplicate)

        if not data.empty:
            self.storage_lock.acquire()
            self.storage[symbol][interval][symbol].to_csv(self.save_dir + f'/{symbol}-{interval}.csv')
            self.storage_lock.release()

        