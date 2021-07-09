# Builtins
import datetime as dt
from typing import List

# External libraries
import pandas as pd

class Queue:
    """The Queue is used by the Trader to keep track of stock and crpyto prices. 
    The Trader makes sure that the queue has the lastest prices.  
    """

    def __init__(self) -> None:
        self.queue = {} 

    def init_symbol(self, symbol: str, interval: str) -> None:
        if not symbol in self.queue:
            self.queue[symbol] = {}
        self.queue[symbol][interval] = pd.DataFrame()
        self.queue[symbol][interval + '-update'] = dt.datetime(1970, 1, 1)

    def set_symbol_interval(self, symbol: str, interval: str, df: pd.DataFrame) -> None:
        self.queue[symbol][interval] = df

    def set_symbol_interval_update(self, symbol: str, interval: str, timestamp: dt.datetime) -> None:
        self.queue[symbol][interval + '-update'] = timestamp
    
    def append_symbol_interval(self, symbol: str, interval: str, df: pd.DataFrame, chk_duplicate: bool=False) -> None:
        if self.queue[symbol][interval].empty:
            self.queue[symbol][interval] = df 
        else:
            self.queue[symbol][interval] = self.queue[symbol][interval].append(df)
            if chk_duplicate:
                self.queue[symbol][interval] = self.queue[symbol][interval][~self.queue[symbol][interval].index.duplicated(keep='last')]

    def check_valid( func ):
        def wrapper(*args, **kwargs):
            self = args[0]
            symbol = args[1]
            interval = args[2]
            ref = 'close' if len(args) < 4 else args[3]
            if symbol not in self.queue:
                Exception(f"{symbol} does not exist")
            if interval not in self.queue[symbol]:
                Exception(f"Interval {interval} does not exist for {symbol}")
            if ref not in ['open', 'high', 'low', 'close']:
                Exception(f"{ref} is not a valid reference. Choose from 'open', 'high', 'low', or 'close'")
            return func(*args, **kwargs)
        return wrapper

    @check_valid
    def get_symbol_interval(self, symbol: str, interval: str) -> pd.DataFrame:
        return self.queue[symbol][interval]
    
    @check_valid
    def get_symbol_interval_prices(self, symbol: str, interval: str, ref: str) -> List[float]:
        return self.queue[symbol][interval][symbol][ref].tolist()

    @check_valid
    def get_symbol_interval_update(self, symbol: str, interval: str) -> dt.datetime:
        return self.queue[symbol][interval + '-update']

    def get_last_symbol_interval(self, symbol:str, interval:str) -> pd.DataFrame:
        return self.get_symbol_interval(symbol, interval).iloc[[-1]]
    
    def get_last_symbol_interval_price(self, symbol:str, interval:str, ref) -> float:
        return float(self.get_symbol_interval_prices(symbol, interval, ref)[-1])

    
        
