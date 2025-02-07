import math
from datetime import timezone
from typing import List, Literal

import numpy as np
import pandas as pd
from finta import TA

# from harvest.broker import Broker
from harvest.client import Client
from harvest.definitions import Account, RuntimeData
from harvest.enum import Interval
from harvest.plugin._base import Plugin
from harvest.util.date import convert_input_to_datetime, datetime_utc_to_local, pandas_timestamp_to_local
from harvest.util.helper import (
    debugger,
    interval_string_to_enum,
    mark_up,
    symbol_type,
)

"""
Algo class is the main interface between users and the program.
"""


class Algorithm:
    """The Algorithm class is an abstract class defining the interface for users to
    track assets, monitor their accounts, and place orders.
    It also provides function for technical analysis.
    """

    watch_list: List[str]  # List of assets this algorithm tracks
    interval: Interval  # Interval to run the algorithm

    client: Client  # Broker object
    stats: RuntimeData  # Stats object
    account: Account  # Account object

    def __init__(self, watch_list: List[str], interval: Interval, aggregations: List[Interval]):
        self.interval = interval
        self.aggregations = aggregations
        self.watch_list = watch_list

    def initialize_algorithm(self, client: Client, stats: RuntimeData, account: Account):
        self.client = client
        self.stats = stats
        self.account = account

    def setup(self):
        """
        Method called right before algorithm begins.
        """
        pass

    def main(self):
        """
        Main method to run the algorithm.
        """
        pass

    def add_plugin(self, plugin: Plugin):
        """
        Adds a plugin to the algorithm.
        """
        value = getattr(self, plugin.name, None)
        if value is None:
            setattr(self, plugin.name, plugin)
        else:
            debugger.error(f"Plugin name is already in use! {plugin.name} points to {value}.")

    ############ Functions interfacing with broker through the trader #################

    def buy(
        self,
        symbol: str,
        quantity: float,
        in_force: Literal["gtc", "gtd"] = "gtc",
        extended: bool = False,
    ):
        """
        Buys the specified asset.

        When called, a limit buy order is placed with a limit
        price 5% higher than the current price. This is a general function that can
        be used to buy stocks, crypto, and options.

        :param str symbol: Symbol of the asset to buy.
            Crypto assets must be prepended with a '@' symbol.
            When buying options, the symbol must be formatted in OCC format.
        :param float quantity: Quantity of asset to buy. Note that this number can be a decimal only if the broker supports fractional trades.
        :param Literal["gtc", "gtd"]? in_force: Duration the order is in force.
            Choose from 'gtc' (Good 'til canceled) or 'gtd' (Good 'til date). defaults to 'gtc'
        :param bool? extended: Whether to trade in extended hours or not. Defaults to False

        :returns: The following Python dictionary
            - order_id: str, ID of order
            - symbol: str, symbol of asset

        :raises Exception: There is an error in the order process.
        """
        debugger.debug(f"Submitted buy order for {symbol} with quantity {quantity}")
        return self.client.buy(symbol, quantity, in_force, extended)

    def sell(
        self,
        symbol: str,
        quantity: float,
        in_force: Literal["gtc", "gtd"] = "gtc",
        extended: bool = False,
    ):
        """Sells the specified asset.

        When called, a limit sell order is placed with a limit
        price 5% lower than the current price. This is a general function that can
        be used to sell stocks, crypto, and options.

        :param str symbol: Symbol of the asset to sell.
            Crypto assets must be prepended with a '@' symbol.
            When selling options, the symbol must be formatted in OCC format.
        :param float quantity: Quantity of asset to sell. If not specified,
            it will sell all currently owned quantity.
        :param Literal["gtc", "gtd"]? in_force: Duration the order is in force.
            Choose from 'gtc' (Good 'til canceled) or 'gtd' (Good 'til date). Defaults to 'gtc'
        :param bool? extended: Whether to trade in extended hours or not. Defaults to False

        :returns: A dictionary with the following keys:
            - order_id: str, ID of order
            - symbol: str, symbol of asset

        :raises Exception: There is an error in the order process.
        """

        debugger.debug(f"Submitted sell order for {symbol} with quantity {quantity}")
        return self.func.sell(symbol, quantity, in_force, extended)

    def sell_all_options(self, symbol: str = None, in_force: str = "gtc"):
        """Sells all options based on the specified stock.

        For example, if you call this function with `symbol` set to "TWTR", it will sell
        all options you own that is related to TWTR.

        :param str? symbol: symbol of stock. defaults to first symbol in watchlist
        :returns: A list of dictionaries with the following keys:
            - order_id: str, ID of order
            - symbol: str, symbol of asset
        """
        if symbol is None:
            symbol = self.watchlist[0]

        symbols = filter(lambda x: x.base_symbol == symbol, self.positions.option)

        ret = []
        for s in symbols:
            debugger.debug(f"Algo SELL OPTION: {s}")
            quantity = self.get_asset_quantity(s.symbol)
            ret.append(self.func.sell(s.symbol, quantity, in_force, True))

        return ret

    def filter_option_chain(
        self,
        symbol=None,
        type=None,
        lower_exp=None,
        upper_exp=None,
        lower_strike=None,
        upper_strike=None,
    ):
        """Returns a DataFrame of options that satisfies the criteria specified.

        The lower_exp and upper_exp input can either be a string in the format "YYYY-MM-DD" or a datetime object.

        :param str symbol: Symbol of stock. defaults to first symbol in watchlist.
        :param str? type: 'call' or 'put'
        :param str? lower_exp: Minimum expiration date of the option, inclusive.
        :param str? upper_exp: Maximum expiration date of the option, inclusive.
        :param float lower_strike: The minimum strike price of the option, inclusive.
        :param float upper_strike: The maximum strike price of the option, inclusive.

        :returns: A DataFrame, with an index of strings representing the OCC symbol of options, and the following columns
        |symbol | type | strike
        |-------|------|-------
        |(str) ticker of stock | 'call' or 'put' | (float) strike price

        """
        if symbol is None:
            symbol = self.watchlist[0]
        lower_exp = convert_input_to_datetime(lower_exp, timezone.utc)
        upper_exp = convert_input_to_datetime(upper_exp, timezone.utc)
        # Remove timezone from datetime objects

        exp_dates = self.get_option_chain_info(symbol)["exp_dates"]
        if lower_exp is not None:
            lower_exp = lower_exp.replace(tzinfo=None)
            exp_dates = list(filter(lambda x: x >= lower_exp, exp_dates))
        if upper_exp is not None:
            upper_exp = upper_exp.replace(tzinfo=None)
            exp_dates = list(filter(lambda x: x <= upper_exp, exp_dates))
        exp_dates = sorted(exp_dates)

        exp_date = exp_dates[0]

        chain = self.get_option_chain(symbol, exp_date)
        if lower_strike is not None:
            chain = chain[chain["strike"] >= lower_strike]
        if upper_strike is not None:
            chain = chain[chain["strike"] <= upper_strike]

        if type is not None:
            chain = chain[chain["type"] == type]

        chain = chain.sort_values(by=["strike", "exp_date"])

        return chain

    # ------------------ Functions to trade options ----------------------

    def get_option_chain_info(self, symbol: str = None):
        """Returns data of a stock's option chain.

        Given a stock's symbol, this function returns a dictionary with two data.
        The first is a list indicating the available expiration dates of the option.
        The second is the multiplier, which indicates how many contracts are in a single option.
        For example, if you buy an option priced at $1.20 and the multiplier is 100,
        you will need to pay $120 to buy one option.

        This function is often used in conjunction with the get_option_chain function.

        :param str? symbol: symbol of stock. defaults to first symbol in watchlist
        :returns: A dict with the following keys:
            - exp_dates: List of expiration dates as strings in the format "YYYY-MM-DD"
            - multiplier: float. Multiplier of the option, usually 100
        """
        if symbol is None:
            symbol = self.watchlist[0]
        return self.func.fetch_chain_info(symbol)

    def get_option_chain(self, symbol: str, date):
        """Returns the option chain for the specified symbol and expiration date.

        The date parameter can either be a string in the format "YYYY-MM-DD" or a datetime object.
        This function is often used in conjunction with the get_option_chain_info function in order to
        retrieve the available expiration dates.

        :param str symbol: symbol of stock
        :param date: date of option expiration
        :returns: A dataframe with the follwing columns:

            - exp_date(datetime.datetime): The expiration date, as offset-naive DateTime object
            *with timezone adjusted to the timezone of the exchange being used*
            - strike(float): Strike price
            - type(str): 'call' or 'put'

        The index is the OCC symbol of the option.
        """
        if symbol is None:
            symbol = self.watchlist[0]
        date = convert_input_to_datetime(date, self.stats.timezone)

        return self.func.fetch_chain_data(symbol, date)

    def get_option_market_data(self, symbol: str):
        """Retrieves data of specified option.

        Note that the price returned by this function returns the price per contract,
        not the total price of the option.

        :param str? symbol: OCC symbol of option
        :returns: A dictionary:
            - price: price of option
            - ask: ask price
            - bid: bid price
        """
        if symbol is None:
            symbol = self.watchlist[0]
        return self.func.fetch_option_market_data(symbol)

    # ------------------ Technical Indicators -------------------

    def _default_param(self, symbol, interval, ref, prices):
        if symbol is None:
            symbol = self.watchlist[0]

        if interval is None:
            interval = self.stats.watchlist_cfg[symbol]["interval"]
        else:
            interval = interval_string_to_enum(interval)

        if prices is None:
            prices = self.func.load(symbol, interval)[symbol][ref]

        return symbol, interval, ref, prices

    def rsi(
        self,
        symbol: str = None,
        period: int = 14,
        interval: Interval = None,
        ref: str = "close",
        prices=None,
    ) -> np.array:
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
            debugger.warning("Not enough data to calculate RSI, returning None")
            return None

        ohlc = pd.DataFrame(
            {
                "close": np.array(prices),
                "open": np.zeros(len(prices)),
                "high": np.zeros(len(prices)),
                "low": np.zeros(len(prices)),
            }
        )
        return TA.RSI(ohlc, period=period).to_numpy()

    def sma(
        self,
        symbol: str = None,
        period: int = 14,
        interval: Interval = None,
        ref: str = "close",
        prices=None,
    ) -> np.array:
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
            debugger.warning("Not enough data to calculate SMA, returning None")
            return None

        ohlc = pd.DataFrame(
            {
                "close": np.array(prices),
                "open": np.zeros(len(prices)),
                "high": np.zeros(len(prices)),
                "low": np.zeros(len(prices)),
            }
        )
        return TA.SMA(ohlc, period=period).to_numpy()

    def ema(
        self,
        symbol: str = None,
        period: int = 14,
        interval: Interval = None,
        ref: str = "close",
        prices=None,
    ) -> np.array:
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
            debugger.warning("Not enough data to calculate EMA, returning None")
            return None

        ohlc = pd.DataFrame(
            {
                "close": np.array(prices),
                "open": np.zeros(len(prices)),
                "high": np.zeros(len(prices)),
                "low": np.zeros(len(prices)),
            }
        )
        return TA.EMA(ohlc, period=period).to_numpy()

    def bbands(
        self,
        symbol: str = None,
        period: int = 14,
        interval: Interval = None,
        ref: str = "close",
        dev: float = 1.0,
        prices=None,
    ) -> Tuple[np.array, np.array, np.array]:
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
            debugger.warning("Not enough data to calculate BBands, returning None")
            return None, None, None

        ohlc = pd.DataFrame(
            {
                "close": np.array(prices),
                "open": np.zeros(len(prices)),
                "high": np.zeros(len(prices)),
                "low": np.zeros(len(prices)),
            }
        )

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
            raise Exception("There must be at least 2 datapoints to calculate crossover")
        return prices_0[-2] < prices_1[-2] and prices_0[-1] > prices_1[-1]

    ############### Getters for Trader properties #################

    def get_asset_quantity(self, symbol: str = None, include_pending_buy=True, include_pending_sell=False) -> float:
        """Returns the quantity owned of a specified asset.

        :param str? symbol:  Symbol of asset. defaults to first symbol in watchlist
        :param bool? include_pending_buy:  Include pending buy orders in quantity. defaults to True
        :param bool? include_pending_sell:  Include pending sell orders in quantity. defaults to False
        :returns: Quantity of asset as float. 0 if quantity is not owned.
        :raises:
        """
        if symbol is None:
            symbol = self.watchlist[0]

        return self.func.get_asset_quantity(symbol, include_pending_buy, include_pending_sell)

    def get_asset_avg_cost(self, symbol: str = None) -> float:
        """Returns the average cost of a specified asset.

        :param str? symbol:  Symbol of asset. defaults to first symbol in watchlist
        :returns: Average cost of asset. Returns None if asset is not being tracked.
        :raises Exception: If symbol is not currently owned.
        """
        if symbol is None:
            symbol = self.watchlist[0]
        symbol = symbol.replace(" ", "")
        asset = self.positions.get(symbol)
        if asset is None:
            raise Exception(f"{symbol} is not currently owned")
        return asset.avg_price

    def get_asset_current_price(self, symbol: str = None) -> float:
        """Returns the current price of a specified asset.

        :param str? symbol: Symbol of asset. defaults to first symbol in watchlist
        :returns:           Price of asset.
        :raises Exception:  If symbol is not in the watchlist.
        """
        if symbol is None:
            symbol = self.watchlist[0]
        if symbol_type(symbol) != "OPTION":
            return self.func.load(symbol, self.interval)[symbol]["close"][-1]

        for p in self.positions.option:
            if p.symbol == symbol:
                return p.current_price * p.multiplier
        return self.func.fetch_option_market_data(symbol)["price"] * 100

    def get_asset_price_list(self, symbol: str = None, interval: str = None, ref: str = "close"):
        """Returns a list of recent prices for an asset.

        This function is not compatible with options.

        :param str? symbol:     Symbol of stock or crypto asset. defaults to first symbol in watchlist
        :param str? interval:   Interval of data. defaults to the interval of the algorithm
        :param str? ref:        'close', 'open', 'high', or 'low'. defaults to 'close'
        :returns: List of prices
        """
        if symbol is None:
            symbol = self.watchlist[0]
        if interval is None:
            interval = self.interval
        else:
            interval = interval_string_to_enum(interval)
        if symbol_type(symbol) != "OPTION":
            return list(self.func.load(symbol, interval)[symbol][ref])
        debugger.warning("Price list not available for options")
        return None

    def get_asset_current_candle(self, symbol: str, interval=None) -> pd.DataFrame():
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
        if symbol is None:
            symbol = self.watchlist[0]
        if interval is None:
            interval = self.interval
        if len(symbol) <= 6:
            df = self.func.load(symbol, interval).iloc[[-1]][symbol]
            return pandas_timestamp_to_local(df, self.stats.timezone)
        debugger.warning("Candles not available for options")
        return None

    def get_asset_candle_list(self, symbol: str = None, interval=None) -> pd.DataFrame():
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
        if symbol is None:
            symbol = self.watchlist[0]
        if interval is None:
            interval = self.interval
        df = self.func.load(symbol, interval)[symbol]
        return pandas_timestamp_to_local(df, self.stats.timezone)

    def get_asset_profit_percent(self, symbol=None) -> float:
        """Returns the return of a specified asset.

        :param str? symbol:  Symbol of stock, crypto, or option. Options should be in OCC format.
                        defaults to first symbol in watchlist
        :returns: Return of asset, expressed as a decimal.
        """
        if symbol is None:
            symbol = self.watchlist[0]
        asset = self.positions.get(symbol)
        if asset is None:
            debugger.warning(
                f"{symbol} is not currently owned. You either don't have it or it's still in the order queue."
            )
            return None
        return asset.profit_percent

    def get_asset_max_quantity(self, symbol=None):
        """Calculates the maximum quantity of an asset that can be bought given the current buying power.

        :param str? symbol:  Symbol of stock, crypto, or option. Options should be in OCC format.
            defaults to first symbol in watchlist
        :returns: Quantity that can be bought.
        """
        if symbol is None:
            symbol = self.watchlist[0]

        power = self.get_account_buying_power()
        price = self.get_asset_current_price(symbol)

        if symbol_type(symbol) == "CRYPTO":
            price = mark_up(price)
            return math.floor(power / price * 10**5) / 10**5
        else:
            price = mark_up(price)
            return math.floor(power / price)

    def get_account_buying_power(self) -> float:
        """Returns the current buying power of the user.

        :returns: The current buying power as a float.
        """
        return self.account.buying_power

    def get_account_equity(self) -> float:
        """Returns the current equity.

        :returns: The current equity as a float.
        """
        return self.account.equity

    def get_account_stock_positions(self) -> List:
        """Returns the current stock positions.

        :returns: A list of Position objects for all currently owned stocks.
        """
        return self.positions.stock

    def get_account_crypto_positions(self) -> List:
        """Returns the current crypto positions.

        :returns: A list of Position objects for all currently owned crypto.
        """
        return self.positions.crypto

    def get_account_option_positions(self) -> List:
        """Returns the current option positions.

        :returns: A list of OptionPosition objects for all currently owned options.
        """
        return self.positions.option

    def get_watchlist(self) -> List:
        """Returns the current watchlist."""
        return self.watchlist

    def get_stock_watchlist(self) -> List:
        """Returns the current watchlist."""
        return [s for s in self.watchlist if symbol_type(s) == "STOCK"]

    def get_crypto_watchlist(self) -> List:
        """Returns the current watchlist."""
        return [s for s in self.watchlist if symbol_type(s) == "CRYPTO"]

    def get_time(self):
        """Returns the current hour and minute.

        This returns the current time, which is different from the timestamp
        of stock prices. For example, if you are running an algorithm every 5 minutes,
        at 11:30am you will get price data with a timestamp of 11:25am. This function will return
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

        The returned datetime object is offset-naive, adjusted to the local timezone.

        :returns: The current date and time as a datetime object
        """
        return datetime_utc_to_local(self.stats.timestamp, self.stats.timezone)

    # def is_day_trade(self, symbol=None, action="buy") -> bool:
    #     """
    #     Checks if performing a buy or sell will be considered day trading.
    #     """

    #     # Get transaction history
    #     history = self.func.load_daytrade()
    #     # False if less than 3 transactions
    #     if len(history) < 3:
    #         return False

    # Used for testing
    def add_symbol(self, symbol: str):
        """Adds a symbol to the watchlist.

        :param str symbol: Symbol of stock or crypto asset.
        """
        self.watchlist.append(symbol)
