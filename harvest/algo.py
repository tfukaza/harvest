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

    ############ Functions to configure the algo #################

    def add_symbol(self, symbol: str) -> None:
        self.watch.append(symbol)
    
    def remove_symbol(self, symbol: str) -> None:
        self.watch.remove(symbol)
    
    ############ Functions interfacing with broker through the trader #################

    def buy(self, symbol: str=None, quantity: int=None, in_force: str='gtc', extended: bool=False):
        """Buys the specified asset.

        When called, Harvests places a limit order with a limit
        price 5% higher than the current price. 

        :param str? symbol:    Symbol of the asset to buy. defaults to first symbol in watch
        :param float? quantity:  Quantity of asset to buy. defaults to 1
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

        :param str? symbol:    Symbol of the asset to sell
        :param float? quantity:  Quantity of asset to sell
        :param str? in_force:  Duration the order is in force
        :param str? extended:  Whether to trade in extended hours or not. 
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

        :param str? symbol:    Symbol of the asset to buy
        :param float? quantity:  Quantity of asset to buy
        :param str? in_force:  Duration the order is in force
        :param str? extended:  Whether to trade in extended hours or not. 
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

        :param str? symbol:    Symbol of the asset to buy
        :param float? quantity:  Quantity of asset to buy
        :param str? in_force:  Duration the order is in force
        :param str? extended:  Whether to trade in extended hours or not. 
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
        
        :param str? symbol:    Symbol of the asset to buy, in OCC format. 
        :param float? quantity:  Quantity of asset to buy
        :param str? in_force:  Duration the order is in force
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
        
        :param str? symbol:    Symbol of the asset to buy, in OCC format. 
        :param float? quantity:  Quantity of asset to buy
        :param str? in_force:  Duration the order is in force
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

    def get_chain_info(self, symbol: str):
        """Returns information about the symbol's options
        
        :param symbol: symbol of stock
        :returns: A dict with the following keys:
            - id: ID of the option chain 
            - exp_dates: List of expiration dates, in the fomrat "YYYY-MM-DD" 
            - multiplier: Multiplier of the option, usually 100 
        """ 
        return self.trader.fetch_chain_info(symbol)
    
    def get_chain_data(self, symbol: str):
        """Returns the option chain for the specified symbol. 
        
        :param symbol: symbol of stock
        :returns: A dataframe in the following format:

                    exp_date strike  type    id
            OCC
            ---     ---      ---     ---     ---     
        - OCC: the chain symbol in OCC format
        """ 
        return self.trader.fetch_chain_data(symbol)
    
    def get_option_market_data(self, symbol: str):
        """Retrieves data of specified option. 

        :param symbol: Occ symbol of option
        :returns: A dictionary:
            - price: price of option 
            - ask: ask price
            - bid: bid price
            }
        """ 
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
                prices = self.trader.queue.get_symbol_interval_prices(symbol, interval, ref)
           
        
        return symbol, interval, ref, prices

    def rsi(self, symbol: str=None, period: int=14, interval: str=None, ref: str='close', prices=None) -> np.array:
        """Calculate RSI

        :param symbol:    Symbol to perform calculation on 
        :param period:    Period of RSI
        :param interval:  Interval to perform the calculation
        :param ref:       'close', 'open', 'high', or 'low'
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

        :param symbol:    Symbol to perform calculation on 
        :param period:    Period of SMA
        :param interval:  Interval to perform the calculation
        :param ref:       'close', 'open', 'high', or 'low'
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

        :param symbol:    Symbol to perform calculation on 
        :param period:    Period of EMA
        :param interval:  Interval to perform the calculation
        :param ref:       'close', 'open', 'high', or 'low'
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

        :param symbol:    Symbol to perform calculation on 
        :param period:    Period of BBand
        :param interval:  Interval to perform the calculation
        :param ref:       'close', 'open', 'high', or 'low'
        :param dev:       Standard deviation of the bands
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
        if len(prices_0) < 2 or len(prices_1) < 2:
            raise Exception('There must be at least 2 datapoints to calculate crossover')
        return prices_0[-2] < prices_1[-2] and prices_0[-1] > prices_1[-1]

    ############### Getters for Trader properties #################

    def get_quantity(self, symbol: str) -> float:
        """Returns the quantity owned of a specified asset. 

        :param symbol:  Symbol of asset
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

        :param symbol:  Symbol of asset
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
                    return p['current_price'] * p['multiplier']
    
    def get_candle(self, symbol: str) -> pd.DataFrame():
        if len(symbol) <= 6:
            return self.trader.queue.get_symbol_interval(symbol, self.trader.interval).iloc[[-1]]
        else:
            raise Exception("Candles not available for options")
    
    def get_candle_list(self, symbol, interval=None):
        if interval == None:
            interval = self.fetch_interval
        return self.trader.queue.get_symbol_interval(symbol, interval)
    
    def get_returns(self, symbol) -> float:
        """Returns the return of a specified asset. 

        :param symbol:  Symbol of stock, crypto, or option. Options should be in OCC format.
        :returns: Return of asset, expressed as a decimal. Returns None if asset is not owned.
        """
        cost = self.get_cost(symbol)
        price = self.get_price(symbol)
        ret = (price - cost) / cost
        return ret
    
    def get_max_quantity(self, symbol, round=True):
        price = self.get_price(symbol)
        power = self.get_account_buying_power()
        if round:
            qty = int(power/price)
        else:
            qty = power/price 
        return qty

    
    def get_account_buying_power(self) -> float:
        return self.trader.account['buying_power']
    
    def get_account_equity(self) -> float:
        return self.trader.account['equity']
            
    
    def get_price_list(self, symbol, interval=None, ref='close'):
        """Returns a list of recent prices for an asset. 

        :param symbol:  Symbol of asset.
        :param interval: Interval of data.
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
    
    
    

        
        
        

