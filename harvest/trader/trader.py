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
        # Initialize the storage
        self.storage = BaseStorage() if storage is None else storage

        self._init_attributes()
        self._setup_debugger(debug)

    def _init_checks(self):
        # Harvest only supports Python 3.9 or newer.
        if sys.version_info[0] < 3 or sys.version_info[1] < 9:
            raise Exception("Harvest requires Python 3.9 or above.")

    def _set_streamer_broker(self, streamer, broker):
        """Sets the streamer and broker."""
        # If streamer is not specified, use YahooStreamer
        self.streamer = YahooStreamer() if streamer is None else streamer
        # Broker must be specified
        if broker is None:
            # TODO: Raise exception if specified class is streaming only
            if isinstance(self.streamer, YahooStreamer):
                raise Exception("Broker must be specified")
            else:
                self.broker = self.streamer
        else:
            self.broker = broker

    def _init_attributes(self):

        signal(SIGINT, self.exit)

        self.watchlist_global = []  # List of securities specified in this class
        self.algo = []  # List of algorithms to run.
        self.account = {}  # Local cache of account data.
        self.stock_positions = []  # Local cache of current stock positions.
        self.option_positions = []  # Local cache of current options positions.
        self.crypto_positions = []  # Local cache of current crypto positions.
        self.order_queue = []  # Queue of unfilled orders.

        self.server = Server(self)  # Initialize the web interface server

        self.stats = Stats()  # Initialize the stats object
        self.stats.timestamp = None
        self.stats.timezone = tzlocal.get_localzone()
        self.stats.interval = None

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
                self.watchlist_global.append(s["base_symbol"])
            for s in self.crypto_positions:
                self.watchlist_global.append(s["symbol"])
            for s in self.order_queue:
                sym = s["base_symbol"] if s["type"] == "OPTION" else s["symbol"]
                self.watchlist_global.append(sym)

        # Remove duplicates in watchlist
        self.watchlist_global = list(set(self.watchlist_global))
        debugger.debug(f"Watchlist: {self.watchlist_global}")

        # Initialize a dict of symbols and the intervals they need to run at
        self._setup_params(interval, aggregations)

        if len(self.stats.interval) == 0:
            raise Exception("No securities were added to watchlist")

        # Initialize the account
        self._setup_account()
        self.storage.init_performace_data(
            self.account["equity"], self.streamer.timestamp
        )

        self.broker.setup(self.stats, self.main)
        if self.broker != self.streamer:
            # Only call the streamer setup if it is a different
            # instance than the broker otherwise some brokers can fail!
            self.streamer.setup(self.stats, self.main)

        # Initialize the storage
        self._storage_init(all_history)

        for a in self.algo:
            a.init(self.stats)
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
        """
        Sets up configuration parameters for the Trader, notably
        the 'interval' attribute.
        """
        interval = interval_string_to_enum(interval)
        aggregations = [interval_string_to_enum(a) for a in aggregations]
        watch_dict = {
            sym: {"interval": interval, "aggregations": aggregations}
            for sym in self.watchlist_global
        }
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
                if sym in watch_dict:
                    cur_interval = watch_dict[sym]["interval"]
                    if a.interval < cur_interval:
                        watch_dict[sym]["aggregations"].append(cur_interval)
                        watch_dict[sym]["interval"] = a.interval
                # If symbol is not in global watchlist, simply add it
                else:
                    watch_dict[sym] = {}
                    watch_dict[sym]["interval"] = a.interval
                    watch_dict[sym]["aggregations"] = a.aggregations

                # If the algo specifies an aggregation that is currently not set, add it to the
                # global aggregation list
                for agg in a.aggregations:
                    if agg not in watch_dict[sym]["aggregations"]:
                        watch_dict[sym]["aggregations"].append(agg)

        # Remove any duplicates in the dict
        for sym in watch_dict:
            new_agg = list((set(watch_dict[sym]["aggregations"])))
            watch_dict[sym]["aggregations"] = [] if new_agg is None else new_agg

        self.stats.interval = watch_dict

    def _setup_account(self):
        """Initializes local cache of account info.
        For testing, it should manually be specified
        """
        ret = self.broker.fetch_account()
        if ret is None:
            raise Exception("Failed to load account info from broker.")
        self.account = ret

    def _storage_init(self, all_history: bool):
        """
        Initializes the storage.
        :all_history: bool :
        """

        for sym in self.stats.interval:
            for inter in [self.stats.interval[sym]["interval"]] + self.stats.interval[
                sym
            ]["aggregations"]:
                start = None if all_history else now() - dt.timedelta(days=3)
                df = self.streamer.fetch_price_history(sym, inter, start)
                self.storage.store(sym, inter, df)

    # ================== Functions for main routine =====================

    def main(self, df_dict):
        """
        Main loop of the Trader.
        """
        # Periodically refresh access tokens
        if self.stats.timestamp.hour % 12 == 0 and self.stats.timestamp.minute == 0:
            self.streamer.refresh_cred()

        self.storage.add_performance_data(self.account["equity"], self.stats.timestamp)

        # Save the data locally
        for sym in df_dict:
            self.storage.store(sym, self.stats.interval[sym]["interval"], df_dict[sym])

        # Aggregate the data to other intervals
        for sym in df_dict:
            for agg in self.stats.interval[sym]["aggregations"]:
                self.storage.aggregate(sym, self.stats.interval[sym]["interval"], agg)

        # If an order was processed, fetch the latest position info.
        # Otherwise, calculate current positions locally
        update = self._update_order_queue()
        self._update_position_cache(
            df_dict, new=update, option_update=len(self.option_positions) > 0
        )

        new_algo = []
        for a in self.algo:
            if not is_freq(self.stats.timestamp, a.interval):
                new_algo.append(a)
                continue
            try:
                debugger.info(f"Running algo: {a}")
                a.main()
                new_algo.append(a)
            except Exception as e:
                debugger.warning(
                    f"Algorithm {a} failed, removing from algorithm list.\n"
                )
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
            self.order_queue[i].update(stat)

        debugger.debug(f"Updated order queue: {self.order_queue}")
        new_order = []
        order_filled = False
        for order in self.order_queue:
            # TODO: handle cancelled orders
            if order["status"] == "filled":
                order_filled = True
                debugger.debug(
                    f"Order {order['id']} filled at {order['filled_time']} at {order['filled_price']}"
                )
                self.storage.store_transaction(
                    order["filled_time"],
                    "N/A",
                    order["symbol"],
                    order["side"],
                    order["quantity"],
                    order["filled_price"],
                )
            else:
                new_order.append(order)
        self.order_queue = new_order

        # if an order was processed, update the positions and account info
        return order_filled

    def _update_position_cache(self, df_dict, new=False, option_update=False):
        """Update local cache of stocks, options, and crypto positions"""
        # Update entries in local cache
        # API should also be called if load_watch is false, as there is a high chance
        # that data in local cache are not representative of the entire portfolio,
        # meaning total equity cannot be calculated locally
        if new:
            self._fetch_account_data()
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
        self.stock_positions = self.broker.fetch_stock_positions()

    def _fetch_account_data(self):
        pos = self.broker.fetch_stock_positions()
        self.stock_positions = [p for p in pos if p["symbol"] in self.stats.interval]
        pos = self.broker.fetch_option_positions()
        self.option_positions = [
            p for p in pos if p["base_symbol"] in self.stats.interval
        ]
        pos = self.broker.fetch_crypto_positions()
        self.crypto_positions = [p for p in pos if p["symbol"] in self.stats.interval]
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
        # Check if user has enough buying power
        buy_power = self.account["buying_power"]
        if symbol_type(symbol) == "OPTION":
            price = self.streamer.fetch_option_market_data(symbol)["price"]
        else:
            price = self.storage.load(symbol, self.stats.interval[symbol]["interval"])[
                symbol
            ]["close"][-1]

        limit_price = mark_up(price)
        total_price = limit_price * quantity

        debugger.warning(
            f"Attempting to buy {quantity} shares of {symbol} at price {price} with price limit {limit_price} and a maximum total price of {total_price}"
        )

        if total_price >= buy_power:
            debugger.error(
                "Not enough buying power.\n"
                + f"Total price ({price} * {quantity} * 1.05 = {limit_price*quantity}) exceeds buying power {buy_power}."
                + "Reduce purchase quantity or increase buying power."
            )
            return None

        # TODO? Perform other checks
        ret = self.broker.buy(symbol, quantity, limit_price, in_force, extended)

        if ret is None:
            debugger.debug("BUY failed")
            return None
        self.order_queue.append(ret)
        debugger.debug(f"BUY: {self.stats.timestamp}, {symbol}, {quantity}")

        return ret

    def sell(self, symbol: str, quantity: int, in_force: str, extended: bool):
        # Check how many of the given asset we currently own
        owned_qty = self.get_asset_quantity(symbol, exclude_pending_sell=True)
        if quantity > owned_qty:
            debugger.debug(
                "SELL failed: More quantities are being sold than currently owned."
            )
            return None

        if symbol_type(symbol) == "OPTION":
            price = self.streamer.fetch_option_market_data(symbol)["price"]
        else:
            price = self.storage.load(symbol, self.stats.interval[symbol]["interval"])[
                symbol
            ]["close"][-1]

        limit_price = mark_down(price)

        ret = self.broker.sell(symbol, quantity, limit_price, in_force, extended)
        if ret is None:
            debugger.debug("SELL failed")
            return None
        self.order_queue.append(ret)
        debugger.debug(f"SELL: {self.stats.timestamp}, {symbol}, {quantity}")
        return ret

    # ================ Helper Functions ======================
    def get_asset_quantity(
        self, symbol: str = None, include_pending_buy=False, exclude_pending_sell=False
    ) -> float:
        """Returns the quantity owned of a specified asset.

        :param str? symbol:  Symbol of asset. defaults to first symbol in watchlist
        :returns: Quantity of asset as float. 0 if quantity is not owned.
        :raises:
        """
        if symbol is None:
            symbol = self.watchlist_global[0]

        if typ := symbol_type(symbol) == "OPTION":
            owned_qty = sum(
                p["quantity"] for p in self.option_positions if p["symbol"] == symbol
            )
        elif typ == "CRYPTO":
            owned_qty = sum(
                p["quantity"] for p in self.crypto_positions if p["symbol"] == symbol
            )
        else:
            owned_qty = sum(
                p["quantity"] for p in self.stock_positions if p["symbol"] == symbol
            )

        if include_pending_buy:
            owned_qty += sum(
                o["quantity"]
                for o in self.order_queue
                if o["symbol"] == symbol and o["side"] == "buy"
            )

        if exclude_pending_sell:
            owned_qty -= sum(
                o["quantity"]
                for o in self.order_queue
                if o["symbol"] == symbol and o["side"] == "sell"
            )

        return owned_qty

    # def buy_option(self, symbol: str, quantity: int, in_force: str):
    #     ret = self.broker.buy_option(symbol, quantity, in_force)
    #     if ret is None:
    #         raise Exception("BUY failed")
    #     self.order_queue.append(ret)
    #     debugger.debug(f"BUY: {self.streamer.timestamp}, {symbol}, {quantity}")
    #     debugger.debug(f"BUY order queue: {self.order_queue}")
    #     self.logger.add_transaction(self.streamer.timestamp, "buy", "option", symbol, quantity)
    #     return ret

    # def sell_option(self, symbol: str, quantity: int, in_force: str):
    #     owned_qty = sum(
    #         p["quantity"] for p in self.option_positions if p["symbol"] == symbol
    #     )
    #     owned_qty -= sum(
    #         o["quantity"]
    #         for o in self.order_queue
    #         if o["symbol"] == symbol and o["side"] == "sell"
    #     )
    #     if quantity > owned_qty:
    #         debugger.debug("SELL failed: Quantity too high")
    #         return None

    #     ret = self.broker.sell_option(symbol, quantity, in_force)
    #     if ret is None:
    #         raise Exception("SELL failed")
    #     self.order_queue.append(ret)
    #     debugger.debug(f"SELL: {self.streamer.timestamp}, {symbol}, {quantity}")
    #     debugger.debug(f"SELL order queue: {self.order_queue}")
    #     self.logger.add_transaction(self.streamer.timestamp, "sell", "option", symbol, quantity)
    #     return ret

    def set_algo(self, algo):
        """Specifies the algorithm to use.

        :param Algo algo: The algorithm to use. You can either pass in a single Algo class, or a
            list of Algo classes.
        """
        self.algo = algo if isinstance(algo, list) else [algo]

    def add_algo(self, algo):
        self.algo.append(algo)

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
        self.broker = PaperBroker(streamer=self.streamer)

        self.storage = (
            BaseStorage() if storage is None else storage
        )  # Initialize the storage
        self._init_attributes()

        self._setup_debugger(debug)
