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
    :exchange: The market the API trades on. Ignored if the API is not a broker.
    """

    interval_list = [
        Interval.MIN_1,
        Interval.MIN_5,
        Interval.MIN_15,
        Interval.MIN_30,
        Interval.HR_1,
        Interval.DAY_1,
    ]

    exchange = ""

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

        if path is None:
            path = "./secret.yaml"
        # Check if file exists
        yml_file = Path(path)
        if not yml_file.is_file() and not self.create_secret(path):
            debugger.debug("Broker not initalized with account information.")
        else:
            with open(path, "r") as stream:
                self.config = yaml.safe_load(stream)

        self.timestamp = now()

    def create_secret(self, path: str):
        """
        This method is called when the yaml file with credentials
        is not found."""
        # raise Exception(f"{path} was not found.")
        debugger.warning(f"Assuming API does not need account information.")
        return False

    def refresh_cred(self):
        """
        Most API endpoints, for security reasons, require a refresh of the access token
        every now and then. This method should perform a refresh of the access token.
        """
        debugger.info(f"Refreshing credentials for {type(self).__name__}.")

    def setup(self, stats: Stats, trader_main=None) -> None:
        """
        This function is called right before the algorithm begins,
        and initializes several runtime parameters like
        the symbols to watch and what interval data is needed.

        :trader_main: A callback function to the trader which will pass the data to the algorithms.
        """

        self.trader_main = trader_main
        self.stats = stats
        self.stats.timestamp = now()

        min_interval = None
        for sym in stats.watchlist_cfg:
            inter = stats.watchlist_cfg[sym]["interval"]
            # If the specified interval is not supported on this API, raise Exception
            if inter < self.interval_list[0]:
                raise Exception(f"Specified interval {inter} is not supported.")
            # If the exact inteval is not supported but it can be recreated by aggregating
            # candles from a more granular interval
            if inter not in self.interval_list:
                granular_int = [i for i in self.interval_list if i < inter]
                new_inter = granular_int[-1]
                stats.watchlist_cfg[sym]["aggregations"].append(inter)
                stats.watchlist_cfg[sym]["interval"] = new_inter

            if (
                min_interval is None
                or stats.watchlist_cfg[sym]["interval"] < min_interval
            ):
                min_interval = stats.watchlist_cfg[sym]["interval"]

        self.interval = stats.watchlist_cfg
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
        """
        cur_min = -1
        val, unit = expand_interval(self.poll_interval)

        debugger.debug(f"{type(self).__name__} started...")
        if unit == "MIN":
            sleep = val * 60 - 10
            while 1:
                cur = now()
                minutes = cur.minute
                if minutes % val == 0 and minutes != cur_min:
                    self.stats.timestamp = cur
                    self.main()
                    time.sleep(sleep)
                cur_min = minutes
        elif unit == "HR":
            sleep = val * 3600 - 60
            while 1:
                cur = now()
                minutes = cur.minute
                if minutes == 0 and minutes != cur_min:
                    self.stats.timestamp = cur
                    self.main()
                    time.sleep(sleep)
                cur_min = minutes
        else:
            while 1:
                cur = now()
                minutes = cur.minute
                hours = cur.hour
                if hours == 19 and minutes == 50:
                    self.stats.timestamp = cur
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
            if is_freq(self.stats.timestamp, inter):
                n = self.stats.timestamp
                latest = self.fetch_price_history(
                    sym, inter, n - interval_to_timedelta(inter) * 2, n
                )
                debugger.debug(f"{sym} price fetch returned: {latest}")
                if latest is None or latest.empty:
                    continue
                df_dict[sym] = latest.iloc[-1]

        self.trader_main(df_dict)

    def exit(self):
        """
        This function is called after every invocation of algo's handler.
        The intended purpose is for brokers to clear any cache it may have created.
        """
        debugger.debug(f"{type(self).__name__} exited")

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
                    tries -= 1
                    debugger.error("Retrying...")
                    continue

        return wrapper

    def _run_once(func):
        """
        Wrapper to only allows wrapped functions to be run once.

        :func: Function to wrap.
        :returns: The return of the inputted function if it has not been run before and None otherwise.
        """

        ran = False

        def wrapper(*args, **kwargs):
            nonlocal ran
            if not ran:
                ran = True
                return func(*args, **kwargs)
            return None

        return wrapper

    # -------------- Streamer methods -------------- #

    def get_current_time(self):
        return now()

    def fetch_price_history(
        self,
        symbol: str,
        interval: Interval,
        start: dt.datetime = None,
        end: dt.datetime = None,
    ) -> pd.DataFrame:
        """
        Fetches historical price data for the specified asset and period
        using the API. The first row is the earliest entry and the last
        row is the latest entry.

        :param symbol: The stock/crypto to get data for. Note options are not supported.
        :param interval: The interval of requested historical data.
        :param start: The starting date of the period, inclusive.
        :param end: The ending date of the period, inclusive.
        :returns: A pandas dataframe, same format as main()
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support this streamer method: `fetch_price_history`."
        )

    def fetch_latest_price(self, symbol: str) -> float:
        interval = self.poll_interval
        end = self.get_current_time()
        start = end - interval_to_timedelta(interval) * 2
        price = self.fetch_price_history(symbol, interval, start, end)
        return price[symbol]["close"][-1]

    def fetch_chain_info(self, symbol: str):
        """
        Returns information about the symbol's options

        :param symbol: Stock symbol. Cannot use crypto.
        :returns: A dict with the following keys and values:
            - id: ID of the option chain
            - exp_dates: List of expiration dates as datetime objects
            - multiplier: Multiplier of the option, usually 100
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support this streamer method: `fetch_chain_info`."
        )

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
        raise NotImplementedError(
            f"{type(self).__name__} does not support this streamer method: `fetch_chain_data`."
        )

    def fetch_option_market_data(self, symbol: str):
        """
        Retrieves data of specified option.

        :param symbol:    OCC symbol of option
        :returns:   A dictionary:
            - price: price of option
            - ask: ask price
            - bid: bid price
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support this streamer method: `fetch_option_market_data`."
        )

    def fetch_market_hours(self, date: datetime.date):
        """
        Returns the market hours for a given day.
        Hours are based on the exchange specified in the class's 'exchange' attribute.

        :returns: A dictionary with the following keys and values:
            - open: Time the market opens in UTC timezone.
            - close: Time the market closes in UTC timezone.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support this broker method: `fetch_market_hours`."
        )

    # ------------- Broker methods ------------- #

    def fetch_stock_positions(self):
        """
        Returns all current stock positions

        :returns: A list of dictionaries with the following keys and values:
            - symbol: Ticker symbol of the stock
            - avg_price: The average price the stock was bought at
            - quantity: Quantity owned
        """
        debugger.error(
            f"{type(self).__name__} does not support this broker method: `fetch_stock_positions`. Returning an empty list."
        )
        return []

    def fetch_option_positions(self):
        """
        Returns all current option positions

        :returns: A list of dictionaries with the following keys and values:
            - symbol: OCC symbol of the option
            - base_symbol: Ticker symbol of the underlying stock
            - avg_price: Average price the option was bought at
            - quantity: Quantity owned
            - multiplier: How many stocks each option represents
            - exp_date: When the option expires
            - strike_price: Strike price of the option
            - type: 'call' or 'put'
        """
        debugger.error(
            f"{type(self).__name__} does not support this broker method: `fetch_option_positions`. Returning an empty list."
        )
        return []

    def fetch_crypto_positions(self):
        """
        Returns all current crypto positions

        :returns: A list of dictionaries with the following keys and values:
            - symbol: Ticker symbol for the crypto, prepended with an '@'
            - avg_price: The average price the crypto was bought at
            - quantity: Quantity owned
        """
        debugger.error(
            f"{type(self).__name__} does not support this broker method: `fetch_crypto_positions`. Returning an empty list."
        )
        return []

    # def update_option_positions(self, positions: List[Any]):
    #     """
    #     Updates entries in option_positions list with the latest option price.
    #     This is needed as options are priced based on various metrics,
    #     and cannot be easily calculated from stock prices.

    #     :positions: The option_positions list in the Trader class.
    #     :returns: Nothing
    #     """
    #     debugger.error(
    #         f"{type(self).__name__} does not support this broker method: `update_option_positions`. Doing nothing."
    #     )

    def fetch_account(self):
        """
        Returns current account information from the brokerage.

        :returns: A dictionary with the following keys and values:
            - equity: Total assets in the brokerage
            - cash: Total cash in the brokerage
            - buying_power: Total buying power
            - multiplier: Scale of leverage, if leveraging
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support this broker method: `fetch_account`."
        )

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
            - filled_time: Time the order was filled
            - filled_price: Price the order was filled at
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support this broker method: `fetch_stock_order_status`."
        )

    def fetch_option_order_status(self, id):
        """
        Returns the status of a option order with the given id.

        :id: ID of the option order

        :returns: A dictionary with the following keys and values:
            - type: 'OPTION'
            - id: ID of the order
            - symbol: OCC symbol of option
            - quantity: Quantity ordered
            - filled_quantity: Quantity filled so far
            - side: 'buy' or 'sell'
            - time_in_force: Time the order is in force
            - status: Status of the order
            - filled_time: Time the order was filled
            - filled_price: Price the order was filled at
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support this broker method: `fetch_option_order_status`."
        )

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
            - filled_time: Time the order was filled
            - filled_price: Price the order was filled at
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support this broker method: `fetch_crypto_order_status`."
        )

    def fetch_order_queue(self):
        """
        Returns all current pending orders

        returns: A list of dictionaries with the following keys and values:
            For stocks and crypto:
                - type: "STOCK" or "CRYPTO"
                - symbol: Symbol of asset
                - quantity: Quantity ordered
                - filled_qty: Quantity filled
                - id: ID of order
                - time_in_force: Time in force
                - status: Status of the order
                - side: 'buy' or 'sell'
                - filled_time: Time the order was filled
                - filled_price: Price the order was filled at
            For options:
                - type: "OPTION",
                - symbol: OCC symbol of option
                - base_symbol:
                - quantity: Quantity ordered
                - filled_qty: Quantity filled
                - filled_time: Time the order was filled
                - filled_price: Price the order was filled at
                - id: ID of order
                - time_in_force: Time in force
                - status: Status of the order
                - legs: A list of dictionaries with keys:
                    - id: id of leg
                    - side: 'buy' or 'sell'
                    Harvest does not support buying multiple options in a single transaction,
                    so legs will always have a length of 1.

        """
        debugger.error(
            f"{type(self).__name__} does not support this broker method: `fetch_order_queue`. Returning an empty list."
        )
        return []

    # --------------- Methods for Trading --------------- #

    def order_stock_limit(
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

        :symbol:    symbol of stock
        :side:      'buy' or 'sell'
        :quantity:  quantity to buy or sell
        :limit_price:   limit price
        :in_force:  'gtc' by default
        :extended:  'False' by default

        :returns: A dictionary with the following keys and values:
            - id: ID of order
            - symbol: symbol of asset
            Raises an exception if order fails.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support this broker method: `order_stock_limit`."
        )

    def order_crypto_limit(
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

        :symbol:    symbol of crypto
        :side:      'buy' or 'sell'
        :quantity:  quantity to buy or sell
        :limit_price:   limit price
        :in_force:  'gtc' by default
        :extended:  'False' by default

        :returns: A dictionary with the following keys and values:
            - id: ID of order
            - symbol: symbol of asset
            Raises an exception if order fails.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support this broker method: `order_crypto_limit`."
        )

    def order_option_limit(
        self,
        side: str,
        symbol: str,
        quantity: float,
        limit_price: float,
        option_type: str,
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
        :option_type:      'call' or 'put'

        :returns: A dictionary with the following keys and values:
            - type: 'OPTION'
            - id: ID of order
            - symbol: symbol of asset
            Raises an exception if order fails.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support this broker method: `order_option_limit`."
        )

    # -------------- Built-in methods -------------- #
    # These do not need to be re-implemented in a subclass

    def buy(
        self,
        symbol: str,
        quantity: int,
        limit_price: float,
        in_force: str = "gtc",
        extended: bool = False,
    ):
        """
        Buys the specified asset.

        :symbol:    Symbol of the asset to buy
        :quantity:  Quantity of asset to buy
        :limit_price:   Limit price to buy at
        :in_force:  Duration the order is in force
        :extended:  Whether to trade in extended hours or not.

        :returns: The result of order_limit(). Returns None if there is an issue with the parameters.
        """

        debugger.debug(f"{type(self).__name__} ordered a buy of {quantity} {symbol}")
        typ = symbol_type(symbol)
        if typ == "STOCK":
            return self.order_stock_limit(
                "buy", symbol, quantity, limit_price, in_force, extended
            )
        elif typ == "CRYPTO":
            return self.order_crypto_limit(
                "buy", symbol[1:], quantity, limit_price, in_force, extended
            )
        elif typ == "OPTION":
            sym, exp_date, option_type, strike = self.occ_to_data(symbol)
            return self.order_option_limit(
                "buy",
                sym,
                quantity,
                limit_price,
                option_type,
                exp_date,
                strike,
                in_force,
            )
        else:
            debugger.error(f"Invalid asset type for {symbol}")

    def sell(
        self,
        symbol: str = None,
        quantity: int = 0,
        limit_price: float = 0.0,
        in_force: str = "gtc",
        extended: bool = False,
    ):
        """Sells the specified asset.

        :symbol:    Symbol of the asset to buy
        :quantity:  Quantity of asset to buy
        :limit_price:   Limit price to buy at
        :in_force:  Duration the order is in force
        :extended:  Whether to trade in extended hours or not.

        :returns: The result of order_limit(). Returns None if there is an issue with the parameters.
        """

        debugger.debug(f"{type(self).__name__} ordered a sell of {quantity} {symbol}")

        typ = symbol_type(symbol)
        if typ == "STOCK":
            return self.order_stock_limit(
                "sell", symbol, quantity, limit_price, in_force, extended
            )
        elif typ == "CRYPTO":
            return self.order_crypto_limit(
                "sell", symbol[1:], quantity, limit_price, in_force, extended
            )
        elif typ == "OPTION":
            sym, exp_date, option_type, strike = self.occ_to_data(symbol)
            return self.order_option_limit(
                "sell",
                sym,
                quantity,
                limit_price,
                option_type,
                exp_date,
                strike,
                in_force,
            )
        else:
            debugger.error(f"Invalid asset type for {symbol}")

    # def buy_option(self, symbol: str, quantity: int = 0, in_force: str = "gtc"):
    #     """
    #     Buys the specified option.

    #     :symbol:    Symbol of the asset to buy, in OCC format.
    #     :quantity:  Quantity of asset to buy
    #     :in_force:  Duration the order is in force

    #     :returns: The result of order_option_limit(). Returns None if there is an issue with the parameters.
    #     """
    #     if quantity <= 0.0:
    #         debugger.error(
    #             f"Quantity cannot be less than or equal to 0: was given {quantity}"
    #         )
    #         return None
    #     if self.trader is None:
    #         buy_power = self.fetch_account()["buying_power"]
    #         price = self.streamer.fetch_option_market_data(symbol)["price"]
    #     else:
    #         buy_power = self.trader.account["buying_power"]
    #         price = self.trader.streamer.fetch_option_market_data(symbol)["price"]

    #     limit_price = mark_up(price)
    #     total_price = limit_price * quantity

    #     if total_price >= buy_power:
    #         debugger.warning(
    #             "Not enough buying power.\n" +
    #             f"Total price ({price} * {quantity} * 1.05 = {limit_price*quantity}) exceeds buying power {buy_power}.\n" +
    #             "Reduce purchase quantity or increase buying power."
    #         )

    #     sym, date, option_type, strike = self.occ_to_data(symbol)
    #     return self.order_option_limit(
    #         "buy",
    #         sym,
    #         quantity,
    #         limit_price,
    #         option_type,
    #         date,
    #         strike,
    #         in_force=in_force,
    #     )

    # def sell_option(self, symbol: str, quantity: int = 0, in_force: str = "gtc"):
    #     """
    #     Sells the specified option.

    #     :symbol:    Symbol of the asset to buy, in OCC format.
    #     :quantity:  Quantity of asset to buy
    #     :in_force:  Duration the order is in force

    #     :returns: The result of order_option_limit(). Returns None if there is an issue with the parameters.
    #     """
    #     if quantity <= 0.0:
    #         debugger.error(
    #             f"Quantity cannot be less than or equal to 0: was given {quantity}"
    #         )
    #         return None
    #     if self.trader is None:
    #         price = self.streamer.fetch_option_market_data(symbol)["price"]
    #     else:
    #         price = self.trader.streamer.fetch_option_market_data(symbol)["price"]

    #     limit_price = mark_down(price)

    #     debugger.debug(f"{type(self).__name__} ordered a sell of {quantity} {symbol}")
    #     sym, date, option_type, strike = self.occ_to_data(symbol)
    #     return self.order_option_limit(
    #         "sell",
    #         sym,
    #         quantity,
    #         limit_price,
    #         option_type,
    #         date,
    #         strike,
    #         in_force=in_force,
    #     )

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
        original_symbol = symbol
        debugger.debug(f"Converting {symbol} to data")
        try:
            sym = ""
            symbol = symbol.replace(" ", "")
            i = 0
            while symbol[i].isalpha():
                i += 1
            sym = symbol[0:i]
            symbol = symbol[i:]
            debugger.debug(f"{sym}, {symbol}")

            date = dt.datetime.strptime(symbol[0:6], "%y%m%d")
            debugger.debug(f"{date}, {symbol}")
            option_type = "call" if symbol[6] == "C" else "put"
            debugger.debug(f"{option_type}, {symbol}")
            price = float(symbol[7:]) / 1000
            debugger.debug(f"{price}, {symbol}")
            return sym, date, option_type, price
        except Exception as e:
            debugger.error(f"Error parsing OCC symbol: {original_symbol}, {e}")
            # return None, None, None, None
            raise Exception(f"Error parsing OCC symbol: {original_symbol}, {e}")

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

    def setup(self, interval: Dict, trader_main=None) -> None:
        super().setup(interval, trader_main)
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
            self.stats.timestamp = df_dict[got[0]].index[0]

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
        # For missing data, return a OHLC with all zeroes.
        self.block_lock.acquire()
        for n in self.needed:
            data = pd.DataFrame(
                {"open": 0, "high": 0, "low": 0, "close": 0, "volume": 0},
                index=[self.timestamp],
            )

            data.columns = pd.MultiIndex.from_product([[n], data.columns])
            self.block_queue[n] = data
        self.block_lock.release()
        self.trader_main(self.block_queue)
        self.block_queue = {}
