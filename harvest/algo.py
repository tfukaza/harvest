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
        self.watch = []
        self.trader = None # Allows algo to handle the case when runs without a trader

    def setup(self):
        pass

    def main(self, meta = {}):
        pass
    
    ############ Functions interfacing with broker through the trader #################

    def buy(self, symbol: str=None, quantity: int=None, in_force: str='gtc', extended: bool=False):
        """Buys the specified asset.

        When called, Harvests places a limit order with a limit
        price 5% higher than the current price. 

        :param str? symbol:    Symbol of the asset to buy. defaults to first symbol in watchlist
        :param float? quantity:  Quantity of asset to buy. defaults to buys as many as possible
        :param str? in_force:  Duration the order is in force. '{gtc}' or '{gtd}'. defaults to 'gtc'
        :param str? extended:  Whether to trade in extended hours or not. defaults to False 
        :returns: The following Python dictionary

            - type: str, 'STOCK' or 'CRYPTO'
            - id: str, ID of order
            - symbol: str, symbol of asset

        :raises Exception: There is an error in the order process.
        """
        if symbol == None:
            symbol = self.watch[0]
        if quantity == None:
            quantity = self.get_max_quantity(symbol)
        
        return self.trader.buy(symbol, quantity, in_force, extended)
    
    def sell(self, symbol: str=None, quantity: int=None, in_force: str='gtc', extended: bool=False):
        """Sells the specified asset.

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
            quantity = self.get_quantity(symbol)
        return self.trader.sell(symbol, quantity, in_force, extended)

    def await_buy(self, symbol: str=None, quantity: int=0, in_force: str='gtc', extended: bool=False):
        """Buys the specified asset, and hangs the code until the order is filled. 

        :param str? symbol:    Symbol of the asset to buy. defaults to first symbol in watchlist
        :param float? quantity:  Quantity of asset to buy. defaults to buys as many as possible
        :param str? in_force:  Duration the order is in force. '{gtc}' or '{gtd}'. defaults to 'gtc'
        :param str? extended:  Whether to trade in extended hours or not. defaults to False 
        :returns: A dictionary with the following keys:

            - type: 'STOCK' or 'CRYPTO'
            - id: ID of order
            - symbol: symbol of asset

        :raises Exception: There is an error in the order process.
        """
        if symbol == None:
            symbol = self.watch[0]
        if quantity == None:
            quantity = self.get_max_quantity(symbol)
        return self.trader.await_buy(symbol, quantity, in_force, extended)
    
    def await_sell(self, symbol: str=None, quantity: int=0, in_force: str='gtc', extended: bool=False):
        """Sells the specified asset, and hangs the code until the order is filled. 

        :param str? symbol:    Symbol of the asset to sell. defaults to first symbol in watchlist
        :param float? quantity:  Quantity of asset to sell defaults to sells all
        :param str? in_force:  Duration the order is in force. '{gtc}' or '{gtd}'. defaults to 'gtc'
        :param str? extended:  Whether to trade in extended hours or not. defaults to False 
        :returns: A dictionary with the following keys:

            - type: 'STOCK' or 'CRYPTO'
            - id: ID of order
            - symbol: symbol of asset

        :raises Exception: There is an error in the order process.
        """
        if symbol == None:
            symbol = self.watch[0]
        if quantity == None:
            quantity = self.get_quantity(symbol)
        return self.trader.await_sell(symbol, quantity, in_force, extended)

    def buy_option(self, symbol: str, quantity: int=None, in_force: str='gtc'):
        """Buys the specified option.
        
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
            quantity = self.get_max_quantity(symbol)
        return self.trader.buy_option(symbol, quantity, in_force)
    
    def sell_option(self, symbol: str, quantity: int=None, in_force: str='gtc'):
        """Sells the specified option.
        
        :param str? symbol:    Symbol of the asset to sell, in {OCC} format. 
        :param float? quantity:  Quantity of asset to sell. defaults to sells all
        :param str? in_force:  Duration the order is in force. '{gtc}' or '{gtd}'. defaults to 'gtc'
        :returns: A dictionary with the following keys:

            - type: 'OPTION'
            - id: ID of order
            - symbol: symbol of asset

        :raises Exception: There is an error in the order process.
        """
        if quantity == None:
            quantity = self.get_quantity(symbol)
        return self.trader.sell_option(symbol, quantity, in_force)
    
    ########### Functions to trade options #################

    def get_chain_info(self, symbol: str=None):
        """Returns metadata about a stock's option chain
        
        :param str? symbol: symbol of stock. defaults to first symbol in watchlist
        :returns: A dict with the following keys:
            - id: ID of the option chain 
            - exp_dates: List of expiration dates, in the fomrat "YYYY-MM-DD" 
            - multiplier: Multiplier of the option, usually 100 
        """ 
        if symbol == None:
            symbol = self.watch[0]
        return self.trader.fetch_chain_info(symbol)
    
    def get_chain_data(self, symbol: str):
        """Returns the option chain for the specified symbol. 
        
        :param str? symbol: symbol of stock
        :returns: A dataframe with the follwing columns:

            - exp_date(datetime.datetime): The expiration date
            - strike(float): Strike price
            - type(str): 'call' or 'put'
            - id(str): The unique ID of the option  
        
        The index is the {OCC} symbol of the option. 
        """ 
        if symbol == None:
            symbol = self.watch[0]
        return self.trader.fetch_chain_data(symbol)
    
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
    
    ########## Technical Indicators ###############

    def default_param(self, symbol, interval, ref, prices):
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
        symbol, interval, ref, prices = self.default_param(symbol, interval, ref, prices)

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
        symbol, interval, ref, prices = self.default_param(symbol, interval, ref, prices)

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
        symbol, interval, ref, prices = self.default_param(symbol, interval, ref, prices)

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
        symbol, interval, ref, prices = self.default_param(symbol, interval, ref, prices)

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

    def get_quantity(self, symbol: str=None) -> float:
        """Returns the quantity owned of a specified asset. 

        :param str? symbol:  Symbol of asset. defaults to first symbol in watchlist
        :returns: Quantity of asset as float. 0 if quantity is not owned.
        :raises: 
        """
        if symbol == None:
            symbol = self.watch[0]
        search = self.trader.stock_positions + self.trader.crypto_positions
        for p in search:
            if p['symbol'] == symbol:
                return p['quantity']
        return 0
    
    def get_cost(self, symbol: str=None) -> float:
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
                if p['occ_symbol'] == symbol:
                    return p['avg_price']
        
        raise Exception(f"{symbol} is not currently owned")

    def get_price(self, symbol: str=None) -> float:
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
            return self.get_option_market_data(symbol)['price']
            

    def get_price_list(self, symbol:str=None, interval:list=None, ref:str='close'):
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
            return self.trader.storage.load(symbol, interval)[symbol][ref]
        else:
            raise Exception("Price list not available for options")
    
    def get_candle(self, symbol: str) -> pd.DataFrame():
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
        if len(symbol) <= 6:
            return self.trader.storage.load(symbol, self.trader.interval).iloc[[-1]]
        else:
            raise Exception("Candles not available for options")
    
    def get_candle_list(self, symbol:str=None, interval=None) -> pd.DataFrame():
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
        return self.trader.storage.load(symbol, interval)
    
    def get_returns(self, symbol=None) -> float:
        """Returns the return of a specified asset.

        :param str? symbol:  Symbol of stock, crypto, or option. Options should be in {OCC} format. 
                        defaults to first symbol in watchlist
        :returns: Return of asset, expressed as a decimal. 
        """
        if symbol == None:
            symbol = self.watch[0]
        cost = self.get_cost(symbol)
        price = self.get_price(symbol)
        ret = (price - cost) / cost
        return ret
    
    def get_max_quantity(self, symbol=None, round=True):
        """Calculates the maximum quantity of an asset that can be bought given the current buying power. 

        :param str? symbol:  Symbol of stock, crypto, or option. Options should be in {OCC} format. 
                        defaults to first symbol in watchlist
        :param bool? round:  If set to True, the result is returned as an integer. defaults to True 
        :returns: Quantity that can be bought.
        """
        if symbol == None:
            symbol = self.watch[0]
        price = self.get_price(symbol) * 1.05
        power = self.get_account_buying_power()
        if round:
            qty = int(power/price)
        else:
            qty = power/price 
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
    
    def get_time(self):
        """Returns the current hour and minute.

        This returns the current time, which is different from the timestamp
        on a ticker. For example, if you are running an algorithm every 5 minutes,
        at 11:30am you will get a ticker for 11:25am. This function will return 
        11:30am. 

        :returns: The current time as a datetime object
        """
        return self.trader.timestamp.time()
    
    def get_date(self):
        """Returns the current date.

        :returns: The current date as a datetime object
        """
        return self.trader.timestamp.date() 

    def get_datetime(self):
        """Returns the current date and time.

        This returns the current time, which is different from the timestamp
        on a ticker. For example, if you are running an algorithm every 5 minutes,
        at 11:30am you will get a ticker for 11:25am. This function will return 
        11:30am. 

        :returns: The current date and time as a datetime object
        """
        return self.trader.timestamp 
    
    # Used for testing
    def add_symbol(self, symbol:str):
        """Adds a symbol to the watchlist. 

        :param str symbol: Symbol of stock or crypto asset. 
        """
        self.watch.append(symbol)

    
    

        
        
        

