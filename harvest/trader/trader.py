# Builtins
import re
import threading
import sys
from sys import exit
from signal import signal, SIGINT
import time
import logging

# External libraries

# Submodule imports
from harvest.utils import *
from harvest.storage import BaseStorage
from harvest.api.yahoo import YahooStreamer
from harvest.api.dummy import DummyStreamer
from harvest.api.paper import PaperBroker
from harvest.storage import BaseStorage
from harvest.storage import BaseLogger
from harvest.server import Server


class Trader:
    """
    :broker: Both the broker and streamer store a Broker object.
        Broker places orders and retrieves latest account info like equity.
    :streamer: Streamer retrieves the latest stock price and calls handler().
    """

    interval_list = [Interval.SEC_15, Interval.MIN_1, Interval.MIN_5, Interval.MIN_15, Interval.MIN_30, Interval.HR_1, Interval.DAY_1]

    def __init__(self, streamer=None, broker=None, storage=None, debug=False):
        """Initializes the Trader. 
        """

        signal(SIGINT, self.exit)

        # Harvest only supports Python 3.8 or newer.
        if sys.version_info[0] < 3 or sys.version_info[1] < 8:
            raise Exception("Harvest requires Python 3.8 or above.")

        # If streamer is not specified, use YahooStreamer
        self.streamer = YahooStreamer() if streamer is None else streamer
        # If broker is not specified and streamer is YahooStreamer, use PaperBroker
        if broker is None:
            if isinstance(self.streamer, (YahooStreamer, DummyStreamer)):
                self.broker = PaperBroker()
            else:
                self.broker = self.streamer
        else:
            self.broker = broker

        # # Initialize timestamp
        self.timestamp = self.streamer.timestamp
        # self.timestamp = self.timestamp_prev

        self.watchlist_global = []  # List of securities specified in this class, 
                                    # fetched from brokers, and retrieved from Algo class.

        self.account = {}           # Local cache of account data.

        self.stock_positions = []  # Local cache of current stock positions.
        self.option_positions = []  # Local cache of current options positions.
        self.crypto_positions = []  # Local cache of current crypto positions.

        self.order_queue = []  # Queue of unfilled orders.

        # Initialize the storage
        self.storage = BaseStorage() if storage is None else storage

        self.logger = BaseLogger()

        self.algo = []  # List of algorithms to run.

        # Initialize the web interface server
        self.server = Server(self)

        # Set up logger
        self.debugger = logging.getLogger("harvest")
        self.debugger.setLevel("DEBUG")
        if debug:
            f_handler = logging.FileHandler("trader.log")
            f_handler.setLevel(logging.DEBUG)
            f_format = logging.Formatter(
                "%(asctime)s : %(name)s : %(levelname)s : %(message)s"
            )
            f_handler.setFormatter(f_format)
            self.debugger.addHandler(f_handler)

        c_handler = logging.StreamHandler()
        if debug:
            c_handler.setLevel(logging.DEBUG)
        else:
            c_handler.setLevel(logging.INFO)
        c_format = logging.Formatter(
            "%(asctime)s : %(name)s : %(levelname)s : %(message)s"
        )
        c_handler.setFormatter(c_format)
        self.debugger.addHandler(c_handler)

    def start(self, interval='5MIN', aggregations=[], sync=True, server=False):
        """Entry point to start the system. 
        
        :param str? interval: The interval to run the algorithm. defaults to '5MIN'
        :param list[str]? aggregations: A list of intervals. The Trader will aggregate data to the intervals specified in this list.
            For example, if this is set to ['5MIN', '30MIN'], and interval is '1MIN', the algorithm will have access to 
            5MIN, 30MIN aggregated data in addition to 1MIN data. defaults to None
        :param bool? sync: If true, the system will sync with the broker and fetch current positions and pending orders. defaults to true. 
        :kill_switch: If true, kills the infinite loop in streamer. Primarily used for testing. defaults to False.

        """
        self.debugger.debug(f"Setting up Harvest...")

        # If sync is on, call the broker to load pending orders and all positions currently held.
        if sync:
            self._setup_stats()
            for s in self.stock_positions:
                self.watchlist_global.append(s['symbol'])
            for s in self.option_positions:
                self.watchlist_global.append(s['symbol'])
            for s in self.crypto_positions:
                self.watchlist_global.append(s['symbol'])
            for s in self.order_queue:
                self.watchlist_global.append(s['symbol'])     
        
        # Remove duplicates in watchlist
        self.watchlist_global = list(set(self.watchlist_global))
        self.debugger.debug(f"Watchlist: {self.watchlist_global}")

        # Initialize a dict of symbols and the intervals they need to run at
        self._setup_params(interval, aggregations)

        if len(self.interval) == 0:
            raise Exception(f"No securities were added to watchlist")

        # Initialize the account
        self._setup_account()

        # Initialize streamers and brokers
        self.broker.setup(self.interval, self, self.main)
        self.streamer.setup(self.interval, self, self.main)

        # Initialize the storage
        self._storage_init()

        for a in self.algo:
            a.setup()
            a.trader = self

        self.debugger.debug("Setup complete")

        if server:
            self.server.start()

        self.streamer.start()
    
    def _setup_stats(self):
        """Initializes local cache of stocks, options, and crypto positions."""

        # Get any pending orders
        ret = self.broker.fetch_order_queue()
        self.order_queue = ret
        self.debugger.debug(f"Fetched orders:\n{self.order_queue}")

        # Get positions
        pos = self.broker.fetch_stock_positions()
        self.stock_positions = pos
        pos = self.broker.fetch_option_positions()
        self.option_positions = pos
        pos = self.broker.fetch_crypto_positions()
        self.crypto_positions = pos
        self.debugger.debug(
            f"Fetched positions:\n{self.stock_positions}\n{self.option_positions}\n{self.crypto_positions}"
        )

        # Update option stats
        self.broker.update_option_positions(self.option_positions)
        self.debugger.debug(f"Updated option positions:\n{self.option_positions}")
    
    def _setup_params(self, interval, aggregations):
        interval = interval_string_to_enum(interval)
        aggregations = [ interval_string_to_enum(a) for a in aggregations ]
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

    def _storage_init(self):
        """Initializes the storage.
        """
        
        for sym in self.interval:
            for inter in [self.interval[sym]["interval"]] + self.interval[sym]["aggregations"]:
                df = self.streamer.fetch_price_history(sym, inter)
                self.storage.store(sym, inter, df)
    
    def main(self, df_dict):
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
        self._update_stats(df_dict, new=update, option_update=True)

        new_algo = []
        for a in self.algo:
            if not is_freq(self.timestamp, a.interval):
                new_algo.append(a)
                continue
            try:
                a.main()
                new_algo.append(a)
            except Exception as e:
                self.debugging.warning(f"Algorithm {a} failed, removing from algorithm list.\nException: {e}")
        self.algo = new_algo

        self.broker.exit()
        self.streamer.exit()

    def _update_order_queue(self):
        """Check to see if outstanding orders have been accepted or rejected
        and update the order queue accordingly.
        """
        self.debugger.debug(f"Updating order queue: {self.order_queue}")
        for i, order in enumerate(self.order_queue):
            if "type" not in order:
                raise Exception(f"key error in {order}\nof {self.order_queue}")
            if order["type"] == "STOCK":
                stat = self.broker.fetch_stock_order_status(order["id"])
            elif order["type"] == "OPTION":
                stat = self.broker.fetch_option_order_status(order["id"])
            elif order["type"] == "CRYPTO":
                stat = self.broker.fetch_crypto_order_status(order["id"])
            self.debugger.debug(f"Updating status of order {order['id']}")
            self.order_queue[i] = stat

        self.debugger.debug(f"Updated order queue: {self.order_queue}")
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

        self.debugger.debug(f"Stock positions: {self.stock_positions}")
        self.debugger.debug(f"Option positions: {self.option_positions}")
        self.debugger.debug(f"Crypto positions: {self.crypto_positions}")

        if new:
            return 

        net_value = 0
        for p in self.stock_positions + self.crypto_positions:
            key = p['symbol']
            price = df_dict[key][key]['close'][0]
            p['current_price'] = price
            value = price * p['quantity']
            p['market_value'] = value
            net_value += value

        equity = net_value + self.account['cash']
        self.account['equity'] = equity

    def _update_positions(self):
        pos = self.broker.fetch_stock_positions()
        self.stock_positions = [p for p in pos if p['symbol'] in self.interval]
        pos = self.broker.fetch_option_positions()
        self.option_positions = [p for p in pos if p['symbol'] in self.interval]
        pos = self.broker.fetch_crypto_positions()
        self.crypto_positions = [p for p in pos if p['symbol'] in self.interval]
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
            self.debugger.debug("BUY failed")
            return None
        self.order_queue.append(ret)
        self.debugger.debug(f"BUY: {self.timestamp}, {symbol}, {quantity}")
        self.debugger.debug(f"BUY order queue: {self.order_queue}")
        asset_type = "crypto" if is_crypto(symbol) else "stock"
        self.logger.add_transaction(self.timestamp, "buy", asset_type, symbol, quantity)
        return ret

    def sell(self, symbol: str, quantity: int, in_force: str, extended: bool):
        ret = self.broker.sell(symbol, quantity, in_force, extended)
        if ret is None:
            self.debugger.debug("SELL failed")
            return None
        self.order_queue.append(ret)
        self.debugger.debug(f"SELL: {self.timestamp}, {symbol}, {quantity}")
        self.debugger.debug(f"SELL order queue: {self.order_queue}")
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
        self.debugger.debug(f"BUY: {self.timestamp}, {symbol}, {quantity}")
        self.debugger.debug(f"BUY order queue: {self.order_queue}")
        self.logger.add_transaction(self.timestamp, "buy", "option", symbol, quantity)
        return ret

    def sell_option(self, symbol: str, quantity: int, in_force: str):
        ret = self.broker.sell_option(symbol, quantity, in_force)
        if ret is None:
            raise Exception("SELL failed")
        self.order_queue.append(ret)
        self.debugger.debug(f"SELL: {self.timestamp}, {symbol}, {quantity}")
        self.debugger.debug(f"SELL order queue: {self.order_queue}")
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
        self.debugger.debug("\nStopping Harvest...")
        exit(0)
