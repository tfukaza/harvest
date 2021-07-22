import pandas as pd
import datetime as dt
from threading import Lock
from typing import Tuple
from logging import debug

from harvest.utils import *

"""
This module logs data for the trader. Data logged include but are
nor not limited to:
    - Buy/sell history
    - Portfolio value
    - Account equity
"""

class BaseLogger:

    def __init__(self):
        """
        Initialize a lock used to make this class thread safe since it is 
        expected that multiple users will be reading and writing to this 
        storage simultaneously.
        """
        self.storage_lock = Lock()
        self.transactions = pd.DataFrame(columns=["action", "asset_type", "symbol", "timestamp", "price"])
        #self.transactions.set_index(["timestamp"], inplace=True)

    def add_transaction(self, timestamp: dt.datetime, action: str, asset_type: str, symbol: str, price: float):
        self.storage_lock.acquire()
        self.transactions = self.transactions.append({"action": action, "asset_type": asset_type, "symbol": symbol, "price": price, "timestamp": timestamp}, ignore_index=True)
        self.storage_lock.release()

    def get_transactions(self) -> pd.DataFrame:
        return self.transactions

    def get_last_transaction(self):
        if self.transactions.empty:
            return None
        return self.transactions.iloc[-1]