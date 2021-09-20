# Builtins
import datetime as dt
import time
from pathlib import Path
import yaml
import traceback
import threading
from typing import List, Dict, Any

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

    interval_list = [
        Interval.MIN_1,
        Interval.MIN_5,
        Interval.MIN_15,
        Interval.MIN_30,
        Interval.HR_1,
        Interval.DAY_1,
    ]

    def __init__(self, path: str = None):
        """
        Performs initializations of the class, such as setting the
        timestamp and loading credentials.

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
        self.trader = (
            None  # Allows broker to handle the case when runs without a trader
        )

        if path is None:
            path = "./secret.yaml"
        # Check if file exists
        yml_file = Path(path)
        if not yml_file.is_file() and not self.create_secret(path):
            debugger.debug("Broker not initalized with account information.")
            return
        with open(path, "r") as stream:
            self.config = yaml.safe_load(stream)

        self.timestamp = now()

    def create_secret(self, path: str):
        """
        This method is called when the yaml file with credentials
        is not found."""
        raise Exception(f"{path} was not found")

    def refresh_cred(self):
        """
        Most API endpoints, for security reasons, require a refresh of the access token
        every now and then. This method should perform a refresh of the access token.
        """
        pass

    def setup(self, interval: Dict, trader=None, trader_main=None) -> None:
        """
        This function is called right before the algorithm begins,
        and initializes several runtime parameters like
        the symbols to watch and what interval data is needed.
        """

        self.trader = trader
        self.trader_main = trader_main

        min_interval = None
        for sym in interval:
            inter = interval[sym]["interval"]
            # If the specified interval is not supported on this API, raise Exception
            if inter < self.interval_list[0]:
                raise Exception(f"Specified interval {inter} is not supported.")
            # If the exact inteval is not supported but it can be recreated by aggregating
            # candles from a more granular interval
            if inter not in self.interval_list:
                granular_int = [i for i in self.crypto_interval_list if i < inter]
                new_inter = granular_int[-1]
                interval[sym]["aggregations"].append(inter)
                interval[sym]["interval"] = new_inter

            if min_interval is None or interval[sym]["interval"] < min_interval:
                min_interval = interval[sym]["interval"]

        self.interval = interval
        self.poll_interval = min_interval
        debugger.debug(f"Interval: {self.interval}")
        debugger.debug(f"Poll Interval: {self.poll_interval}")
        debugger.debug(f"{type(self).__name__} setup finished")

    def start(self):
        """
        This method begins streaming data from the API.

        The default implementation below is for polling the API.
        If your brokerage provides a streaming API, you should override
        this method and configure it to use that API. In that case,
        make sure to set the callback function to self.main().

        :kill_switch: A flag to indicate whether the algorithm should stop
            after a single iteration. Usually used for testing.
        """
        cur_min = -1
        val, unit = expand_interval(self.poll_interval)

        debugger.info(f"{type(self).__name__} started...")
        if unit == "MIN":
            sleep = val * 60 - 10
            while 1:
                cur = now()
                minutes = cur.minute
                if minutes % val == 0 and minutes != cur_min:
                    self.timestamp = cur
                    self.main()
                    time.sleep(sleep)
                cur_min = minutes
        elif unit == "HR":
            sleep = val * 3600 - 60
            while 1:
                cur = now()
                minutes = cur.minute
                if minutes == 0 and minutes != cur_min:
                    self.timestamp = cur
                    self.main()
                    time.sleep(sleep)
                cur_min = minutes
        else:
            while 1:
                cur = now()
                minutes = cur.minute
                hours = cur.hour
                if hours == 19 and minutes == 50:
                    self.timestamp = cur
                    self.main()
                    time.sleep(80000)
                cur_min = minutes

    def main(self):
        """
        This method is called at the interval specified by the user.
        It should create a dictionary where each key is the symbol for an asset,
        and the value is the corresponding data in the following pandas dataframe format:
                      Symbol
                      open   high    low close   volume
            timestamp
            ---       ---    ---     --- ---     ---

        timestamp should be an offset-aware datetime object in UTC timezone.

        The dictionary should be passed to the trader by calling `self.trader_main(dict)`
        """
        # Iterate through securities in the watchlist. For those that have
        # intervals that needs to be called now, fetch the latest data

        df_dict = {}
        for sym in self.interval:
            inter = self.interval[sym]["interval"]
            if is_freq(self.timestamp, inter):
                n = self.timestamp
                latest = self.fetch_price_history(
                    sym, inter, n - interval_to_timedelta(inter), n
                )
                df_dict[sym] = latest.iloc[-1]

        self.trader_main(df_dict)

    def exit(self):
        """
        This function is called after every invocation of algo's handler.
        The intended purpose is for brokers to clear any cache it may have created.
        """
        debugger.info(f"{type(self).__name__} exited")

    def _exception_handler(func):
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
                    self = args[0]
                    debugger.error(f"Error: {e}")
                    traceback.print_exc()
                    debugger.error("Logging out and back in...")
                    args[0].refresh_cred()
                    tries = tries - 1
                    debugger.error("Retrying...")
                    continue

        return wrapper

    def _run_once(func):
        """ """

        def wrapper(*args, **kwargs):
            self = args[0]
            if self.run_count == 0:
                self.run_count += 1
                return func
            return None

        return wrapper

    # -------------- Streamer methods -------------- #

    def fetch_price_history(
        self,
        symbol: str,
        interval: Interval,
        start: dt.datetime = None,
        end: dt.datetime = None,
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

    def order_limit(
        self,
        side: str,
        symbol: str,
        quantity: float,
        limit_price: float,
        in_force: str = "gtc",
        extended: bool = False,
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

    def order_option_limit(
        self,
        side: str,
        symbol: str,
        quantity: float,
        limit_price: float,
        type: str,
        exp_date: dt.datetime,
        strike: float,
        in_force: str = "gtc",
    ):
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

    def buy(
        self, symbol: str, quantity: int, in_force: str = "gtc", extended: bool = False
    ):
        """
        Buys the specified asset.

        :symbol:    Symbol of the asset to buy
        :quantity:  Quantity of asset to buy
        :in_force:  Duration the order is in force
        :extended:  Whether to trade in extended hours or not.

        :returns: The result of order_limit(). Returns None if there is an issue with the parameters.
        """
        if quantity <= 0.0:
            debugger.error(
                f"Quantity cannot be less than or equal to 0: was given {quantity}"
            )
            return None
        if self.trader is None:
            buy_power = self.fetch_account()["buying_power"]
            # If there is no trader, streamer must be manually set
            price = self.streamer.fetch_price_history(
                symbol,
                self.interval[symbol]["interval"],
                now() - dt.timedelta(days=7),
                now(),
            )[symbol]["close"][-1]
        else:
            buy_power = self.trader.account["buying_power"]
            price = self.trader.storage.load(symbol, self.interval[symbol]["interval"])[
                symbol
            ]["close"][-1]

        limit_price = mark_up(price)
        total_price = limit_price * quantity

        if total_price >= buy_power:
            debugger.error(
                f"""Not enough buying power.\n Total price ({price} * {quantity} * 1.05 = {limit_price*quantity}) exceeds buying power {buy_power}.\n Reduce purchase quantity or increase buying power."""
            )
            return None

        debugger.debug(f"{type(self).__name__} ordered a buy of {quantity} {symbol}")
        return self.order_limit(
            "buy", symbol, quantity, limit_price, in_force, extended
        )

    def sell(
        self,
        symbol: str = None,
        quantity: int = 0,
        in_force: str = "gtc",
        extended: bool = False,
    ):
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
            debugger.warning(
                f"Quantity cannot be less than or equal to 0: was given {quantity}"
            )
            return None

        if self.trader is None:
            price = self.streamer.fetch_price_history(
                symbol,
                self.interval[symbol]["interval"],
                now() - dt.timedelta(days=7),
                now(),
            )[symbol]["close"][-1]
        else:
            price = self.trader.storage.load(symbol, self.interval[symbol]["interval"])[
                symbol
            ]["close"][-1]

        limit_price = mark_down(price)

        debugger.debug(f"{type(self).__name__} ordered a sell of {quantity} {symbol}")
        return self.order_limit(
            "sell", symbol, quantity, limit_price, in_force, extended
        )

    def buy_option(self, symbol: str, quantity: int = 0, in_force: str = "gtc"):
        """
        Buys the specified option.

        :symbol:    Symbol of the asset to buy, in OCC format.
        :quantity:  Quantity of asset to buy
        :in_force:  Duration the order is in force

        :returns: The result of order_option_limit(). Returns None if there is an issue with the parameters.
        """
        if quantity <= 0.0:
            debugger.warning(
                f"Quantity cannot be less than or equal to 0: was given {quantity}"
            )
            return None
        if self.trader is None:
            buy_power = self.fetch_account()["buying_power"]
            price = self.streamer.fetch_option_market_data(symbol)["price"]
        else:
            buy_power = self.trader.account["buying_power"]
            price = self.trader.streamer.fetch_option_market_data(symbol)["price"]

        limit_price = mark_up(price)
        total_price = limit_price * quantity

        if total_price >= buy_power:
            debugger.warning(
                f"""
Not enough buying power 🏦.\n
Total price ({price} * {quantity} * 1.05 = {limit_price*quantity}) exceeds buying power {buy_power}.\n
Reduce purchase quantity or increase buying power."""
            )

        sym, date, option_type, strike = self.occ_to_data(symbol)
        return self.order_option_limit(
            "buy",
            sym,
            quantity,
            limit_price,
            option_type,
            date,
            strike,
            in_force=in_force,
        )

    def sell_option(self, symbol: str, quantity: int = 0, in_force: str = "gtc"):
        """
        Sells the specified option.

        :symbol:    Symbol of the asset to buy, in OCC format.
        :quantity:  Quantity of asset to buy
        :in_force:  Duration the order is in force

        :returns: The result of order_option_limit(). Returns None if there is an issue with the parameters.
        """
        if quantity <= 0.0:
            debugger.warning(
                f"Quantity cannot be less than or equal to 0: was given {quantity}"
            )
            return None
        if self.trader is None:
            price = self.streamer.fetch_option_market_data(symbol)["price"]
        else:
            price = self.trader.streamer.fetch_option_market_data(symbol)["price"]

        limit_price = mark_down(price)

        sym, date, option_type, strike = self.occ_to_data(symbol)
        return self.order_option_limit(
            "sell",
            sym,
            quantity,
            limit_price,
            option_type,
            date,
            strike,
            in_force=in_force,
        )

    # -------------- Helper methods -------------- #

    def has_interval(self, interval: str):
        return interval in self.interval_list

    def data_to_occ(
        self, symbol: str, date: dt.datetime, option_type: str, price: float
    ):
        """
        Converts data into a OCC format string
        """
        occ = symbol + ((6 - len(symbol)) * " ")
        occ = occ + date.strftime("%y%m%d")
        occ = occ + "C" if option_type == "call" else occ + "P"
        occ = occ + f"{int(price*1000):08}"
        return occ

    def occ_to_data(self, symbol: str):
        sym = ""
        while symbol[0].isalpha():
            sym = sym + symbol[0]
            symbol = symbol[1:]
        symbol = symbol.replace(" ", "")
        date = dt.datetime.strptime(symbol[0:6], "%y%m%d")
        option_type = "call" if symbol[6] == "C" else "put"
        price = float(symbol[7:]) / 1000
        return sym, date, option_type, price

    def current_timestamp(self):
        return self.timestamp


class StreamAPI(API):
    """ """

    def __init__(self, path: str = None):
        super().__init__(path)

        self.block_lock = (
            threading.Lock()
        )  # Lock for streams that receive data asynchronously.
        self.block_queue = {}
        self.first = True

    def setup(self, interval: Dict, trader=None, trader_main=None) -> None:
        super().setup(interval, trader, trader_main)
        self.blocker = {}

    def start(self):
        debugger.debug(f"{type(self).__name__} started...")

    def main(self, df_dict):
        """
        Streaming is event driven, so sometimes not all data comes in at once.
        StreamAPI class
        """
        self.block_lock.acquire()
        got = [k for k in df_dict]
        # First, identify which symbols need to have data fetched
        # for this timestamp
        if self.first:
            self.needed = [
                sym
                for sym in self.interval
                if is_freq(now(), self.interval[sym]["interval"])
            ]
            self.timestamp = df_dict[got[0]].index[0]

        debugger.debug(f"Needs: {self.needed}")
        debugger.debug(f"Got data for: {got}")
        missing = list(set(self.needed) - set(got))
        debugger.debug(f"Still need data for: {missing}")

        self.block_queue.update(df_dict)
        # debugger.debug(self.block_queue)

        # If all data has been received, pass on the data
        if len(missing) == 0:
            debugger.debug("All data received")
            self.trader_main(self.block_queue)
            self.block_queue = {}
            self.all_recv = True
            self.first = True
            self.block_lock.release()
            return

        # If there are data that has not been received, start a timer
        if self.first:
            timer = threading.Thread(target=self.timeout, daemon=True)
            timer.start()
            self.all_recv = False
            self.first = False

        self.needed = missing
        self.got = got
        self.block_lock.release()

    def timeout(self):
        debugger.debug("Begin timeout timer")
        time.sleep(1)
        if not self.all_recv:
            debugger.debug("Force flush")
            self.flush()

    def flush(self):
        # For missing data, repeat the existing one
        self.block_lock.acquire()
        for n in self.needed:
            data = (
                self.trader.storage.load(n, self.interval[n]["interval"])
                .iloc[[-1]]
                .copy()
            )
            data.index = [self.timestamp]
            self.block_queue[n] = data
        self.block_lock.release()
        self.trader_main(self.block_queue)
        self.block_queue = {}
