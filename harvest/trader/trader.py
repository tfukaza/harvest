# Builtins
from logging import debug
import re
import threading
import traceback
import sys
from sys import exit
from signal import signal, SIGINT
import time
import datetime as dt

# External libraries
import tzlocal

# Submodule imports
from harvest.utils import *
from harvest.storage import BaseStorage
from harvest.api.yahoo import YahooStreamer
from harvest.api.dummy import DummyStreamer
from harvest.api.paper import PaperBroker
from harvest.storage import BaseStorage
from harvest.storage import BaseLogger
from harvest.server import Server


class LiveTrader:
    """
    :broker: Both the broker and streamer store a Broker object.
        Broker places orders and retrieves latest account info like equity.
    :streamer: Streamer retrieves the latest stock price and calls handler().
    """

    interval_list = [
        Interval.SEC_15,
        Interval.MIN_1,
        Interval.MIN_5,
        Interval.MIN_15,
        Interval.MIN_30,
        Interval.HR_1,
        Interval.DAY_1,
    ]

    def __init__(self, streamer=None, broker=None, storage=None, debug=False):
        """Initializes the Trader."""

        self._init_checks()

        self._set_streamer_broker(streamer, broker)
        self.storage = (
            BaseStorage() if storage is None else storage
        )  # Initialize the storage
        self._init_attributes()

        self._setup_debugger(debug)

    def _init_checks(self):
        # Harvest only supports Python 3.8 or newer.
        if sys.version_info[0] < 3 or sys.version_info[1] < 8:
            raise Exception("Harvest requires Python 3.8 or above.")

    def _set_streamer_broker(self, streamer, broker):
        """Sets the streamer and broker."""
        # If streamer is not specified, use YahooStreamer
        self.streamer = YahooStreamer() if streamer is None else streamer
        # Broker must be specified
        if broker is None:
            # TODO: Raise exception is specified class is streaming only
            if isinstance(self.streamer, YahooStreamer):
                raise Exception("Broker must be specified")
            else:
                self.broker = self.streamer
        else:
            self.broker = broker

    def _init_attributes(self):

        signal(SIGINT, self.exit)

        # Initialize timestamp
        self.timestamp = self.streamer.timestamp

        self.watchlist_global = []  # List of securities specified in this class
        self.algo = []  # List of algorithms to run.
        self.account = {}  # Local cache of account data.
        self.stock_positions = []  # Local cache of current stock positions.
        self.option_positions = []  # Local cache of current options positions.
        self.crypto_positions = []  # Local cache of current crypto positions.
        self.order_queue = []  # Queue of unfilled orders.

        self.logger = BaseLogger()
        self.server = Server(self)  # Initialize the web interface server

        self.timezone = tzlocal.get_localzone()
        debugger.debug(f"Timezone: {self.timezone}")

    def _setup_debugger(self, debug):
        # Set up logger
        if debug:
            debugger.setLevel("DEBUG")

        debugger.debug(
            f"Streamer: {type(self.streamer).__name__}\nBroker: {type(self.broker).__name__}\nStorage: {type(self.storage).__name__}"
        )

    def start(
        self,
        interval="5MIN",
        aggregations=[],
        sync=True,
        server=False,
        all_history=True,
    ):
        """Entry point to start the system.

        :param str? interval: The interval to run the algorithm. defaults to '5MIN'
        :param list[str]? aggregations: A list of intervals. The Trader will aggregate data to the intervals specified in this list.
            For example, if this is set to ['5MIN', '30MIN'], and interval is '1MIN', the algorithm will have access to
            5MIN, 30MIN aggregated data in addition to 1MIN data. defaults to None
        :param bool? sync: If true, the system will sync with the broker and fetch current positions and pending orders. defaults to true.
        :param bool? all_history: If true, gets all history for all the given assets and if false only get data in the past three days.
        """
        debugger.debug("Setting up Harvest...")

        # If sync is on, call the broker to load pending orders and all positions currently held.
        if sync:
            self._setup_stats()
            for s in self.stock_positions:
                self.watchlist_global.append(s["symbol"])
            for s in self.option_positions:
                self.watchlist_global.append(s["symbol"])
            for s in self.crypto_positions:
                self.watchlist_global.append(s["symbol"])
            for s in self.order_queue:
                self.watchlist_global.append(s["symbol"])

        # Remove duplicates in watchlist
        self.watchlist_global = list(set(self.watchlist_global))
        debugger.debug(f"Watchlist: {self.watchlist_global}")

        # Initialize a dict of symbols and the intervals they need to run at
        self._setup_params(interval, aggregations)

        if len(self.interval) == 0:
            raise Exception("No securities were added to watchlist")

        # Initialize the account
        self._setup_account()

        self.broker.setup(self.interval, self, self.main)
        if self.broker != self.streamer:
            # Only call the streamer setup if it is a different
            # instance than the broker otherwise some brokers can fail!
            self.streamer.setup(self.interval, self, self.main)

        # Initialize the storage
        self._storage_init(all_history)

        for a in self.algo:
            a.trader = self
            a.setup()

        debugger.debug("Setup complete")

        if server:
            self.server.start()

        self.streamer.start()

    def _setup_stats(self):
        """Initializes local cache of stocks, options, and crypto positions."""

        # Get any pending orders
        ret = self.broker.fetch_order_queue()
        self.order_queue = ret
        debugger.debug(f"Fetched orders:\n{self.order_queue}")

        # Get positions
        pos = self.broker.fetch_stock_positions()
        self.stock_positions = pos
        pos = self.broker.fetch_option_positions()
        self.option_positions = pos
        pos = self.broker.fetch_crypto_positions()
        self.crypto_positions = pos
        debugger.debug(
            f"Fetched positions:\n{self.stock_positions}\n{self.option_positions}\n{self.crypto_positions}"
        )

        # Update option stats
        self.broker.update_option_positions(self.option_positions)
        debugger.debug(f"Updated option positions:\n{self.option_positions}")

    def _setup_params(self, interval, aggregations):
        interval = interval_string_to_enum(interval)
        aggregations = [interval_string_to_enum(a) for a in aggregations]
        self.interval = {}

        # Initialize a dict with symbol keys and values indicating
        # what data intervals they need.
        for sym in self.watchlist_global:
            self.interval[sym] = {}
            self.interval[sym]["interval"] = interval
            self.interval[sym]["aggregations"] = aggregations

        # Update the dict based on parameters specified in Algo class
        for a in self.algo:
            a.config()

            # If the algorithm does not specify a parameter, use the one
            # specified in the Trader class
            if len(a.watchlist) == 0:
                a.watchlist = self.watchlist_global
            if a.interval is None:
                a.interval = interval
            else:
                a.interval = interval_string_to_enum(a.interval)
            if a.aggregations is None:
                a.aggregations = aggregations
            else:
                a.aggregations = [interval_string_to_enum(a) for a in a.aggregations]

            # For each symbol specified in the Algo...
            for sym in a.watchlist:
                # If the algorithm needs data for the symbol at a higher frequency than
                # it is currently available in the Trader class, update the interval
                if sym in self.interval:
                    cur_interval = self.interval[sym]["interval"]
                    if a.interval < cur_interval:
                        self.interval[sym]["aggregations"].append(cur_interval)
                        self.interval[sym]["interval"] = a.interval
                # If symbol is not in global watchlist, simply add it
                else:
                    self.interval[sym] = {}
                    self.interval[sym]["interval"] = a.interval
                    self.interval[sym]["aggregations"] = a.aggregations

                # If the algo specifies an aggregation that is currently not set, add it to the
                # global aggregation list
                for agg in a.aggregations:
                    if agg not in self.interval[sym]["aggregations"]:
                        self.interval[sym]["aggregations"].append(agg)

        # Remove any duplicates in the dict
        for sym in self.interval:
            new_agg = list((set(self.interval[sym]["aggregations"])))
            self.interval[sym]["aggregations"] = [] if new_agg is None else new_agg

    def _setup_account(self):
        """Initializes local cache of account info.
        For testing, it should manually be specified
        """
        ret = self.broker.fetch_account()
        self.account = ret

    def _storage_init(self, all_history: bool):
        """
        Initializes the storage.
        :all_history: bool :
        """

        for sym in self.interval:
            for inter in [self.interval[sym]["interval"]] + self.interval[sym][
                "aggregations"
            ]:
                start = None if all_history else now() - dt.timedelta(days=3)
                df = self.streamer.fetch_price_history(sym, inter, start)
                self.storage.store(sym, inter, df)

    def main(self, df_dict):
        self.timestamp = self.streamer.timestamp
        # Periodically refresh access tokens
        if self.timestamp.hour % 12 == 0 and self.timestamp.minute == 0:
            self.streamer.refresh_cred()

        # Save the data locally
        for sym in df_dict:
            self.storage.store(sym, self.interval[sym]["interval"], df_dict[sym])

        # Aggregate the data to other intervals
        for sym in df_dict:
            for agg in self.interval[sym]["aggregations"]:
                self.storage.aggregate(sym, self.interval[sym]["interval"], agg)

        # If an order was processed, fetch the latest position info.
        # Otherwise, calculate current positions locally
        update = self._update_order_queue()
        self._update_stats(
            df_dict, new=update, option_update=len(self.option_positions) > 0
        )

        new_algo = []
        for a in self.algo:
            if not is_freq(self.timestamp, a.interval):
                new_algo.append(a)
                continue
            try:
                debugger.info(f"Running algo: {a}")
                a.main()
                new_algo.append(a)
            except Exception as e:
                debugger.warning(f"Algorithm {a} failed, removing from algorithm list.\n")
                debugger.warning(f"Exception: {e}\n")
                debugger.warning(f"Traceback: {traceback.format_exc()}\n")

        if len(new_algo) <= 0:
            debugger.critical("No algorithms to run")
            exit()

        self.algo = new_algo

        self.broker.exit()
        self.streamer.exit()

    def _update_order_queue(self):
        """Check to see if outstanding orders have been accepted or rejected
        and update the order queue accordingly.
        """
        debugger.debug(f"Updating order queue: {self.order_queue}")
        for i, order in enumerate(self.order_queue):
            if "type" not in order:
                raise Exception(f"key error in {order}\nof {self.order_queue}")
            if order["type"] == "STOCK":
                stat = self.broker.fetch_stock_order_status(order["id"])
            elif order["type"] == "OPTION":
                stat = self.broker.fetch_option_order_status(order["id"])
            elif order["type"] == "CRYPTO":
                stat = self.broker.fetch_crypto_order_status(order["id"])
            debugger.debug(f"Updating status of order {order['id']}")
            self.order_queue[i] = stat

        debugger.debug(f"Updated order queue: {self.order_queue}")
        new_order = []
        order_filled = False
        for order in self.order_queue:
            if order["status"] == "filled":
                order_filled = True
            else:
                new_order.append(order)
        self.order_queue = new_order

        # if an order was processed, update the positions and account info
        return order_filled

    def _update_stats(self, df_dict, new=False, option_update=False):
        """Update local cache of stocks, options, and crypto positions"""
        # Update entries in local cache
        # API should also be called if load_watch is false, as there is a high chance
        # that data in local cache are not representative of the entire portfolio,
        # meaning total equity cannot be calculated locally
        if new:
            self._update_positions()
        if option_update:
            self.broker.update_option_positions(self.option_positions)

        debugger.debug(f"Stock positions: {self.stock_positions}")
        debugger.debug(f"Option positions: {self.option_positions}")
        debugger.debug(f"Crypto positions: {self.crypto_positions}")

        if new:
            return

        net_value = 0
        for p in self.stock_positions + self.crypto_positions:
            key = p["symbol"]
            if key in df_dict:
                price = df_dict[key][key]["close"]
            elif key not in self.watchlist_global:
                i = self.streamer.poll_interval
                end = now()
                start = end - interval_to_timedelta(i) * 2
                price = self.streamer.fetch_price_history(key, i, start, end)
                price = price[key]["close"][-1]
            else:
                continue
            p["current_price"] = price
            value = price * p["quantity"]
            p["market_value"] = value
            net_value += value

        equity = net_value + self.account["cash"]
        self.account["equity"] = equity

    def _update_positions(self):
        pos = self.broker.fetch_stock_positions()
        self.stock_positions = [p for p in pos if p["symbol"] in self.interval]
        pos = self.broker.fetch_option_positions()
        self.option_positions = [p for p in pos if p["symbol"] in self.interval]
        pos = self.broker.fetch_crypto_positions()
        self.crypto_positions = [p for p in pos if p["symbol"] in self.interval]
        ret = self.broker.fetch_account()
        self.account = ret

    # --------------------- Interface Functions -----------------------

    def fetch_chain_info(self, *args, **kwargs):
        return self.streamer.fetch_chain_info(*args, **kwargs)

    def fetch_chain_data(self, *args, **kwargs):
        return self.streamer.fetch_chain_data(*args, **kwargs)

    def fetch_option_market_data(self, *args, **kwargs):
        return self.streamer.fetch_option_market_data(*args, **kwargs)

    def buy(self, symbol: str, quantity: int, in_force: str, extended: bool):
        ret = self.broker.buy(symbol, quantity, in_force, extended)
        if ret is None:
            debugger.debug("BUY failed")
            return None
        self.order_queue.append(ret)
        debugger.debug(f"BUY: {self.timestamp}, {symbol}, {quantity}")
        debugger.debug(f"BUY order queue: {self.order_queue}")
        asset_type = "crypto" if is_crypto(symbol) else "stock"
        self.logger.add_transaction(self.timestamp, "buy", asset_type, symbol, quantity)
        return ret

    def sell(self, symbol: str, quantity: int, in_force: str, extended: bool):
        ret = self.broker.sell(symbol, quantity, in_force, extended)
        if ret is None:
            debugger.debug("SELL failed")
            return None
        self.order_queue.append(ret)
        debugger.debug(f"SELL: {self.timestamp}, {symbol}, {quantity}")
        debugger.debug(f"SELL order queue: {self.order_queue}")
        asset_type = "crypto" if is_crypto(symbol) else "stock"
        self.logger.add_transaction(
            self.timestamp, "sell", asset_type, symbol, quantity
        )
        return ret

    def buy_option(self, symbol: str, quantity: int, in_force: str):
        ret = self.broker.buy_option(symbol, quantity, in_force)
        if ret is None:
            raise Exception("BUY failed")
        self.order_queue.append(ret)
        debugger.debug(f"BUY: {self.timestamp}, {symbol}, {quantity}")
        debugger.debug(f"BUY order queue: {self.order_queue}")
        self.logger.add_transaction(self.timestamp, "buy", "option", symbol, quantity)
        return ret

    def sell_option(self, symbol: str, quantity: int, in_force: str):
        ret = self.broker.sell_option(symbol, quantity, in_force)
        if ret is None:
            raise Exception("SELL failed")
        self.order_queue.append(ret)
        debugger.debug(f"SELL: {self.timestamp}, {symbol}, {quantity}")
        debugger.debug(f"SELL order queue: {self.order_queue}")
        self.logger.add_transaction(self.timestamp, "sell", "option", symbol, quantity)
        return ret

    def set_algo(self, algo):
        """Specifies the algorithm to use.

        :param Algo algo: The algorithm to use. You can either pass in a single Algo class, or a
            list of Algo classes.
        """
        self.algo = algo if isinstance(algo, list) else [algo]

    def set_symbol(self, symbol):
        """Specifies the symbol(s) to watch.

        Cryptocurrencies should be prepended with an `@` to differentiate them from stocks.
        For example, '@ETH' will refer to Etherium, while 'ETH' will refer to Ethan Allen Interiors.
        If this method was previously called, the symbols specified earlier will be replaced with the
        new symbols.

        :symbol str symbol: Ticker Symbol(s) of stock or cryptocurrency to watch.
            It can either be a string, or a list of strings.
        """
        self.watchlist_global = symbol if isinstance(symbol, list) else [symbol]

    def exit(self, signum, frame):
        # TODO: Gracefully exit
        debugger.debug("\nStopping Harvest...")
        exit(0)


class PaperTrader(LiveTrader):
    """
    A class for trading in the paper trading environment.
    """

    def __init__(self, streamer=None, storage=None, debug=False):
        """Initializes the Trader."""

        self._init_checks()

        # If streamer is not specified, use YahooStreamer
        self.streamer = YahooStreamer() if streamer is None else streamer
        self.broker = PaperBroker()

        self.storage = (
            BaseStorage() if storage is None else storage
        )  # Initialize the storage
        self._init_attributes()

        self._setup_debugger(debug)
