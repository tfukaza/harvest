# Builtins
import datetime as dt
import time
from logging import debug, warning
from typing import Any, Callable, Dict, List 
from pathlib import Path
import yaml
import traceback

# External libraries
import pandas as pd

# Submodule imports
from harvest.utils import *

class API:
    """
    The API class communicates with various API endpoints to perform the
    necessary operations. The Base class defines the interface for all API classes to 
    extend and implement.

    Attributes
    :interval_list: A list of supported intervals.
    :fetch_interval: A string indicating the interval the broker fetches the latest asset data.  
        This should be initialized in setup_run (see below).
    """
    
    def __init__(self, path: str=None):
        """
        Here, you should perform any authentications necessary to 
        communicate with the API this class is using. 

        There are three API class types, 'streamer', 'broker', and 'both'. A 
        'streamer' is responsible for fetching data and interacting with 
        the queue to store data. A 'broker' is used solely for buying and 
        selling stocks, cryptos and options. Finally, 'both' is used to 
        indicate that the broker fetch data and buy and sell stocks.
        
        All subclass implementations should call this __init__ method
        using `super().__init__(path)`.

        :path: path to the YAML file containing credentials to communicate with the API. 
            If not specified, defaults to './secret.yaml'
        """
        self.trader = None # Allows broker to handle the case when runs without a trader
        
        if path == None:
            path = './secret.yaml'
        # Check if file exists
        yml_file = Path(path)
        if not yml_file.is_file():
            if not self.no_secret(path):
                return 
        with open(path, 'r') as stream:
            self.config = yaml.safe_load(stream)
    
    def no_secret(self, path: str): 
        """
        This method is called when the yaml file with credentials 
        is not found. """
        raise Exception(f"{path} was not found")
    
    def refresh_cred(self):
        """
        Most API endpoints, for security reasons, require a refresh of the access token
        every now and then. This method should perform a refresh of the access token. 
        """
        pass

    def setup(self, watch: List[str], interval: str, fetch_interval:str, trader=None, trader_main=None) -> None:
        """
        This function is called right before the algorithm begins.

        On top of performing any configurations and input checks,
        this method must initialize the following attributes:
        
        :watch: A list containing strings of stock/crypto (but not option) symbols this class should 
            keep track of. Cryptos are prepended with a '@' to distinguish them from stocks.
        :interval: A string specifying the interval to run the algorithm.
        :fetch_interval: A string specifying the interval to collect data. 
            For example, say a broker only provides 1MIN data. If the user wants to 
            run the algorithm at 5MIN, fetch_interval should be set to '1MIN'.
            The Trader class will then automatically resample the 1MIN data to 
            5MIN data.
        :trader: A reference to the Trader class. 
        :trader_main: A reference to a method in the Trader class that invokes 
            the algorithm
        """
        self.watch = watch 
        self.interval = interval 
        self.fetch_interval = fetch_interval
        self.trader = trader
        self.trader_main = trader_main

    def start(self, kill_switch: bool=False):
        """
        This method begins streaming data from the API.

        The default implementation below is for polling the API.
        If your brokerage provides a streaming API, you should override
        this method and configure it to use that API. In that case,
        make sure to set the callback function to self.main().

        :kill_switch: A flag to indicate whether the algorithm should stop 
            after a single iteration. Usually used for testing.
        """
        self.cur_hr = -1
        self.cur_min = -1
        val, unit = expand_interval(self.fetch_interval)
        
        print("Running...")
        # kill_switch is true for testing purposes to prevent an infinite 
        # loop after streamer.main is called.
        if kill_switch:
            self.main()
            return
        
        if unit == 'MIN':
            sleep = val * 60 - 10
            while 1:
                cur = now()
                minutes = cur.minute
                if minutes % val == 0 and minutes != self.cur_min:
                    self.main()
                    time.sleep(sleep)
                self.cur_min = minutes
        elif unit == 'HR':
            sleep = val * 3600 - 60
            while 1:
                cur = now()
                minutes = cur.minute
                if minutes == 0 and minutes != self.cur_min:
                    self.main()
                    time.sleep(sleep)
                self.cur_min = minutes
        else:
            while 1:
                cur = now()
                minutes = cur.minute
                hours = cur.hour
                if hours == 19 and minutes == 50:
                    self.main()
                    time.sleep(80000)
                self.cur_min = minutes
            

    def main(self) -> Dict[str, pd.DataFrame]:
        """
        This function should be called at the specified interval, and return data.
        For brokers that use streaming, this often means specifying this function as a callback.
        For brokers that use polling, this often means calling whatever endpoint is needed to 
        obtain stock/crypto data, at the specified interval.

        This method should create a dictionary where each key is the symbol for an asset, 
        and the value is the corresponding data in the following pandas dataframe format:
                      Symbol                              
                      open   high    low close   volume       
            timestamp
            ---       ---    ---     --- ---     ---         

        timestamp should be an offset-aware datetime object in UTC timezone.
        
        The dictionary should be passed to the trader by calling `self.trader_main(dict)` 
        """
        raise NotImplementedError("This endpoint is not supported in this broker")

    def exit(self):
        """
        This function is called after every invocation of algo's handler. 
        The intended purpose is for brokers to clear any cache it may have created.
        """
        pass

    def _exception_handler( func ):
        """
        Wrapper to handle unexpected errors in the wrapped function. 
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
                    debug(f"Error: {e}")
                    traceback.print_exc()
                    # debug("Logging out and back in...")
                    # args[0].refresh_cred()
                    tries = tries - 1 
                    debug("Retrying...")
                    continue
            raise Exception(f"{func} failed")
        return wrapper

    # -------------- Streamer methods -------------- #

    def fetch_price_history(self,
        symbol: str,
        interval: str,
        start: dt.datetime=None, 
        end: dt.datetime=None, 
        ):
        """
        Fetches historical price data for the specified asset and period 
        using the API.

        :param symbol: The stock/crypto to get data for.
        :param interval: The interval of requested historical data.
        :param start: The starting date of the period, inclusive.
        :param end: The ending date of the period, inclusive.
        :returns: A pandas dataframe, same format as main()
        """
        raise NotImplementedError("This endpoint is not supported in this broker")

    def fetch_chain_info(self, symbol: str):
        """
        Returns information about the symbol's options
        
        :param symbol: Stock symbol. Cannot use crypto.
        :returns: A dict with the following keys and values:
            - id: ID of the option chain 
            - exp_dates: List of expiration dates as datetime objects
            - multiplier: Multiplier of the option, usually 100 
        """ 
    
    def fetch_chain_data(self, symbol: str):
        """
        Returns the option chain for the specified symbol. 
        
        :param symbol: Stock symbol. Cannot use crypto.
        :returns: A dataframe in the following format:

                    exp_date strike  type   
            OCC
            ---     ---      ---     ---        
        exp_date should be a timezone-aware datetime object localized to UTC
        """ 
        raise NotImplementedError("This endpoint is not supported in this broker")
    
    def fetch_option_market_data(self, symbol: str):
        """
        Retrieves data of specified option. 

        :param symbol:    OCC symbol of option
        :returns:   A dictionary:
            - price: price of option 
            - ask: ask price
            - bid: bid price
        """
        raise NotImplementedError("This endpoint is not supported in this broker") 
    
    # ------------- Broker methods ------------- #

    def fetch_stock_positions(self):
        """
        Returns all current stock positions
        
        :returns: A list of dictionaries with the following keys and values:
            - symbol: Ticker symbol of the stock
            - avg_price: The average price the stock was bought at
            - quantity: Quantity owned
        """
        raise NotImplementedError("This endpoint is not supported in this broker")

    def fetch_option_positions(self):
        """
        Returns all current option positions
        
        :returns: A list of dictionaries with the following keys and values:
            - symbol: Ticker symbol of the underlying stock
            - occ_symbol: OCC symbol of the option
            - avg_price: Average price the option was bought at
            - quantity: Quantity owned
            - multiplier: How many stocks each option represents
            - exp_date: When the option expires
            - strike_price: Strike price of the option
            - type: 'call' or 'put'
        """
        raise NotImplementedError("This endpoint is not supported in this broker")

    def fetch_crypto_positions(self):
        """
        Returns all current crypto positions
        
        :returns: A list of dictionaries with the following keys and values:
            - symbol: Ticker symbol for the crypto, prepended with an '@'
            - avg_price: The average price the crypto was bought at
            - quantity: Quantity owned
        """
        raise NotImplementedError("This endpoint is not supported in this broker")
    
    def update_option_positions(self, positions: List[Any]):
        """
        Updates entries in option_positions list with the latest option price. 
        This is needed as options are priced based on various metrics, 
        and cannot be easily calculated from stock prices. 

        :positions: The option_positions list in the Trader class. 
        :returns: Nothing
        """
        raise NotImplementedError("This endpoint is not supported in this broker")

    def fetch_account(self):
        """
        Returns current account information from the brokerage. 
        
        :returns: A dictionary with the following keys and values:
            - equity: Total assets in the brokerage
            - cash: Total cash in the brokerage
            - buying_power: Total buying power
            - multiplier: Scale of leverage, if leveraging
        """
        raise NotImplementedError("This endpoint is not supported in this broker")
    
    def fetch_stock_order_status(self, id):
        """
        Returns the status of a stock order with the given id.

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
        raise NotImplementedError("This endpoint is not supported in this broker")
    
    def fetch_option_order_status(self, id):
        """
        Returns the status of a option order with the given id.

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
        raise NotImplementedError("This endpoint is not supported in this broker")
    
    def fetch_crypto_order_status(self, id):
        """
        Returns the status of a crypto order with the given id.

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
        raise NotImplementedError("This endpoint is not supported in this broker")
    
    def fetch_order_queue(self):
        """
        Returns all current pending orders 
        
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
        raise NotImplementedError("This endpoint is not supported in this broker")

    # --------------- Methods for Trading --------------- #

    def order_limit(self, 
        side: str, 
        symbol: str,
        quantity: float, 
        limit_price: float, 
        in_force: str='gtc', 
        extended: bool=False, 
        ):
        """
        Places a limit order. 

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
        raise NotImplementedError("This endpoint is not supported in this broker")
    
    def order_option_limit(self, side: str, symbol: str, quantity: float, limit_price: float, type: str, 
        exp_date: dt.datetime, strike: float, in_force: str='gtc'):
        """
        Order an option.

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
        raise NotImplementedError("This endpoint is not supported in this broker")

    # -------------- Built-in methods -------------- #
    # These do not need to be re-implemented in a subclass

    def buy(self, symbol: str, quantity: int, in_force: str='gtc', extended: bool=False):
        """
        Buys the specified asset.

        :symbol:    Symbol of the asset to buy
        :quantity:  Quantity of asset to buy
        :in_force:  Duration the order is in force
        :extended:  Whether to trade in extended hours or not. 

        :returns: The result of order_limit(). Returns None if there is an issue with the parameters.
        """
        if quantity <= 0.0:
            warning(f"Quantity cannot be less than or equal to 0: was given {quantity}")
            return None
        if self.trader is None:
            buy_power = self.fetch_account()['buying_power']
            price = self.streamer.fetch_price_history( symbol, self.interval, now() - dt.timedelta(days=7), now())[symbol]['close'][-1]
        else:
            buy_power = self.trader.account['buying_power']
            price = self.trader.storage.load(symbol, self.interval)[symbol]['close'][-1]

        limit_price = mark_up(price)
        total_price = limit_price * quantity
        
        if total_price >= buy_power:
            warning(f"""Not enough buying power.\n Total price ({price} * {quantity} * 1.05 = {limit_price*quantity}) exceeds buying power {buy_power}.\n Reduce purchase quantity or increase buying power.""")
            return None

        return self.order_limit('buy', symbol, quantity, limit_price, in_force, extended)
    
    def await_buy(self, symbol: str=None, quantity: int=0, in_force: str='gtc', extended: bool=False):
        """
        Buys the specified asset, and hangs the code until the order is filled. 

        :symbol:    Symbol of the asset to buy
        :quantity:  Quantity of asset to buy
        :in_force:  Duration the order is in force
        :extended:  Whether to trade in extended hours or not. 

        :returns: The result of order_limit(). Returns None if there is an issue with the parameters.
        """
        ret = self.buy(symbol, quantity, in_force, extended)

        if self.trader is None:
            if is_crypto(symbol):
                check = self.fetch_crypto_order_status
            else:
                check = self.fetch_stock_order_status
        else:
            if is_crypto(symbol):
                check = self.trader.broker.fetch_crypto_order_status
            else:
                check = self.trader.broker.fetch_stock_order_status

        while True:
            time.sleep(0.5)
            stat = check(ret["id"])
            if stat['status'] == 'filled':
                return stat

    def sell(self, symbol: str=None, quantity: int=0, in_force: str='gtc', extended: bool=False):
        """Sells the specified asset.

        :symbol:    Symbol of the asset to buy
        :quantity:  Quantity of asset to buy
        :in_force:  Duration the order is in force
        :extended:  Whether to trade in extended hours or not. 

        :returns: The result of order_limit(). Returns None if there is an issue with the parameters.
        """
        if symbol == None:
            symbol = self.watch[0]
        if quantity <= 0.0:
            warning(f"Quantity cannot be less than or equal to 0: was given {quantity}")
            return None
       
        if self.trader is None:
            price = self.streamer.fetch_price_history(symbol, self.interval, now() - dt.timedelta(days=7), now())[symbol]['close'][-1]
        else:
            price = self.trader.storage.load(symbol, self.interval)[symbol]['close'][-1]

        limit_price = mark_down(price)
       
        return self.order_limit('sell', symbol, quantity, limit_price, in_force, extended)

    def await_sell(self, symbol: str=None, quantity: int=0, in_force: str='gtc', extended: bool=False):
        """
        Sells the specified asset, and hangs the code until the order is filled. 

        :symbol:    Symbol of the asset to buy
        :quantity:  Quantity of asset to buy
        :in_force:  Duration the order is in force
        :extended:  Whether to trade in extended hours or not. 

        :returns: The result of order_limit(). Returns None if there is an issue with the parameters.
        """
        ret = self.sell(symbol, quantity, in_force, extended)
        
        time.sleep(2)
        while True:
            if self.trader is None:
                stat = self.fetch_stock_order_status(ret["id"])
            else:
                stat = self.trader.broker.fetch_stock_order_status(ret["id"])
            if stat['status'] == 'filled':
                return stat
            time.sleep(1)
       
    def buy_option(self, symbol: str, quantity: int=0, in_force: str='gtc'):
        """
        Buys the specified option.
        
        :symbol:    Symbol of the asset to buy, in OCC format. 
        :quantity:  Quantity of asset to buy
        :in_force:  Duration the order is in force

        :returns: The result of order_option_limit(). Returns None if there is an issue with the parameters.
        """
        if quantity <= 0.0:
            warning(f"Quantity cannot be less than or equal to 0: was given {quantity}")
            return None
        if self.trader is None:
            buy_power = self.fetch_account()['buying_power']
            price = self.streamer.fetch_option_market_data(symbol)['price']
        else:
            buy_power = self.trader.account['buying_power']
            price = self.trader.streamer.fetch_option_market_data(symbol)['price']

        limit_price = mark_up(price)
        total_price = limit_price * quantity
        
        if total_price >= buy_power:
            warning(f"""
Not enough buying power 🏦.\n
Total price ({price} * {quantity} * 1.05 = {limit_price*quantity}) exceeds buying power {buy_power}.\n
Reduce purchase quantity or increase buying power.""")
        
        sym, date, option_type, strike = self.occ_to_data(symbol)
        return self.order_option_limit('buy', sym, quantity, limit_price, option_type, date, strike, in_force=in_force)

    def sell_option(self, symbol: str, quantity: int=0, in_force: str='gtc'):
        """
        Sells the specified option.
        
        :symbol:    Symbol of the asset to buy, in OCC format. 
        :quantity:  Quantity of asset to buy
        :in_force:  Duration the order is in force

        :returns: The result of order_option_limit(). Returns None if there is an issue with the parameters.
        """
        if quantity <= 0.0:
            warning(f"Quantity cannot be less than or equal to 0: was given {quantity}")
            return None
        if self.trader is None:
            price = self.streamer.fetch_option_market_data(symbol)['price']
        else:
            price = self.trader.streamer.fetch_option_market_data(symbol)['price']
            
        limit_price = mark_down(price)
       
        sym, date, option_type, strike = self.occ_to_data(symbol)
        return self.order_option_limit('sell', sym, quantity, limit_price, option_type, date, strike, in_force=in_force)

    # -------------- Helper methods -------------- #
    
    def has_interval(self, interval: str):
        return interval in self.interval_list

    def data_to_occ(self, symbol: str, date: dt.datetime, option_type: str, price: float):
        """
        Converts data into a OCC format string 
        """
        occ = symbol+((6-len(symbol))*' ')
        occ = occ+date.strftime('%y%m%d')
        occ = occ+'C' if option_type == 'call' else occ+'P'
        occ = occ+f'{int(price*1000):08}'
        return occ
    
    def occ_to_data(self, symbol: str):
        sym = ''
        while symbol[0].isalpha():
            sym = sym + symbol[0]
            symbol = symbol[1:]
        symbol = symbol.replace(' ', '')
        date =  dt.datetime.strptime(symbol[0:6], '%y%m%d')
        option_type = 'call' if symbol[6] == 'C' else 'put'
        price = float(symbol[7:])/1000
        return sym, date, option_type, price
    