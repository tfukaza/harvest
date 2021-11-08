import re
from os import listdir, makedirs
from os.path import isfile, join
import pandas as pd
import datetime as dt
from typing import Tuple

from harvest.storage import BaseStorage
from harvest.utils import *

"""
This module serves as a storage system for pandas dataframes in with pickle files.
"""


class PickleStorage(BaseStorage):
    """
    An extension of the basic storage that saves data in pickle files.
    """

    def __init__(
        self, save_dir: str = "data", queue_size: int = 200, limit_size: bool = True
    ):
        super().__init__(queue_size, limit_size)
        """
        Adds a directory to save data to. Loads any data that is currently in the
        directory.
        """
        self.save_dir = save_dir

        # if the data dir does not exists, create it
        makedirs(self.save_dir, exist_ok=True)

        files = [f for f in listdir(self.save_dir) if isfile(join(self.save_dir, f))]

        for file in files:
            symbol, interval = file.split("@")
            interval = interval.split(".")[0]
            if interval[0] == "-":
                interval = int(interval[1:])
            else:
                interval = interval_string_to_enum(interval)

            super().store(symbol, interval, pd.read_pickle(join(self.save_dir, file)))

    def store(
        self,
        symbol: str,
        interval: Interval,
        data: pd.DataFrame,
        remove_duplicate: bool = True,
        save_pickle: bool = True,
    ) -> None:
        """
        Stores the stock data in the storage dictionary as a pickle file.
        :symbol: a stock or crypto
        :interval: the interval between each data point, must be atleast
             1 minute
        :data: a pandas dataframe that has stock data and has a datetime
            index
        """
        super().store(symbol, interval, data, remove_duplicate)

        if not data.empty and save_pickle:
            self.storage_lock.acquire()
            self.storage_price[symbol][interval].to_pickle(
                self.save_dir + f"/{symbol}@{interval_enum_to_string(interval)}.pickle"
            )
            self.storage_lock.release()

    def open(self, symbol: str, interval: Interval):
        if isinstance(interval, Interval):
            interval = interval_enum_to_string(interval)
        name = self.save_dir + f"/{symbol}@{interval}.pickle"
        if isfile(name):
            return pd.read_pickle(name)
        else:
            return pd.DataFrame()
