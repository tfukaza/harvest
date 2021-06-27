# Builtins
import asyncio
import atexit
import datetime as dt
import json
import logging
import time
import re
import requests
import sys
import urllib
from datetime import timedelta
from logging import critical, debug, error, info, warning
from typing import Any, Callable, Dict, List 

# External libraries
import numpy as np
import pandas as pd
import pytz

# Submodule imports
import harvest.load


class BaseBroker:
    """Broker class communicates with various API endpoints to perform the
    neccesary operations. The BaseBroker defines the interface for all Broker classes to 
    extend and implement.

    Attributes
    :fetch_interval: A string indicating the interval the broker fetches the latest asset data.  
        This should be initialized in setup_run (see below).
    """
    
    def __init__(self, path: str=None):
        """Here, the broker should perform any authentications neccesary to 
        connect to the brokerage it is using.

        :path: path to the YAML file containing credentials for the broker. 
            If not specified, should default to './secret.yaml'
        """
        pass

    def setup(self, handler, trader) -> None:
        """This method initializes several class attributes which are required for 
        all implementations of BaseBroker. Usually this method does not need to 
        be reimplemenetd, and can be left alone. 
      
        :handler: A reference to a method in the Trader class that invokes 
            the algorithm
        :trader: A reference to the parent Trader class
        """
        self.handler = handler
        self.trader = trader
    
    def setup_run(self, watch: List[str], interval: str):
        """This function is called right before the algorithm begins.
        It should perform any configurations neccesary to start running.

        :watch: List of stocks/cryptos to watch. Cryptos are prepended with a '@'
            to distinguish them from stocks
        :interval: Interval to call the algo's handler 
        
        Regardless of the implementation, this method must initialize 
        the following attributes:

        :watch: A list containing strings of stock/crypto (but not option) symbols this broker should 
            keep track of. Cryptos are prepended with a '@' to distinguish them from stocks.
        :interval: A string specifying the interval to run the algorithm.
        :fetch_interval: A string specifying the interval to collect data. This is needed
            because some brokers like Alpaca Market allow data streaming. Usualluy data streaming 
            streams data every minute, so even if the algorithm is designed to run at a lower frequncy 
            (like once every 30MIN), under the hood Harvest needs to process data every minute.
        """
        raise Exception("setup() is not yet implemented in this broker")
           
    def run(self):
        """This function starts the algorithm. Whether it be polling or streaming,
        the broker must implement some code to invoke _handler() at a specified interval. 
        """
        pass

    def _handler(self) -> Dict[str, pd.DataFrame]:
        """This function should be called at the specified interval, and return data.
        For brokers that use streaming, this often means specifying this function as a callback.
        For brokers that use polling, this often means calling whatever endpoint is needed to 
        obtain stock/crpto data, at the specified interval.

        :returns: A dictionary where each key is the symbol for an asset, and the value is the
            corresponding data in the following pandas dataframe format:
                      Symbol                              
                      open   high    low close   volume       
            timestamp
            ---       ---    ---     --- ---     ---         

        timestamp should be an offset-aware datetime object in UTC timezone
        """
        pass
    
    def _handler_wrap( func ):
        """Wrapper to run the handler async"""
        def wrapper(*args, **kwargs):
            self = args[0]
            df = func(*args, **kwargs) 

            now = time.mktime(time.gmtime())
            now = dt.datetime.fromtimestamp(now)
            now = now.replace(second=0, microsecond=0)
            now = pytz.utc.localize(now)

            self.trader.loop.run_until_complete(self.handler(df, now))
        return wrapper

    def exit(self):
        """This function is called after every invocation of algo's handler. 
        The intended purpose is for brokers to clear any cache it may have created.
        """
        pass

    def _exception_handler( func ):
        """Wrapper to handle unexpected errors in the wrapped funtion. 
        Most functions should be wrapped with this to properly handle errors, such as
        when internet connection is lost. 

        :func: Function to wrap.
        :returns: The returned value of func if func runs properly. Raises an Exception if func fails.
        """
        def wrapper(*args, **kwargs):
            tries = 3
            while tries > 0:
                try:
                    return func(*args, **kwargs) 
                except Exception as e:
                    error(e)
                    error("Retrying...")
                    tries = tries - 1 
                    continue
            raise Exception(f"{func} failed")
        return wrapper

    def fetch_price_history( self,
        last: dt.datetime, 
        today: dt.datetime, 
        interval: str='5MIN',
        symbol: str = None):
        """Returns historical price data for the specified asset and period.

        :last: The starting date of the period, inclusive.
        :today: The ending date of the period, inclusive.
        :interval: The interval of requested historical data.
        :symbol: The stock/crypto to get data for.

        :returns: A pandas dataframe, same format as _handler()
        """
        raise Exception("This endpoint is not supported in this broker")
    
    def fetch_latest_stock_price(self):
        """Returns the latest prices for all stocks in self.watch

        :returns: A pandas dataframe, same format as _handler()
        """
        raise Exception("This endpoint is not supported in this broker")

    def fetch_latest_crypto_price(self):
        """Returns the latest prices for all cryptos in self.watch
        
        :returns: A pandas dataframe, same format as _handler()
        """
    
    def fetch_stock_positions(self):
        """Returns all current stock positions
        
        :returns: A list of dictionaries with the following keys and values:
            - symbol: Ticker symbol of the stock
            - avg_price: The average price the stock was bought at
            - quantity: Quantity owned
        """
        raise Exception("This endpoint is not supported in this broker")

    def fetch_option_positions(self):
        """Returns all current option positions
        
        :returns: A list of dictionaries with the following keys and values:
            - symbol: Ticker symbol of the underlying stock
            - occ_symbol: OCC symbol of option
            - avg_price: Average price the option was bought at
            - quantity: Quantity owned
            - multiplier: How many stocks each option represents
            - exp_date: When the option expires
            - strike_price: Strike price of the option
            - type: 'call' or 'put'
        """
        raise Exception("This endpoint is not supported in this broker")

    def fetch_crypto_positions(self):
        """Returns all current crypto positions
        
        :returns: A list of dictionaries with the following keys and values:
            - symbol: Ticker symbol for the crypto, prepended with an '@'
            - avg_price: The average price the crypto was bought at
            - quantity: Quantity owned
        """
        raise Exception("This endpoint is not supported in this broker")
    
    def update_option_positions(self, positions: List[Any]):
        """Updates entries in option_positions list. This is needed as options are priced
        based on various metrics, and cannot be easily calculated from stock prices. 

        :positions: The option_positions list in the Trader class. 
        :returns: Nothing
        """
        raise Exception("This endpoint is not supported in this broker")

    def fetch_account(self):
        """Returns current account information from the brokerage. 
        
        :returns: A dictionary with the following keys and values:
            - equity: Total assets in the brokerage
            - cash: Total cash in the brokerage
            - buying_power: Total buying power
            - multiplier: Scale of leverge, if leveraging
        """
        raise Exception("This endpoint is not supported in this broker")
    
    def fetch_stock_order_status(self, id):
        """Returns the status of a stock order with the given id.

        :id: ID of the stock order 
        
        :returns: A dictionary with the following keys and values:
            - type: 'STOCK'
            - id: ID of the order
            - symbol: Ticker of stock
            - quantity: Quantity ordered
            - filled_quantity: Quantity filled so far
            - side: 'buy' or 'sell'
            - time_in_force: Time the order is in force
            - status: Status of the order
        """
        raise Exception("This endpoint is not supported in this broker")
    
    def fetch_option_order_status(self, id):
        """Returns the status of a option order with the given id.

        :id: ID of the option order 
        
        :returns: A dictionary with the following keys and values:
            - type: 'OPTION'
            - id: ID of the order
            - symbol: Ticker of underlying stock
            - quantity: Quantity ordered
            - filled_quantity: Quantity filled so far
            - side: 'buy' or 'sell'
            - time_in_force: Time the order is in force
            - status: Status of the order
        """
        raise Exception("This endpoint is not supported in this broker")
    
    def fetch_crypto_order_status(self, id):
        """Returns the status of a crypto order with the given id.

        :id: ID of the crypto order 
        
        :returns: A dictionary with the following keys and values:
            - type: 'CRYPTO'
            - id: ID of the order
            - symbol: Ticker of crypto
            - quantity: Quantity ordered
            - filled_quantity: Quantity filled so far
            - side: 'buy' or 'sell'
            - time_in_force: Time the order is in force
            - status: Status of the order
        """
        raise Exception("This endpoint is not supported in this broker")
    
    def fetch_order_queue(self):
        """Returns all current pending orders 
        
        returns: A list of dictionaries with the following keys and values:
            For stocks:
                - type: "STOCK"
                - symbol: Symbol of stock
                - quantity: Quantity ordered
                - filled_qty: Quantity filled
                - id: ID of order
                - time_in_force: Time in force
                - status: Status of the order
                - side: 'buy' or 'sell'
            For options:
                - type: "OPTION",
                - symbol: Symbol of stock
                - quantity: Quantity ordered
                - filled_qty: Quantity filled
                - id: ID of order
                - time_in_force: Time in force
                - status: Status of the order         
                - legs: A list of dictionaries with keys:
                    - id: id of leg
                    - side: 'buy' or 'sell'
            For crypto:
                - type: "CRYPTO"
                - symbol: Symbol of stock
                - quantity: Quantity ordered
                - filled_qty: Quantity filled
                - id: ID of order
                - time_in_force: Time in force
                - status: Status of the order
                - side: 'buy' or 'sell'
        """
        raise Exception("This endpoint is not supported in this broker")

    def fetch_chain_info(self, symbol: str):
        """Returns information about the symbol's options
        
        :returns: A dict with the following keys and values:
            - id: ID of the option chain 
            - exp_dates: List of expiration dates, in the fomrat "YYYY-MM-DD" 
            - multiplier: Multiplier of the option, usually 100 
        """ 
    
    def fetch_chain_data(self, symbol: str):
        """Returns the option chain for the specified symbol. 
        
        :symbol: symbol 
        :returns: A dataframe in the following format:

                    exp_date strike  type    id
            OCC
            ---     ---      ---     ---     ---     
        exp_date should be a timezone-aware date localized to UTC
        """ 
    
    def fetch_option_market_data(self, symbol: str):
        """Retrieves data of specified option. 

        :symbol:    Occ symbol of option
        :returns:   A dictionary:
            - price: price of option 
            - ask: ask price
            - bid: bid price
            }
        """ 

    def order_limit(self, 
        side: str, 
        symbol: str,
        quantity: float, 
        limit_price: float, 
        in_force: str='gtc', 
        extended: bool=False, 
        ):
        """Places a limit order. 

        :symbol:    symbol of asset
        :side:      'buy' or 'sell'
        :quantity:  quantity to buy or sell
        :limit_price:   limit price
        :in_force:  'gtc' by default
        :extended:  'False' by default

        :returns: A dictionary with the following keys and values:
            - type: 'STOCK' or 'CRYPTO'
            - id: ID of order
            - symbol: symbol of asset
            Raises an exception if order fails. 
        """
        raise Exception("This endpoint is not supported in this broker")
    
    def buy(self, symbol: str=None, quantity: int=0, in_force: str='gtc', extended: bool=False):
        """Buys the sepcified asset.

        :symbol:    Symbol of the asset to buy
        :quantity:  Quantity of asset to buy
        :in_force:  Duration the order is in force
        :extended:  Whether to trade in extended hours or not. 

        :returns: The result of order_limit(). Returns None if there is an issue with the parameters.
        """
        if symbol == None:
            symbol = self.watch[0]
        buy_power = self.trader.account['buying_power']
        price = self.trader.queue.get_last_symbol_interval_price(symbol, self.fetch_interval, 'close')
        limit_price = round(price * 1.05, 2)
        total_price = limit_price * quantity
        
        if total_price >= buy_power:
            debug("Not enough buying power")
            return None
        if quantity <= 0:
            debug("Quantity must be greater than 0")
            return None
        return self.order_limit('buy', symbol, quantity, limit_price, in_force, extended)
    
    def await_buy(self, symbol: str=None, quantity: int=0, in_force: str='gtc', extended: bool=False):
        """Buys the specified asset, and hangs the code until the order is filled. 

        :symbol:    Symbol of the asset to buy
        :quantity:  Quantity of asset to buy
        :in_force:  Duration the order is in force
        :extended:  Whether to trade in extended hours or not. 

        :returns: The result of order_limit(). Returns None if there is an issue with the parameters.
        """
        ret = self.buy(symbol, quantity, in_force, extended)
        if symbol[0] == '@':
            check = self.trader.order.fetch_crypto_order_status
        else:
            check = self.trader.order.fetch_stock_order_status
        while True:
            time.sleep(0.5)
            stat = check(ret["id"])
            if stat['status'] == 'filled':
                return stat

    def sell(self, symbol: str=None, quantity: int=0, in_force: str='gtc', extended: bool=False):
        """Sells the sepcified asset.

        :symbol:    Symbol of the asset to buy
        :quantity:  Quantity of asset to buy
        :in_force:  Duration the order is in force
        :extended:  Whether to trade in extended hours or not. 

        :returns: The result of order_limit(). Returns None if there is an issue with the parameters.
        """
        if symbol == None:
            symbol = self.watch[0]
        
        if isinstance(quantity, str):
            for p in self.trader.stock_positions + self.trader.crypto_positions:
                if p['symbol'] == symbol:
                    quantity = p['quantity']
                    break
        if quantity < 0.00001:
            debug(f"SELL quantity {quantity} is too little")
            return None
       
        price = self.trader.queue.get_last_symbol_interval_price(symbol, self.fetch_interval, 'close') 
        limit_price = round(price * 0.95, 2)
       
        return self.order_limit('sell', symbol, quantity, limit_price, in_force, extended)

    def await_sell(self, symbol: str=None, quantity: int=0, in_force: str='gtc', extended: bool=False):
        """Sells the specified asset, and hangs the code until the order is filled. 

        :symbol:    Symbol of the asset to buy
        :quantity:  Quantity of asset to buy
        :in_force:  Duration the order is in force
        :extended:  Whether to trade in extended hours or not. 

        :returns: The result of order_limit(). Returns None if there is an issue with the parameters.
        """
        ret = self.sell(symbol, quantity, in_force, extended)
        
        time.sleep(2)
        while True:
            stat = self.trader.order.fetch_stock_order_status(ret["id"])
            if stat['status'] == 'filled':
                return stat
            time.sleep(1)
       
    def order_option_limit(self, side: str, symbol: str, quantity: float, limit_price: float, type: str, 
        exp_date: dt.datetime, strike: float, in_force: str='gtc'):
        """Order an option.

        :side:      'buy' or 'sell'
        :symbol:    symbol of asset
        :in_force:  
        :limit_price: limit price
        :quantity:  quantity to sell or buy
        :exp_date:  expiration date
        :strike:    strike price
        :type:      'call' or 'put'

        :returns: A dictionary with the following keys and values:
            - type: 'OPTION'
            - id: ID of order
            - symbol: symbol of asset
            Raises an exception if order fails. 
        """
        raise Exception("This endpoint is not supported in this broker")
    
    def buy_option(self, symbol: str=None, quantity: int=0, in_force: str='gtc'):
        """Buys the sepcified option.
        
        :symbol:    Symbol of the asset to buy, in OCC format. 
        :quantity:  Quantity of asset to buy
        :in_force:  Duration the order is in force

        :returns: The result of order_option_limit(). Returns None if there is an issue with the parameters.
        """
        if symbol == None:
            return None
        buy_power = self.trader.account['buying_power']
        price = self.trader.streamer.fetch_option_market_data(symbol)['price']
        limit_price = round(price * 1.05, 2)
        total_price = limit_price * quantity
        
        if total_price >= buy_power:
            debug("Not enough buying power")
            return None
        if quantity <= 0:
            debug("Quantity must be greater than 0")
            return None
        
        sym, date, option_type, strike = self.occ_to_data(symbol)
        return self.order_option_limit('buy', sym, quantity, limit_price, option_type, date, strike, in_force=in_force)

    def sell_option(self, symbol: str=None, quantity: int=0, in_force: str='gtc'):
        """Sells the sepcified option.
        
        :symbol:    Symbol of the asset to buy, in OCC format. 
        :quantity:  Quantity of asset to buy
        :in_force:  Duration the order is in force

        :returns: The result of order_option_limit(). Returns None if there is an issue with the parameters.
        """
        if symbol == None:
            return None
        if isinstance(quantity, str):
            for p in self.trader.stock_positions + self.trader.crypto_positions + self.trader.option_positions:
                if p['symbol'] == symbol:
                    quantity = p['quantity']
                    break
        if quantity < 0.00001:
            debug(f"SELL quantity {quantity} is too little")
            return None
       
        price = self.trader.streamer.fetch_option_market_data(symbol)['price']
        limit_price = round(price * 0.95, 2)
       
        sym, date, option_type, strike = self.occ_to_data(symbol)
        return self.order_option_limit('sell', sym, quantity, limit_price, option_type, date, strike, in_force=in_force)

    ############# Helper functions #################

    def data_to_occ(self, symbol: str, date: dt.datetime, option_type: str, price: float):
        """Converts data into a OCC format string 
        """
        occ = symbol+((6-len(symbol))*' ')
        occ = occ+date.strftime('%y%m%d')
        occ = occ+'C' if option_type == 'call' else occ+'P'
        occ = occ+f'{int(price*1000):08}'

        return occ
    
    def occ_to_data(self, symbol: str):
        sym = symbol[0:6].replace(' ', '')
        date =  dt.datetime.strptime(symbol[6:12], '%y%m%d')
        option_type = 'call' if symbol[12] == 'C' else 'put'
        price = float(symbol[13:])/1000
        return sym, date, option_type, price