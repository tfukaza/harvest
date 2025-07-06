import datetime as dt
import sys
import traceback
from signal import SIGINT, signal
from sys import exit
from typing import Dict, List, Union

import polars as pl
import tzlocal
from rich import box
from rich.console import Console
from rich.table import Table

from harvest.definitions import (
    Account,

    OptionPosition,
    Position,
    RuntimeData,
)
from harvest.enum import BrokerType, DataBrokerType, Interval, StorageType, TradeBrokerType
from harvest.util.factory import load_broker, load_storage
from harvest.util.helper import (
    check_interval,
    debugger,
    interval_string_to_enum,
    mark_down,
    mark_up,
    symbol_type,
    utc_current_time,
)


class BrokerHub:
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

    def __init__(
        self,
        data_broker: BrokerType = None,
        trade_broker: BrokerType = None,
        storage: StorageType = None,
        debug: bool = False,
    ) -> None:
        """
        Initializes the BrokerHub.

        :param str? data_broker: The broker to use to obtain data. If not specified, defaults to 'dummy'.
        :param str? trade_broker: The broker to use to place orders. If not specified, defaults to 'paper'.
        :param str? storage: The storage to use. If not specified, defaults to 'base', which is saves data to RAM.
        :param bool? debug: If true, the debugger will be set to debug mode. defaults to False.
        """

        self._init_checks()
        self._set_streamer_broker(data_broker, trade_broker)
        self._set_storage(storage)
        self._init_attributes()
        self._setup_debugger(debug)
        self.console = Console()

    def _init_checks(self) -> None:
        if sys.version_info[0] < 3 or sys.version_info[1] < 9:
            raise Exception("Harvest requires Python 3.9 or above.")

    def _set_streamer_broker(self, data_broker: BrokerType, trade_broker: BrokerType) -> None:
        """
        Sets the data and trade brokers.
        """

        if data_broker is None:
            if trade_broker is None:
                data_broker = BrokerType.DUMMY
            elif trade_broker.value in DataBrokerType.list():
                data_broker = trade_broker
            else:
                data_broker = BrokerType.DUMMY

        if not trade_broker:
            trade_broker = BrokerType.PAPER

        self.data_broker = data_broker
        self.trade_broker = trade_broker

        if self.data_broker.value not in BrokerType.list():
            raise Exception(f"{self.data_broker} is not recognized.")
        if self.trade_broker.value not in BrokerType.list():
            raise Exception(f"{self.trade_broker} is not recognized.")

        if self.data_broker.value not in DataBrokerType.list():
            raise Exception(f"{self.data_broker} cannot be used to retrieve data.")
        if self.trade_broker.value not in TradeBrokerType.list():
            raise Exception(f"{self.trade_broker} cannot be used to place trades.")

    def _set_storage(self, storage: StorageType) -> None:
        """
        Sets the storage to use.
        """
        if storage is None:
            storage = StorageType.BASE
        self.storage = storage

    def _init_attributes(self) -> None:
        try:
            signal(SIGINT, self.exit)
        except Exception:
            debugger.warning("Can't use signal, Harvest is running in a non-main thread.")

        self.start_data_broker = True  # If True, the streamer will start when the Trader starts
        self.skip_init = False  # If True, the Trader will not sync with the broker when it starts

        self.watchlist = []  # List of securities specified in this class
        self.algo = []  # List of algorithms to run.

        self.stats = RuntimeData(None, tzlocal.get_localzone(), None)

        
        self.account = Account()
        self.positions = self.account.positions
        self.orders = self.account.orders

    def _setup_debugger(self, debug: bool) -> None:
        # Set up logger
        if debug:
            debugger.setLevel("DEBUG")

    def _init_param_streamer_broker(self, interval, aggregations) -> None:
        # Initialize a dict of symbols and the intervals they need to run at
        self._setup_params(self.watchlist, interval, aggregations)
        self.watchlist = list(self.stats.watchlist_cfg.keys())
        if not self.watchlist:
            raise Exception("No securities were added to watchlist")

        # Load and set up streamer and broker
        self.trade_broker_ref = load_broker(self.trade_broker)()
        self.trade_broker_ref.setup(self.stats, self.account, self.main)
        self.console.print(f"- [cyan]{self.trade_broker_ref.__class__.__name__}[/cyan] setup complete")
        if self.trade_broker != self.data_broker:
            self.data_broker_ref = load_broker(self.data_broker)()
            self.data_broker_ref.setup(self.stats, self.account, self.main)
            self.trade_broker_ref.streamer = self.data_broker_ref
            self.data_broker_ref.broker = self.trade_broker_ref
            self.console.print(f"- [cyan]{self.data_broker_ref.__class__.__name__}[/cyan] setup complete")
        else:
            self.data_broker_ref = self.trade_broker_ref

        self.storage = load_storage(self.storage)()
        self.storage.setup(self.stats)

    def start(
        self,
        interval: str = "5MIN",
        aggregations: List = None,
        sync: bool = True,
        server: bool = False,
        all_history: bool = True,
    ) -> None:
        """Entry point to start the system.

        :param str? interval: The interval to run the algorithm. defaults to '5MIN'
        :param list[str]? aggregations: A list of intervals. The Trader will aggregate data to the intervals specified in this list.
            For example, if this is set to ['5MIN', '30MIN'], and interval is '1MIN', the algorithm will have access to
            5MIN, 30MIN aggregated data in addition to 1MIN data. defaults to None
        :param bool? sync: If true, the system will sync with the broker and fetch current positions and pending orders. defaults to true.
        :param bool? all_history: If true, gets all history for all the given assets and if false only get data in the past three days.
        """
        debugger.debug("Setting up Harvest")

        if aggregations == None:
            aggregations = []

        with self.console.status("[bold green] Setting up Trader...[/bold green]") as _:
            if not self.skip_init:
                self._init_param_streamer_broker(interval, aggregations)
            # If sync is on, call the broker to load pending orders and all positions currently held.
            if sync:
                self._setup_stats()
                for s in self.positions.stock_crypto:
                    self.watchlist.append(s.symbol)
                for s in self.positions.option:
                    self.watchlist.append(s.base_symbol)
                self.watchlist.extend(self.orders.stock_crypto_symbols)
                self.console.print("- Finished syncing data with broker")

            # Initialize the account
            self._setup_account()
            self.storage.init_performance_data(self.account.equity, self.stats.timestamp)

            # Initialize the storage
            self._storage_init(all_history)
            self.console.print(f"- [cyan]{self.storage.__class__.__name__}[/cyan] setup complete")

            for a in self.algo:
                a.init(self.stats, self.func, self.account)
                a.trader = self
                a.setup()
            self.console.print("- All algorithms initialized")

        self.console.print("> [bold green]Trader initialization complete[/bold green]")

        self._print_status()

        if server:
            from harvest.server import Server

            self.server = Server(self)
            self.server.start()

        if self.start_data_broker:
            try:
                self.data_broker_ref.start()
            except Exception as _:
                self.console.print_exception(show_locals=True)

    def _print_account(self) -> None:
        a = self.account

        def p_line(k, v):
            return f"{k}", f"[bold white]{v}[/bold white]"

        table = Table(
            title=a.account_name,
            show_header=False,
            show_lines=True,
            box=box.ROUNDED,
        )
        table.add_row(*p_line("Cash ($)", a.cash))
        table.add_row(*p_line("Equity ($)", a.equity))
        table.add_row(*p_line("Buying Power ($)", a.buying_power))

        self.console.print(table)

    def _print_positions(self) -> None:
        def bold(s):
            return f"[bold white]{s}[/bold white]"

        def red_or_green(s):
            if s >= 0:
                return f"[bold green]{s}[/bold green]"
            else:
                return f"[bold red]{s}[/bold red]"

        def print_table(title, positions):
            if len(positions) == 0:
                return

            stock_table = Table(
                title=title,
                show_lines=True,
                box=box.ROUNDED,
            )
            stock_table.add_column("Symbol")
            stock_table.add_column("Quantity")
            stock_table.add_column("Current Price")
            stock_table.add_column("Avg. Cost")
            stock_table.add_column("Profit/Loss")
            stock_table.add_column("Profit/Loss")

            for p in positions:
                ret_prefix = "+" if p.profit >= 0 else ""
                per_prefix = "🚀 " if p.profit_percent >= 0.1 else ""
                stock_table.add_row(
                    f"{p.symbol}",
                    f"{p.quantity}",
                    f"${p.current_price}",
                    f"${p.avg_cost}",
                    f"{per_prefix} ${ret_prefix}{red_or_green(p.profit)}",
                    f"{per_prefix} {ret_prefix}{red_or_green(p.profit_percent*100)}%",
                )
            self.console.print(stock_table)

        print_table("Stock Positions", self.positions.stock)
        print_table("Crypto Positions", self.positions.crypto)

        if len(self.positions.option) == 0:
            return

        option_table = Table(
            title="Option Positions",
            show_lines=True,
            box=box.ROUNDED,
        )
        option_table.add_column("Symbol")
        option_table.add_column("Strike Price")
        option_table.add_column("Expiration Date")
        option_table.add_column("Type")
        option_table.add_column("Quantity")
        option_table.add_column("Current Price")
        option_table.add_column("Avg. Cost")
        option_table.add_column("Profit/Loss ($)")
        option_table.add_column("Profit/Loss (%)")

        for p in self.positions.option:
            ret_prefix = "+" if p.profit >= 0 else ""
            per_prefix = "🚀 " if p.profit_percent >= 0.1 else ""
            option_table.add_row(
                f"{p.base_symbol}",
                f"{p.strike}",
                f"{p.expiration}",
                f"{p.option_type}",
                f"{p.quantity}",
                f"${p.current_price}",
                f"${p.avg_cost}",
                f"{per_prefix} {ret_prefix} {red_or_green(p.profit)}",
                f"{per_prefix} {ret_prefix} {red_or_green(p.profit_percent)}",
            )
        self.console.print(option_table)

    def _print_status(self) -> None:
        self._print_account()
        self._print_positions()

    def _setup_stats(self) -> None:
        """Initializes local cache of stocks, options, and crypto positions."""

        # Get any pending orders
        ret = self.trade_broker_ref.fetch_order_queue()
        self.orders.init(ret)
        self._update_order_queue()

        debugger.debug(f"Fetched orders:\n{self.orders}")

        # Get currently held positions
        self._fetch_account_data()

    def _setup_params(self, watchlist: List[str], interval: str, aggregations: List[str]) -> None:
        """
        Sets up configuration parameters for the Trader, notably
        the 'interval' attribute.
        """
        interval = interval_string_to_enum(interval)
        aggregations = [interval_string_to_enum(a) for a in aggregations]
        watchlist_cfg_tmp = {sym: {"interval": interval, "aggregations": aggregations} for sym in watchlist}

        debugger.debug(f"Watchlist cfg: {watchlist_cfg_tmp}")
        # Update the dict based on parameters specified in Algo class
        for a in self.algo:
            a.config()

            # If the algorithm does not specify a parameter, use the one
            # specified in the Trader class
            if len(a.watchlist) == 0:
                a.watchlist = watchlist
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
                if sym in watchlist_cfg_tmp:
                    cur_interval = watchlist_cfg_tmp[sym]["interval"]
                    if a.interval < cur_interval:
                        watchlist_cfg_tmp[sym]["aggregations"].append(cur_interval)
                        watchlist_cfg_tmp[sym]["interval"] = a.interval
                    elif a.interval > cur_interval:
                        watchlist_cfg_tmp[sym]["aggregations"].append(a.interval)
                # If symbol is not in global watchlist, simply add it
                else:
                    watchlist_cfg_tmp[sym] = {}
                    watchlist_cfg_tmp[sym]["interval"] = a.interval
                    watchlist_cfg_tmp[sym]["aggregations"] = a.aggregations

                # If the algo specifies an aggregation that is currently not set, add it to the
                # global aggregation list
                for agg in a.aggregations:
                    if agg not in watchlist_cfg_tmp[sym]["aggregations"]:
                        watchlist_cfg_tmp[sym]["aggregations"].append(agg)

        debugger.debug(f"Watchlist config: {watchlist_cfg_tmp}")

        # Remove any duplicates in the dict
        for sym in watchlist_cfg_tmp:
            new_agg = list((set(watchlist_cfg_tmp[sym]["aggregations"])))
            watchlist_cfg_tmp[sym]["aggregations"] = [] if new_agg is None else new_agg

        self.stats.watchlist_cfg = watchlist_cfg_tmp

    def _setup_account(self) -> None:
        """Initializes local cache of account info.
        For testing, it should manually be specified
        """
        ret = self.trade_broker_ref.fetch_account()
        if ret is None:
            raise Exception("Failed to load account info from broker.")
        self.account.init(ret)

    def _storage_init(self, all_history: bool) -> None:
        """
        Initializes the storage.
        :all_history: bool :
        """

        for sym in self.stats.watchlist_cfg.keys():
            for inter in [self.stats.watchlist_cfg[sym]["interval"]] + self.stats.watchlist_cfg[sym]["aggregations"]:
                start = None if all_history else utc_current_time() - dt.timedelta(days=3)
                df = self.data_broker_ref.fetch_price_history(sym, inter, start)
                self.storage.store(sym, inter, df)

    # ================== Functions for main routine =====================

    def main(self, df_dict: Dict[str, pl.DataFrame]) -> None:
        """
        Main loop of the Trader.
        """
        # # Periodically refresh access tokens
        # if self.stats.timestamp.hour % 12 == 0 and self.stats.timestamp.minute == 0:
        #     self.streamer.refresh_cred()

        debugger.debug(f"{df_dict}")

        self.storage.add_performance_data(self.account.equity, self.stats.timestamp)
        self.storage.add_calendar_data(self.data_broker_ref.fetch_market_hours(self.stats.timestamp.date()))

        # Save the data locally
        for sym in df_dict:
            self.storage.store(sym, self.stats.watchlist_cfg[sym]["interval"], df_dict[sym])

        # Aggregate the data to other intervals
        for sym in df_dict:
            for agg in self.stats.watchlist_cfg[sym]["aggregations"]:
                self.storage.aggregate(sym, self.stats.watchlist_cfg[sym]["interval"], agg)

        # If an order was processed, fetch the latest position info from the brokerage.
        # Otherwise, calculate current positions locally
        is_order_filled = self._update_order_queue()
        if is_order_filled:
            self._fetch_account_data()

        self._update_local_cache(df_dict)

        # self._print_positions()

        new_algo = []
        for a in self.algo:
            if not check_interval(self.stats.timestamp, a.interval):
                new_algo.append(a)
                continue
            try:
                # debugger.info(f"Running algo: {a}")
                a.main()
                new_algo.append(a)
            except Exception as e:
                debugger.warning(f"Algorithm {a} failed, removing from algorithm list.\n")
                debugger.warning(f"Exception: {e}\n")
                debugger.warning(f"Traceback: {traceback.format_exc()}\n")
                self.console.print_exception(show_locals=True)

        if len(new_algo) <= 0:
            debugger.critical("No algorithms to run")
            exit()

        self.algo = new_algo

        self.trade_broker_ref.exit()
        self.data_broker_ref.exit()

    def _update_order_queue(self) -> bool:
        """Check to see if outstanding orders have been accepted or rejected
        and update the order queue accordingly.
        """
        debugger.debug(f"Updating order queue: {self.orders}")
        for order in self.orders.orders:
            typ = order.type
            if typ == "STOCK":
                stat = self.trade_broker_ref.fetch_stock_order_status(order.order_id)
            elif typ == "OPTION":
                stat = self.trade_broker_ref.fetch_option_order_status(order.order_id)
            elif typ == "CRYPTO":
                stat = self.trade_broker_ref.fetch_crypto_order_status(order.order_id)
            debugger.debug(f"Updating status of order {order.order_id}")
            order.update(stat)

        order_filled = False
        for order in self.orders.orders:
            # TODO: handle cancelled orders
            if order.status == "filled":
                order_filled = True
                debugger.debug(f"Order {order.order_id} filled at {order.filled_time} at {order.filled_price}")
                self.storage.store_transaction(
                    order.filled_time,
                    "N/A",  # Name of algorithm
                    order.symbol,
                    order.side,
                    order.quantity,
                    order.filled_price,
                )
        self.orders.remove_non_open()
        debugger.debug(f"Updated order queue: {self.orders}")

        # if an order was processed, update the positions and account info
        return order_filled

    def _update_local_cache(self, df_dict: Dict[str, pl.DataFrame]) -> None:
        """Update local cache of stocks, options, and crypto positions"""
        # Update entries in local cache
        # API should also be called if load_watch is false, as there is a high chance
        # that data in local cache are not representative of the entire portfolio,
        # meaning total equity cannot be calculated locally

        debugger.debug(f"Got data: {df_dict}")

        for p in self.positions.stock_crypto:
            symbol = p.symbol
            if symbol in df_dict:
                sym_df = df_dict[symbol]
                price_df = sym_df.iloc[-1]
                price = price_df[symbol]["close"]
            elif symbol not in self.watchlist:  # handle cases when user has an asset not in watchlist
                price = self.data_broker_ref.fetch_latest_price(symbol)
            else:
                continue
            p.update(price)
        for p in self.positions.option:
            symbol = p.symbol
            price = self.data_broker_ref.fetch_option_market_data(symbol)["price"]
            p.update(price)

        self.account.update()

        debugger.debug(f"Updated positions: {self.positions}")

    def _fetch_account_data(self) -> None:
        debugger.debug("Fetching account data")
        stock_pos = [
            Position(p["symbol"], p["quantity"], p["avg_price"]) for p in self.trade_broker_ref.fetch_stock_positions()
        ]
        option_pos = [
            OptionPosition(
                p["symbol"],
                p["quantity"],
                p["avg_price"],
                p["strike_price"],
                p["exp_date"],
                p["type"],
                p["multiplier"],
            )
            for p in self.trade_broker_ref.fetch_option_positions()
        ]
        crypto_pos = [
            Position(p["symbol"], p["quantity"], p["avg_price"]) for p in self.trade_broker_ref.fetch_crypto_positions()
        ]
        self.positions.update(stock_pos, option_pos, crypto_pos)
        # Get the latest price for all positions
        for p in self.positions.stock_crypto:
            price = self.data_broker_ref.fetch_latest_price(p.symbol)
            p.update(price)
        for p in self.positions.option:
            price = self.data_broker_ref.fetch_option_market_data(p.symbol)["price"]
            p.update(price)

        ret = self.trade_broker_ref.fetch_account()

        self.account.init(ret)

    # --------------------- Interface Functions -----------------------

    def fetch_chain_info(self, *args, **kwargs):
        return self.data_broker_ref.fetch_chain_info(*args, **kwargs)

    def fetch_chain_data(self, *args, **kwargs):
        return self.data_broker_ref.fetch_chain_data(*args, **kwargs)

    def fetch_option_market_data(self, *args, **kwargs):
        return self.data_broker_ref.fetch_option_market_data(*args, **kwargs)

    def load(self, *args, **kwargs):
        return self.storage.load(*args, **kwargs)

    def store(self, *args, **kwargs):
        return self.storage.store(*args, **kwargs)

    def load_daytrade(self, *args, **kwargs):
        return self.storage.load_daytrade(*args, **kwargs)

    def buy(self, symbol: str, quantity: int, in_force: str, extended: bool):
        # Check if user has enough buying power
        buy_power = self.account.buying_power
        if symbol_type(symbol) == "OPTION":
            price = self.data_broker_ref.fetch_option_market_data(symbol)["price"]
        else:
            price = self.storage.load(symbol, self.stats.watchlist_cfg[symbol]["interval"])[symbol]["close"][-1]

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
        ret = self.trade_broker_ref.buy(symbol, quantity, limit_price, in_force, extended)
        debugger.debug(f"Account info after buy: {self.account}")

        if ret is None:
            debugger.debug("BUY failed")
            return None
        self.orders.add_new_order(symbol, ret["order_id"], "buy", quantity, in_force)
        debugger.debug(f"BUY: {self.stats.timestamp}, {symbol}, {quantity}")
        debugger.debug(f"Updated order queue: {self.orders}")

        return ret

    def sell(self, symbol: str, quantity: int, in_force: str, extended: bool):
        # Check how many of the given asset we currently own
        owned_qty = self.get_asset_quantity(symbol, True, False)
        if owned_qty == 0:
            debugger.error(f"You do not own any {symbol}")
            return None
        if quantity > owned_qty:
            debugger.debug("SELL failed: More quantities are being sold than currently owned.")
            return None

        if symbol_type(symbol) == "OPTION":
            price = self.data_broker_ref.fetch_option_market_data(symbol)["price"]
        else:
            price = self.storage.load(symbol, self.stats.watchlist_cfg[symbol]["interval"])[symbol]["close"][-1]

        limit_price = mark_down(price)

        ret = self.trade_broker_ref.sell(symbol, quantity, limit_price, in_force, extended)
        if ret is None:
            debugger.debug("SELL failed")
            return None
        self.orders.add_new_order(symbol, ret["order_id"], "sell", quantity, in_force)
        debugger.debug(f"SELL: {self.stats.timestamp}, {symbol}, {quantity}")
        return ret

    # ================ Helper Functions ======================
    def get_asset_quantity(self, symbol: str, include_pending_buy: bool, include_pending_sell: bool) -> float:
        """Returns the quantity owned of a specified asset.

        :param str? symbol:  Symbol of asset. defaults to first symbol in watchlist
        :returns: Quantity of asset as float. 0 if quantity is not owned.
        :raises:
        """
        if symbol is None:
            symbol = self.watchlist[0]
        typ = symbol_type(symbol)
        if typ == "OPTION":
            owned_qty = sum(p.quantity for p in self.positions.option if p.symbol == symbol)
        elif typ == "CRYPTO":
            owned_qty = sum(p.quantity for p in self.positions.crypto if p.symbol == symbol)
        else:
            owned_qty = sum(p.quantity for p in self.positions.stock if p.symbol == symbol)

        if include_pending_buy:
            owned_qty += sum(o.quantity for o in self.orders.orders if o.symbol == symbol and o.side == "buy")

        if not include_pending_sell:
            owned_qty -= sum(o.quantity for o in self.orders.orders if o.symbol == symbol and o.side == "sell")

        return owned_qty

    def set_algo(self, algo) -> None:
        """Specifies the algorithm to use.

        :param Algo algo: The algorithm to use. You can either pass in a single Algo class, or a
            list of Algo classes.
        """
        self.algo = algo if isinstance(algo, list) else [algo]

    def add_algo(self, algo) -> None:
        self.algo.append(algo)

    def set_symbol(self, symbol: Union[List[str], str]) -> None:
        """Specifies the symbol(s) to watch.

        Cryptocurrencies should be prepended with an `@` to differentiate them from stocks.
        For example, '@ETH' will refer to Etherium, while 'ETH' will refer to Ethan Allen Interiors.
        If this method was previously called, the symbols specified earlier will be replaced with the
        new symbols.

        :symbol str symbol: Ticker Symbol(s) of stock or cryptocurrency to watch.
            It can either be a string, or a list of strings.
        """
        self.watchlist = symbol if isinstance(symbol, list) else [symbol]

    def day_trade_count(self) -> None:
        # Get the 5-day trading window
        calendar = self.storage.load_calendar()
        debugger.debug(f"Calendar: {calendar}")
        open_days = calendar.loc[calendar["is_open"] == True]
        if len(open_days) == 0:
            return 0
        elif len(open_days) < 5:
            window_start = open_days.iloc[0]["open_at"]
        else:
            window_start = open_days.iloc[-5]["open_at"]

        # Check how many daytrades occurred in the last 5 trading days
        day_trades = self.storage.load_daytrade()
        debugger.debug(f"Day trades: {day_trades}")
        day_trades = day_trades.loc[day_trades["timestamp"] >= window_start]

        return len(day_trades)

    def exit(self, signum, frame):
        # TODO: Gracefully exit
        debugger.debug("\nStopping Harvest...")
        exit(0)


class PaperTrader(BrokerHub):
    """
    A class for trading in the paper trading environment.
    """

    def __init__(self, streamer: BrokerType = None, storage: StorageType = None, debug: bool = False) -> None:
        """Initializes the Trader."""

        self._init_checks()

        # If streamer is not specified, use YahooStreamer
        self.data_broker = DataBrokerType.DUMMY if streamer is None else streamer
        self.trade_broker = TradeBrokerType.PAPER
        self.storage = StorageType.BASE if storage is None else storage

        self._init_attributes()
        self._setup_debugger(debug)
        self.console = Console()
