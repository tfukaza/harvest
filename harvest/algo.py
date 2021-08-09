# Builtins
from datetime import timedelta, timezone
import datetime as dt
from logging import critical, error, info, warning, debug
from typing import Any, List, Tuple
import math

# External libraries
from finta import TA
import numpy as np
import pandas as pd

from harvest.utils import *
from harvest.plugin._base import Plugin

"""
Methods that perform an action should follow this naming convention:
    [action]_[target]_[returns]
    - action: The action taken by the method, such as 'get', 'buy'
    - target: The entity the method operates on, such as 'stock', 'option', 'account'
    - returns: What the method returns, such as 'list', 'price'

When dealing with dates, unlike datetime objects in other classes, 
dates in Algo class are NOT localized to UTC timezone. This keeps the 
interface easier for users, especially for beginners of Python. 
"""

class BaseAlgo:
    """
    The BaseAlgo class is where the algorithm resides. 
    It provides an interface to monitor stocks and place orders. 
    Helper functions are also provided for common calculations such as RSI and SMA.  
    """

    def __init__(self):
        self.watch = []
        self.trader = None 

    def setup(self):
        pass

    def main(self):
        pass

    def add_plugin(self, plugin: Plugin):
        value = getattr(self, plugin.name, None)
        if value is None:
            setattr(self, plugin.name, plugin)
        else:
            error(f"Plugin name is already in use! {plugin.name} points to {value}.")
    
    ############ Functions interfacing with broker through the trader #################

    def buy(self, symbol: str=None, quantity: int=None, in_force: str='gtc', extended: bool=False):
        """Buys the specified asset.

        When called, a limit buy order is placed with a limit
        price 5% higher than the current price. 

        :param str? symbol: Symbol of the asset to buy. defaults to first symbol in watchlist
        :param float? quantity: Quantity of asset to buy. defaults to buys as many as possible
        :param str? in_force: Duration the order is in force. '{gtc}' or '{gtd}'. defaults to 'gtc'
        :param str? extended: Whether to trade in extended hours or not. defaults to False 
        :returns: The following Python dictionary

            - type: str, 'STOCK' or 'CRYPTO'
            - id: str, ID of order
            - symbol: str, symbol of asset

        :raises Exception: There is an error in the order process.
        """
        if symbol == None:
            symbol = self.watch[0]
        if quantity == None:
            quantity = self.get_asset_max_quantity(symbol)
        
        return self.trader.buy(symbol, quantity, in_force, extended)
    
    def sell(self, symbol: str=None, quantity: int=None, in_force: str='gtc', extended: bool=False):
        """Sells the specified asset.

        When called, a limit sell order is placed with a limit
        price 5% lower than the current price. 

        :param str? symbol:    Symbol of the asset to sell. defaults to first symbol in watchlist
        :param float? quantity:  Quantity of asset to sell defaults to sells all
        :param str? in_force:  Duration the order is in force. '{gtc}' or '{gtd}'. defaults to 'gtc'
        :param str? extended:  Whether to trade in extended hours or not. defaults to False 
        :returns: A dictionary with the following keys:

            - type: str, 'STOCK' or 'CRYPTO'
            - id: str, ID of order
            - symbol: str, symbol of asset
        
        :raises Exception: There is an error in the order process.
        """
        if symbol == None:
            symbol = self.watch[0]
        if quantity == None:
            quantity = self.get_asset_quantity(symbol)
        return self.trader.sell(symbol, quantity, in_force, extended)

    # def await_buy(self, symbol: str=None, quantity: int=0, in_force: str='gtc', extended: bool=False):
    #     """Buys the specified asset, and hangs the code until the order is filled. 

    #     :param str? symbol:    Symbol of the asset to buy. defaults to first symbol in watchlist
    #     :param float? quantity:  Quantity of asset to buy. defaults to buys as many as possible
    #     :param str? in_force:  Duration the order is in force. '{gtc}' or '{gtd}'. defaults to 'gtc'
    #     :param str? extended:  Whether to trade in extended hours or not. defaults to False 
    #     :returns: A dictionary with the following keys:

    #         - type: 'STOCK' or 'CRYPTO'
    #         - id: ID of order
    #         - symbol: symbol of asset

    #     :raises Exception: There is an error in the order process.
    #     """
    #     if symbol == None:
    #         symbol = self.watch[0]
    #     if quantity == None:
    #         quantity = self.get_asset_max_quantity(symbol)
    #     return self.trader.await_buy(symbol, quantity, in_force, extended)
    
    # def await_sell(self, symbol: str=None, quantity: int=0, in_force: str='gtc', extended: bool=False):
    #     """Sells the specified asset, and hangs the code until the order is filled. 

    #     :param str? symbol:    Symbol of the asset to sell. defaults to first symbol in watchlist
    #     :param float? quantity:  Quantity of asset to sell defaults to sells all
    #     :param str? in_force:  Duration the order is in force. '{gtc}' or '{gtd}'. defaults to 'gtc'
    #     :param str? extended:  Whether to trade in extended hours or not. defaults to False 
    #     :returns: A dictionary with the following keys:

    #         - type: 'STOCK' or 'CRYPTO'
    #         - id: ID of order
    #         - symbol: symbol of asset

    #     :raises Exception: There is an error in the order process.
    #     """
    #     if symbol == None:
    #         symbol = self.watch[0]
    #     if quantity == None:
    #         quantity = self.get_asset_quantity(symbol)
    #     return self.trader.await_sell(symbol, quantity, in_force, extended)

    def buy_option(self, symbol: str, quantity: int=None, in_force: str='gtc'):
        """Buys the specified option.

        When called, a limit buy order is placed with a limit
        price 5% higher than the current price. 
        
        :param str symbol:    Symbol of the asset to buy, in {OCC} format. 
        :param float? quantity:  Quantity of asset to buy. defaults to buys as many as possible
        :param str? in_force:  Duration the order is in force. '{gtc}' or '{gtd}'. defaults to 'gtc'
        :returns: A dictionary with the following keys:

            - type: 'OPTION'
            - id: ID of order
            - symbol: symbol of asset

        :raises Exception: There is an error in the order process.
        """
        if quantity == None:
            quantity = self.get_asset_max_quantity(symbol)
        return self.trader.buy_option(symbol, quantity, in_force)
    
    def sell_option(self, symbol: str=None, quantity: int=None, in_force: str='gtc'):
        """Sells the specified option.

        When called, a limit sell order is placed with a limit
        price 5% lower than the current price. 

        If the option symbol is specified, it will sell that option. If it is not, then the 
        method will select the first stock symbol in the watchlist, and sell all options 
        related to that stock.
        
        :param str? symbol: Symbol of the asset to sell, in {OCC} format. defaults to sell all options for the first stock in watchlist
        :param float? quantity:  Quantity of asset to sell. defaults to sells all
        :param str? in_force:  Duration the order is in force. '{gtc}' or '{gtd}'. defaults to 'gtc'
        :returns: A dictionary with the following keys:

            - type: 'OPTION'
            - id: ID of order
            - symbol: symbol of asset

        :raises Exception: There is an error in the order process.
        """
        if symbol == None:
            symbol = self.watch[0]
            symbols = [s['occ_symbol'] for s in self.get_account_option_positions() if s['symbol'] == symbol]
        else:
            symbols = [symbol]
        for s in symbols:
            if quantity == None:
                quantity = self.get_asset_quantity(s)
            return self.trader.sell_option(s, quantity, in_force)
    
    def get_option_auto(self, type, symbol=None, limit_exp=None, limit_strike=None):
        """
        Automatically buys an option that satisfies the criteria specified.

        :param str type: 'call' or 'put'
        :param str? symbol: Symbol of stock. defaults to first symbol in watchlist
        :param datetime limit_exp: Minimum expiration date of the option. defaults to 5 days from current day
        :param float limit_strike: For calls, sets the minimum strike price of the option - for puts, the maximum. 
            defaults to current stock price

        """
        if symbol is None:
            symbol = self.watch[0]
        if limit_exp is None:
            limit_exp = self.get_date() + dt.timedelta(days=5)
        if limit_strike is None:
            limit_strike = self.get_asset_price(symbol) 

        exp_dates = self.get_option_chain_info(symbol)['exp_dates']
        exp_dates = list(filter(lambda x: x >= limit_exp, exp_dates))
        exp_dates = sorted(exp_dates)
        exp_date = exp_dates[0]
        chain = self.get_option_chain(symbol, exp_date)
        if type == 'call':
            chain = chain[chain['strike'] > limit_strike]
        else:
            chain = chain[chain['strike'] < limit_strike]
        chain = chain[chain['type'] == type]
        chain = chain.sort_values(by=['strike', 'exp_date'])
        occ = chain.index[0]
        return occ
    
    # ------------------ Functions to trade options ----------------------

    def get_option_chain_info(self, symbol: str=None):
        """Returns metadata about a stock's option chain
        
        :param str? symbol: symbol of stock. defaults to first symbol in watchlist
        :returns: A dict with the following keys:
            - exp_dates: List of expiration dates, in the fomrat "YYYY-MM-DD" 
            - multiplier: Multiplier of the option, usually 100 
        """ 
        if symbol == None:
            symbol = self.watch[0]
        return self.trader.fetch_chain_info(symbol)
    
    def get_option_chain(self, symbol: str, date: dt.datetime):
        """Returns the option chain for the specified symbol and expiration date.
        
        :param str symbol: symbol of stock
        :param dt.datetime date: date of option expiration
        :returns: A dataframe with the follwing columns:

            - exp_date(datetime.datetime): The expiration date
            - strike(float): Strike price
            - type(str): 'call' or 'put'
        
        The index is the {OCC} symbol of the option. 
        """ 
        if symbol == None:
            symbol = self.watch[0]
        return self.trader.fetch_chain_data(symbol, date)
    
    def get_option_market_data(self, symbol: str):
        """Retrieves data of specified option. 

        :param str? symbol: {OCC} symbol of option
        :returns: A dictionary:

            - price: price of option 
            - ask: ask price
            - bid: bid price
        
        """ 
        if symbol == None:
            symbol = self.watch[0]
        return self.trader.fetch_option_market_data(symbol)
    
    # ------------------ Technical Indicators -------------------

    def _default_param(self, symbol, interval, ref, prices):
        if symbol == None:
            symbol = self.watch[0]
        if self.trader is None:
            if interval == None:
                interval = '5MIN'
            if prices == None:
                raise Exception(f'No prices found for symbol {symbol}')
        else:
            if interval == None:
                interval = self.trader.interval
            if prices == None:
                prices = self.trader.storage.load(symbol, interval)[symbol][ref]
           
        return symbol, interval, ref, prices

    def rsi(self, symbol: str=None, period: int=14, interval: str=None, ref: str='close', prices=None) -> np.array:
        """Calculate RSI

        :param str? symbol:     Symbol to perform calculation on. defaults to first symbol in watchlist
        :param int? period:     Period of RSI. defaults to 14
        :param str? interval:   Interval to perform the calculation. defaults to interval of algorithm
        :param str? ref:        'close', 'open', 'high', or 'low'. defaults to 'close'
        :param list? prices:    When specified, this function will use the values provided in the 
                                list to perform calculations and ignore other parameters. defaults to None
        :returns: A list in numpy format, containing RSI values
        """
        symbol, interval, ref, prices = self._default_param(symbol, interval, ref, prices)

        if len(prices) < period:
            warning("Not enough data to calculate RSI, returning None")
            return None

        ohlc = pd.DataFrame({
            'close': np.array(prices),
            'open': np.zeros(len(prices)),
            'high': np.zeros(len(prices)),
            'low': np.zeros(len(prices)),
        })
        rsi = TA.RSI(ohlc, period=period).to_numpy()
        return rsi
    
    def sma(self, symbol: str=None, period: int=14, interval: str='5MIN', ref: str='close', prices=None) -> np.array:
        """Calculate SMA

        :param str? symbol:    Symbol to perform calculation on. defaults to first symbol in watchlist
        :param int? period:    Period of SMA. defaults to 14
        :param str? interval:  Interval to perform the calculation. defaults to interval of algorithm
        :param str? ref:       'close', 'open', 'high', or 'low'. defaults to 'close'
        :param list? prices:    When specified, this function will use the values provided in the 
                                list to perform calculations and ignore other parameters. defaults to None
        :returns: A list in numpy format, containing SMA values
        """
        symbol, interval, ref, prices = self._default_param(symbol, interval, ref, prices)

        if len(prices) < period:
            warning("Not enough data to calculate SMA, returning None")
            return None

        ohlc = pd.DataFrame({
            'close': np.array(prices),
            'open': np.zeros(len(prices)),
            'high': np.zeros(len(prices)),
            'low': np.zeros(len(prices)),
        })
        sma = TA.SMA(ohlc, period=period).to_numpy()
        return sma
    
    def ema(self, symbol: str=None, period: int=14, interval: str='5MIN', ref: str='close', prices=None) -> np.array:
        """Calculate EMA

        :param str? symbol:    Symbol to perform calculation on. defaults to first symbol in watchlist
        :param int? period:    Period of EMA. defaults to 14
        :param str? interval:  Interval to perform the calculation. defaults to interval of algorithm
        :param str? ref:       'close', 'open', 'high', or 'low'. defaults to 'close'
        :param list? prices:    When specified, this function will use the values provided in the 
                                list to perform calculations and ignore other parameters. defaults to None
        :returns: A list in numpy format, containing EMA values
        """
        symbol, interval, ref, prices = self._default_param(symbol, interval, ref, prices)

        if len(prices) < period:
            warning("Not enough data to calculate EMA, returning None")
            return None

        ohlc = pd.DataFrame({
            'close': np.array(prices),
            'open': np.zeros(len(prices)),
            'high': np.zeros(len(prices)),
            'low': np.zeros(len(prices)),
        })
        ema = TA.EMA(ohlc, period=period).to_numpy()
        return ema
    
    def bbands(self, symbol: str=None, period: int=14, interval: str='5MIN', ref: str='close', dev: float=1.0, prices=None) -> Tuple[np.array, np.array, np.array]:
        """Calculate Bollinger Bands

        :param str? symbol:    Symbol to perform calculation on. defaults to first symbol in watchlist
        :param int? period:    Period of BBands. defaults to 14
        :param str? interval:  Interval to perform the calculation. defaults to interval of algorithm
        :param str? ref:       'close', 'open', 'high', or 'low'. defaults to 'close'
        :param float? dev:         Standard deviation of the bands. defaults to 1.0
        :param list? prices:    When specified, this function will use the values provided in the 
                                list to perform calculations and ignore other parameters. defaults to None
        :returns: A tuple of numpy lists, each a list of BBand top, average, and bottom values
        """
        symbol, interval, ref, prices = self._default_param(symbol, interval, ref, prices)

        if len(prices) < period:
            warning("Not enough data to calculate BBands, returning None")
            return None, None, None

        ohlc = pd.DataFrame({
            'close': np.array(prices),
            'open': np.zeros(len(prices)),
            'high': np.zeros(len(prices)),
            'low': np.zeros(len(prices)),
        })

        t, m, b = TA.BBANDS(ohlc, period=period, std_multiplier=dev, MA=TA.SMA(ohlc, period)).T.to_numpy()
        return t, m, b
    
    def crossover(self, prices_0, prices_1):
        """Performs {crossover analysis} on two sets of price data

        :param list prices_0:  First set of price data.
        :param list prices_1:  Second set of price data
        :returns: 'True' if prices_0 most recently crossed over prices_1, 'False' otherwise

        :raises Exception: If either or both price list has less than 2 values
        """
        if len(prices_0) < 2 or len(prices_1) < 2:
            raise Exception('There must be at least 2 datapoints to calculate crossover')
        return prices_0[-2] < prices_1[-2] and prices_0[-1] > prices_1[-1]

    ############### Getters for Trader properties #################

    def get_asset_quantity(self, symbol: str=None) -> float:
        """Returns the quantity owned of a specified asset. 

        :param str? symbol:  Symbol of asset. defaults to first symbol in watchlist
        :returns: Quantity of asset as float. 0 if quantity is not owned.
        :raises: 
        """
        if symbol == None:
            symbol = self.watch[0]
        if len(symbol) <= 6:
            search = self.trader.stock_positions + self.trader.crypto_positions
            for p in search:
                if p['symbol'] == symbol:
                    return p['quantity']
        else:
            for p in self.trader.option_positions:
                if p['occ_symbol'] == symbol:
                    return p['quantity']        
        return 0
    
    def get_asset_cost(self, symbol: str=None) -> float:
        """Returns the average cost of a specified asset. 

        :param str? symbol:  Symbol of asset. defaults to first symbol in watchlist
        :returns: Average cost of asset. Returns None if asset is not being tracked.
        :raises Exception: If symbol is not currently owned.
        """
        if symbol == None:
            symbol = self.watch[0]
        if len(symbol) <= 6:
            search = self.trader.stock_positions + self.trader.crypto_positions
            for p in search:
                if p['symbol'] == symbol:
                    return p['avg_price']
        else:
            for p in self.trader.option_positions:
                if p['occ_symbol'].replace(' ', '') == symbol.replace(' ', ''):
                    return p['avg_price']
        
        raise Exception(f"{symbol} is not currently owned")

    def get_asset_price(self, symbol: str=None) -> float:
        """Returns the current price of a specified asset. 

        :param str? symbol: Symbol of asset. defaults to first symbol in watchlist
        :returns:           Price of asset. 
        :raises Exception:  If symbol is not in the watchlist.
        """
        if symbol == None:
            symbol = self.watch[0]
        if len(symbol) <= 6:
            return self.trader.storage.load(symbol, self.trader.interval)[symbol]['close'][-1]
        else:
            for p in self.trader.option_positions:
                if p['occ_symbol'] == symbol:
                    return p['current_price'] * p['multiplier']
            return self.get_option_market_data(symbol)['price'] * 100
            

    def get_asset_price_list(self, symbol:str=None, interval:list=None, ref:str='close'):
        """Returns a list of recent prices for an asset. 

        This function is not compatible with options. 

        :param str? symbol:     Symbol of stock or crypto asset. defaults to first symbol in watchlist
        :param str? interval:   Interval of data. defaults to the interval of the algorithm 
        :param str? ref:        'close', 'open', 'high', or 'low'. defaults to 'close'
        :returns: List of prices
        """
        if symbol == None:
            symbol = self.watch[0]
        if interval == None:
            interval = self.trader.interval
        if len(symbol) <= 6:
            return list(self.trader.storage.load(symbol, interval)[symbol][ref])
        else:
            warning("Price list not available for options")
            return None
    
    def get_asset_candle(self, symbol: str, interval=None) -> pd.DataFrame():
        """Returns the most recent candle as a pandas DataFrame

        This function is not compatible with options. 

        :param str? symbol:  Symbol of stock or crypto asset. defaults to first symbol in watchlist
        :returns: Price of asset as a dataframe with the following columns:

            - open
            - high
            - low
            - close
            - volume
        
        The index is a datetime object

        :raises Exception: If symbol is not in the watchlist.
        """
        if symbol == None:
            symbol = self.watch[0]
        if interval == None:
            interval = self.trader.interval
        if len(symbol) <= 6:
            return self.trader.storage.load(symbol, interval).iloc[[-1]][symbol]
        else:
            warning("Candles not available for options")
            return None
    
    def get_asset_candle_list(self, symbol:str=None, interval=None) -> pd.DataFrame():
        """Returns the candles of an asset as a pandas DataFrame

        This function is not compatible with options. 

        :param str? symbol:  Symbol of stock or crypto asset. defaults to first symbol in watchlist
        :returns: Prices of asset as a dataframe with the following columns:

            - open
            - high
            - low
            - close
            - volume
        
        The index is a datetime object
        
        :raises Exception: If symbol is not in the watchlist.
        """
        if symbol == None:
            symbol = self.watch[0]
        if interval == None:
            interval = self.trader.interval
        return self.trader.storage.load(symbol, interval)[symbol]
    
    def get_asset_returns(self, symbol=None) -> float:
        """Returns the return of a specified asset.

        :param str? symbol:  Symbol of stock, crypto, or option. Options should be in {OCC} format. 
                        defaults to first symbol in watchlist
        :returns: Return of asset, expressed as a decimal. 
        """
        if symbol == None:
            symbol = self.watch[0]
        cost = self.get_asset_cost(symbol)
        # For options, apply the multiplier 
        if len(symbol) > 6:
            cost = cost * 100
        price = self.get_asset_price(symbol)
        ret = (price - cost) / cost
        return ret
    
    def get_asset_max_quantity(self, symbol=None):
        """Calculates the maximum quantity of an asset that can be bought given the current buying power. 

        :param str? symbol:  Symbol of stock, crypto, or option. Options should be in {OCC} format. 
            defaults to first symbol in watchlist
        :returns: Quantity that can be bought.
        """
        if symbol == None:
            symbol = self.watch[0]

        power = self.get_account_buying_power()
        price = self.get_asset_price(symbol)
        print(f"{symbol} price: {price}, buying power: {power}")
        if is_crypto(symbol):
            price = mark_up(price)
            qty = math.floor(power/price * 10**5) / 10**5
        else:
            price = mark_up(price)
            qty = math.floor(power/price)
        return qty

    def get_account_buying_power(self) -> float:
        """Returns the current buying power of the user

        :returns: The current buying power as a float.
        """
        return self.trader.account['buying_power']
    
    def get_account_equity(self) -> float:
        """Returns the current equity.

        :returns: The current equity as a float.
        """
        return self.trader.account['equity']
    
    def get_account_stock_positions(self) -> List:
        """Returns the current stock positions.

        :returns: A list of dictionaries with the following keys:
            - symbol
            - quantity
            - avg_price
        """
        return self.trader.stock_positions
    
    def get_account_crypto_positions(self) -> List:
        """Returns the current crypto positions.

        :returns: A list of dictionaries with the following keys:
            - symbol
            - quantity
            - avg_price
        """
        return self.trader.crypto_positions
    
    def get_account_option_positions(self) -> List:
        """Returns the current option positions.

        :returns: A list of dictionaries with the following keys:
            - symbol
            - quantity
            - avg_price
        """
        return self.trader.option_positions
    
    def get_watchlist(self) -> List:
        """Returns the current watchlist.
        """
        return self.watch

    def get_stock_watchlist(self) -> List:
        """Returns the current watchlist.
        """
        return [s for s in self.watch if not is_crypto(s)]
    
    def get_crypto_watchlist(self) -> List:
        """Returns the current watchlist.
        """
        return [s for s in self.watch if is_crypto(s)]

    def get_time(self):
        """Returns the current hour and minute.

        This returns the current time, which is different from the timestamp
        on a ticker. For example, if you are running an algorithm every 5 minutes,
        at 11:30am you will get a ticker for 11:25am. This function will return 
        11:30am. 

        :returns: The current time as a datetime object
        """
        return self.get_datetime().time()
    
    def get_date(self):
        """Returns the current date.

        :returns: The current date as a datetime object
        """
        return self.get_datetime().date()

    def get_datetime(self):
        """Returns the current date and time.

        This returns the current time, which is different from the timestamp
        on a ticker. For example, if you are running an algorithm every 5 minutes,
        at 11:30am you will get a ticker for 11:25am. This function will return 
        11:30am. 

        :returns: The current date and time as a datetime object
        """
        return self.trader.timestamp.replace(tzinfo=None)
    
    def get_option_position_quantity(self, symbol: str=None) -> bool:
        """Returns the number of types of options held for a stock.

        :param str symbol:  Symbol of the stock to check
        :returns: True if the user has an option for the specified symbol.
        """
        if symbol == None:
            symbol = self.watch[0]
        pos = [p for p in self.trader.option_positions if p['symbol'] == symbol]
        return len(pos)
    
    def is_day_trade(self, action, symbol=None) -> bool:
        """
        Checks if performing a buy or sell will be considered day trading
        """
        if symbol == None:
            symbol = self.watch[0]
        
        history = self.trader.logger.get_transactions()
        if len(history) < 1:
            return False
        recent = history.loc[self.get_date():]
        recent = recent[recent['symbol'] == symbol]
        if action == 'buy':
            return False 
        if action == 'sell':
            recent = recent.loc[recent['action'] == 'buy']
            if len(recent.index) > 0:
                return True
            return False
    
    # Used for testing
    def add_symbol(self, symbol:str):
        """Adds a symbol to the watchlist. 

        :param str symbol: Symbol of stock or crypto asset. 
        """
        self.watch.append(symbol)

    
    

        
        
        

