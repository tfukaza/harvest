# Builtins
from datetime import timedelta
import datetime as dt
from logging import critical, error, info, warning, debug
from typing import Any, List, Tuple 

# External libraries
from finta import TA
import numpy as np
import pandas as pd

class BaseAlgo:
    """The Algo class is where the algorithm resides. 
    It provides an interface to monitor stocks and place orders. 
    Helper functions are also provided for common calculations such as RSI and SMA.  
    """

    def __init__(self):
        self.watch=[]

    def setup(self, trader) -> None:
        self.trader = trader

    def algo_init(self):
        pass

    def handler(self, meta = {}):
        pass

    ############ Functions to configure the algo #################

    def add_symbol(self, symbol: str) -> None:
        self.watch.append(symbol)
    
    def remove_symbol(self, symbol: str) -> None:
        self.watch.remove(symbol)
    
    ############ Functions interfacing with broker #################

    def buy(self, *args, **kwargs):
        """Buys the sepcified asset.

        :symbol:    Symbol of the asset to buy
        :quantity:  Quantity of asset to buy
        :in_force:  Duration the order is in force
        :extended:  Whether to trade in extended hours or not. 

        :returns: A dictionary with the following keys:
            - type: 'STOCK' or 'CRYPTO'
            - id: ID of order
            - symbol: symbol of asset
            Raises an exception if order fails. 
        """
        return self.trader.buy(*args, **kwargs)
    
    def sell(self, *args, **kwargs):
        """Sells the sepcified asset.

        :symbol:    Symbol of the asset to buy
        :quantity:  Quantity of asset to buy
        :in_force:  Duration the order is in force
        :extended:  Whether to trade in extended hours or not. 

        :returns: A dictionary with the following keys:
            - type: 'STOCK' or 'CRYPTO'
            - id: ID of order
            - symbol: symbol of asset
            Raises an exception if order fails. 
        """
        return self.trader.sell(*args, **kwargs)

    def await_buy(self, *args, **kwargs):
        """Buys the specified asset, and hangs the code until the order is filled. 

        :symbol:    Symbol of the asset to buy
        :quantity:  Quantity of asset to buy
        :in_force:  Duration the order is in force
        :extended:  Whether to trade in extended hours or not. 

        :returns: A dictionary with the following keys:
            - type: 'STOCK' or 'CRYPTO'
            - id: ID of order
            - symbol: symbol of asset
            Raises an exception if order fails. 
        """
        return self.trader.await_buy(*args, **kwargs)
    
    def await_sell(self, *args, **kwargs):
        """Sells the specified asset, and hangs the code until the order is filled. 

        :symbol:    Symbol of the asset to buy
        :quantity:  Quantity of asset to buy
        :in_force:  Duration the order is in force
        :extended:  Whether to trade in extended hours or not. 

        :returns: A dictionary with the following keys:
            - type: 'STOCK' or 'CRYPTO'
            - id: ID of order
            - symbol: symbol of asset
            Raises an exception if order fails. 
        """
        return self.trader.await_sell(*args, **kwargs)

    def buy_option(self, *args, **kwargs):
        """Buys the sepcified option.
        
        :symbol:    Symbol of the asset to buy, in OCC format. 
        :quantity:  Quantity of asset to buy
        :in_force:  Duration the order is in force

        :returns: A dictionary with the following keys:
            - type: 'OPTION'
            - id: ID of order
            - symbol: symbol of asset
            Raises an exception if order fails. 
        """
        return self.trader.buy_option(*args, **kwargs)
    
    def sell_option(self, *args, **kwargs):
        """Sells the sepcified option.
        
        :symbol:    Symbol of the asset to buy, in OCC format. 
        :quantity:  Quantity of asset to buy
        :in_force:  Duration the order is in force

        :returns: A dictionary with the following keys:
            - type: 'OPTION'
            - id: ID of order
            - symbol: symbol of asset
            Raises an exception if order fails. 
        """
        return self.trader.sell_option(*args, **kwargs)
    
    ########### Functions to trade options #################

    def get_chain_info(self, symbol: str):
        """Returns information about the symbol's options
        
        :symbol: symbol of stock
        :returns: A dict with the following keys:
            - id: ID of the option chain 
            - exp_dates: List of expiration dates, in the fomrat "YYYY-MM-DD" 
            - multiplier: Multiplier of the option, usually 100 
        """ 
        return self.trader.fetch_chain_info(symbol)
    
    def get_chain_data(self, symbol: str):
        """Returns the option chain for the specified symbol. 
        
        :symbol: symbol of stock
        :returns: A dataframe in the following format:

                    exp_date strike  type    id
            OCC
            ---     ---      ---     ---     ---     
        - OCC: the chain symbol in OCC format
        """ 
        return self.trader.fetch_chain_data(symbol)
    
    def get_option_market_data(self, symbol: str):
        """Retrieves data of specified option. 

        :symbol: Occ symbol of option
        :returns: A dictionary:
            - price: price of option 
            - ask: ask price
            - bid: bid price
            }
        """ 
        return self.trader.fetch_option_market_data(symbol)
    
    ########## Technical Indicaters ###############

    def rsi(self, symbol: str=None, period: int=14, interval: str='5MIN', ref: str='close') -> np.array:
        """Calculate RSI

        :symbol:    Symbol to perform calculation on 
        :period:    Period of RSI
        :interval:  Interval to perform the calculation
        :ref:       'close', 'open', 'high', or 'low'
        :returns: A list in numpy format, containing RSI values
        """
        if symbol == None:
            symbol = self.watch[0]
        prices = self.trader.queue.get_symbol_interval_prices(symbol, interval, ref)
        ohlc = pd.DataFrame({
            'close': np.array(prices),
            'open': np.zeros(len(prices)),
            'high': np.zeros(len(prices)),
            'low': np.zeros(len(prices)),
        })
        rsi = TA.RSI(ohlc, period=period).to_numpy()
        return rsi
    
    def sma(self, symbol: str=None, period: int=14, interval: str='5MIN', ref: str='close') -> np.array:
        """Calculate SMA

        :symbol:    Symbol to perform calculation on 
        :period:    Period of SMA
        :interval:  Interval to perform the calculation
        :ref:       'close', 'open', 'high', or 'low'
        :returns: A list in numpy format, containing SMA values
        """
        if symbol == None:
            symbol = self.watch[0]
        prices = self.trader.queue.get_symbol_interval_prices(symbol, interval, ref)
        ohlc = pd.DataFrame({
            'close': np.array(prices),
            'open': np.zeros(len(prices)),
            'high': np.zeros(len(prices)),
            'low': np.zeros(len(prices)),
        })
        sma = TA.SMA(ohlc, period=period).to_numpy()
        return sma
    
    def ema(self, symbol: str=None, period: int=14, interval: str='5MIN', ref: str='close') -> np.array:
        """Calculate EMA

        :symbol:    Symbol to perform calculation on 
        :period:    Period of EMA
        :interval:  Interval to perform the calculation
        :ref:       'close', 'open', 'high', or 'low'
        :returns: A list in numpy format, containing EMA values
        """
        if symbol == None:
            symbol = self.watch[0]
        prices = self.trader.queue.get_symbol_interval_prices(symbol, interval, ref)
        ohlc = pd.DataFrame({
            'close': np.array(prices),
            'open': np.zeros(len(prices)),
            'high': np.zeros(len(prices)),
            'low': np.zeros(len(prices)),
        })
        ema = TA.EMA(ohlc, period=period).to_numpy()
        return ema
    
    def bbands(self, symbol: str=None, period: int=14, interval: str='5MIN', ref: str='close', dev: float=1.0) -> Tuple[np.array, np.array, np.array]:
        """Calculate Bollinger Bands

        :symbol:    Symbol to perform calculation on 
        :period:    Period of BBand
        :interval:  Interval to perform the calculation
        :ref:       'close', 'open', 'high', or 'low'
        :dev:       Standard deviation of the bands
        :returns: A tuple of numpy lists, each a list of BBand top, average, and bottom values
        """
        if symbol == None:
            symbol = self.watch[0]
        prices = self.trader.queue.get_symbol_interval_prices(symbol, interval, ref)
        ohlc = pd.DataFrame({
            'close': np.array(prices),
            'open': np.zeros(len(prices)),
            'high': np.zeros(len(prices)),
            'low': np.zeros(len(prices)),
        })

        t, m, b = TA.BBANDS(ohlc, period=period, std_multiplier=dev, MA=TA.SMA(ohlc, period)).T.to_numpy()
        return t, m, b
    
    def bbands_raw(self, arr: List[float]=[], period: int=14, dev: float=1.0) -> Tuple[np.array, np.array, np.array]:
        """Calculate Bollinger Bands using given data

        :arr: List of prices as float to use in calculation of bollinger band
        :symbol:    Symbol to perform calculation on 
        :period:    Period of BBand
        :interval:  Interval to perform the calculation
        :ref:       'close', 'open', 'high', or 'low'
        :dev:       Standard deviation of the bands
        :returns: A tuple of numpy lists, each a list of BBand top, average, and bottom values
        """
        ohlc = pd.DataFrame({
            'close': np.array(arr),
            'open': np.zeros(len(arr)),
            'high': np.zeros(len(arr)),
            'low': np.zeros(len(arr)),
        })
        t, m, b = TA.BBANDS(ohlc, period=period, std_multiplier=dev, MA=TA.SMA(ohlc, period)).T.to_numpy()
        return t, m, b

    ############### Getters for Trader properties #################

    def get_quantity(self, symbol: str) -> float:
        """Returns the quantity owned of a specified asset. 

        :symbol:  Symbol of asset
        :returns: Quantity of asset. 0 if asset is not owned. 
        """
        search = self.trader.stock_positions + self.trader.crypto_positions
        if not any([p['symbol'] == symbol for p in search]):
            return None
        for p in search:
            if p['symbol'] == symbol:
                return p['quantity']
    
    def get_cost(self, symbol) -> float:
        """Returns the average cost of a specified asset. 

        :symbol:  Symbol of asset
        :returns: Average cost of asset. Returns None if asset is not being tracked.
        """
        if len(symbol) <= 6:
            search = self.trader.stock_positions + self.trader.crypto_positions
            for p in search:
                if p['symbol'] == symbol:
                    return p['avg_price']
            return None
        else:
            for p in self.trader.option_positions:
                if p['occ_symbol'] == symbol:
                    return p['avg_price']

    def get_price(self, symbol: str) -> float:
        if len(symbol) <= 6:
            return self.trader.queue.get_last_symbol_interval_price(symbol, self.fetch_interval, 'close')
        else:
            for p in self.trader.option_positions:
                if p['occ_symbol'] == symbol:
                    return p['current_price']
    
    def get_candle(self, symbol: str) -> pd.DataFrame():
        if len(symbol) <= 6:
            return self.trader.queue.get_symbol_interval(symbol, self.trader.interval).iloc[[-1]][symbol]
        else:
            raise Exception("Candles not available for options")
    
    def get_candle_list(self, symbol, interval=None):
        if interval == None:
            interval = self.fetch_interval
        return self.trader.queue.get_symbol_interval(symbol, interval)[symbol]
    
    def get_returns(self, symbol) -> float:
        """Returns the return of a specified asset. 

        :symbol:  Symbol of stock, crypto, or option. Options should be in OCC format.
        :returns: Return of asset, expressed as a decimal. Returns None if asset is not owned.
        """
        cost = self.get_cost(symbol)
        price = self.get_price(symbol)
        ret = (price - cost) / cost
        return ret
    
    def get_account_buying_power(self) -> float:
        return self.trader.account['buying_power']
    
    def get_account_equity(self) -> float:
        return self.trader.account['equity']
            
    
    def get_price_list(self, symbol, interval=None, ref='close'):
        """Returns a list of recent prices for an asset. 

        :symbol:  Symbol of asset.
        :interval: Interval of data.
        :returns: Average cost of asset. Returns None if asset is not being tracked.
        """
        if interval == None:
            interval = self.fetch_interval
        return self.trader.queue.get_symbol_interval_prices(symbol, interval, ref)
    
    def get_time(self):
        return self.trader.timestamp.time()
    
    def get_date(self):
        return self.trader.timestamp.date() 

    def get_datetime(self):
        # Note that all get_time functions return the 
        # current time, not the timestamp of the data. 
        return self.trader.timestamp 

    def get_watch(self) -> List[str]:
        return self.watch
    
    
    

        
        
        

