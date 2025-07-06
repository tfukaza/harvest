import sys
from sys import exit
from typing import Dict, List, Union

import polars as pl
from rich.console import Console

from harvest.algorithm import Algorithm
from harvest.broker._base import Broker
from harvest.definitions import (
    Account,
    AssetType,
    OptionPosition,
    Order,
    Position,
    RuntimeData,
)
from harvest.enum import BrokerType, DataBrokerType, Interval, StorageType, TradeBrokerType
from harvest.storage._base import Storage
from harvest.util.helper import (
    applicable_intervals_for_time,
    debugger,
    mark_down,
    mark_up,
    symbol_type,
)

interval_list: list[Interval] = [
    Interval.SEC_15,
    Interval.MIN_1,
    Interval.MIN_5,
    Interval.MIN_15,
    Interval.MIN_30,
    Interval.HR_1,
    Interval.DAY_1,
]


class Client:
    watch_list: list[str]
    algorithm_list: list[Algorithm]
    broker: Broker
    storage: Storage
    stats: RuntimeData
    account: Account | None
    secret_path: str = "./secret.yaml"

    _order_queue: List[Order] = []
    _interval_table: dict[Interval, dict[str, dict]] = {}

    def __init__(
        self,
        broker: Broker,
        storage: Storage,
        algorithm_list: List[Algorithm],
        secret_path: str = "./secret.yaml",
        sync_with_broker: bool = False,
        debug: bool = False,
    ) -> None:
        """
        Initializes the Client.

        :param Type[Broker]? broker: The broker to use. If not specified, defaults to 'dummy'.
        :param str? storage: The storage to use. If not specified, defaults to 'base', which is saves data to RAM.
        :param bool? debug: If true, the debugger will be set to debug mode. defaults to False.
        """

        if sys.version_info[0] < 3 or sys.version_info[1] < 9:
            raise Exception("Harvest requires Python 3.9 or above.")

        self.broker = broker
        self.storage = storage
        self.console = Console()

        self.watch_list = []
        self.algorithm_list = algorithm_list

        self.account = None
        self.secret_path = secret_path
        if debug:
            debugger.setLevel("DEBUG")

        self.sync_with_broker = sync_with_broker

        # Create a table of all intervals, and the algorithms and symbols that need them
        interval_table = {interval: {"algorithms": [], "symbols": set()} for interval in interval_list}

        # Update the dict based on parameters specified in Algo class
        for algorithm in self.algorithm_list:
            for interval in algorithm.aggregations:
                interval_table[interval]["algorithms"].append(algorithm)
                interval_table[interval]["symbols"].update(algorithm.watch_list)

        # Check if the requested intervals are supported by the broker
        for interval, algo_list in interval_table.items():
            if len(algo_list) and interval not in self.broker.interval_list:
                raise Exception(f"Interval {interval} is not supported by the broker")

        # Remove intervals that are not needed
        for interval in interval_table.keys():
            if len(interval_table[interval]["algorithms"]) == 0:
                del interval_table[interval]

        self._interval_table = interval_table

        debugger.debug(f"Interval table: {self._interval_table}")

    def start(self) -> None:
        """Entry point to start the system."""
        debugger.debug("Setting up Harvest")

        with self.console.status("[bold green] Setting up Trader...[/bold green]") as _:
            self.broker.setup(self.secret_path)
            self.console.print(f"- [cyan]{self.broker.__class__.__name__}[/cyan] setup complete")

            # Initialize the account
            account = self.broker.fetch_account()
            if account is None:
                raise Exception("Failed to load account info from broker.")
            self.account = account

            # Initialize the storage
            self.storage.setup(self.stats)
            # self.storage.init_performance_data(self.account.equity, self.stats.utc_timestamp)

            # Save the historical data
            # self._storage_init(all_history)
            self.console.print(f"- [cyan]{self.storage.__class__.__name__}[/cyan] setup complete")

            for algorithm in self.algorithm_list:
                algorithm.initialize_algorithm(self, self.stats, self.account)
                algorithm.setup()
            self.console.print("- All algorithms initialized")

        self.console.print("> [bold green]Trader initialization complete[/bold green]")

        # self._print_status()

        # if server:
        #     from harvest.server import Server

        #     self.server = Server(self)
        #     self.server.start()

        # if self.start_data_broker:
        #     try:
        #         self.data_broker_ref.start()
        #     except Exception as _:
        #         self.console.print_exception(show_locals=True)

    # def _print_account(self) -> None:
    #     a = self.account

    #     def p_line(k, v):
    #         return f"{k}", f"[bold white]{v}[/bold white]"

    #     table = Table(
    #         title=a.account_name,
    #         show_header=False,
    #         show_lines=True,
    #         box=box.ROUNDED,
    #     )
    #     table.add_row(*p_line("Cash ($)", a.cash))
    #     table.add_row(*p_line("Equity ($)", a.equity))
    #     table.add_row(*p_line("Buying Power ($)", a.buying_power))

    #     self.console.print(table)

    # def _print_positions(self) -> None:
    #     def bold(s):
    #         return f"[bold white]{s}[/bold white]"

    #     def red_or_green(s):
    #         if s >= 0:
    #             return f"[bold green]{s}[/bold green]"
    #         else:
    #             return f"[bold red]{s}[/bold red]"

    #     def print_table(title, positions):
    #         if len(positions) == 0:
    #             return

    #         stock_table = Table(
    #             title=title,
    #             show_lines=True,
    #             box=box.ROUNDED,
    #         )
    #         stock_table.add_column("Symbol")
    #         stock_table.add_column("Quantity")
    #         stock_table.add_column("Current Price")
    #         stock_table.add_column("Avg. Cost")
    #         stock_table.add_column("Profit/Loss")
    #         stock_table.add_column("Profit/Loss")

    #         for p in positions:
    #             ret_prefix = "+" if p.profit >= 0 else ""
    #             per_prefix = "🚀 " if p.profit_percent >= 0.1 else ""
    #             stock_table.add_row(
    #                 f"{p.symbol}",
    #                 f"{p.quantity}",
    #                 f"${p.current_price}",
    #                 f"${p.avg_cost}",
    #                 f"{per_prefix} ${ret_prefix}{red_or_green(p.profit)}",
    #                 f"{per_prefix} {ret_prefix}{red_or_green(p.profit_percent*100)}%",
    #             )
    #         self.console.print(stock_table)

    #     print_table("Stock Positions", self.positions.stock)
    #     print_table("Crypto Positions", self.positions.crypto)

    #     if len(self.positions.option) == 0:
    #         return

    #     option_table = Table(
    #         title="Option Positions",
    #         show_lines=True,
    #         box=box.ROUNDED,
    #     )
    #     option_table.add_column("Symbol")
    #     option_table.add_column("Strike Price")
    #     option_table.add_column("Expiration Date")
    #     option_table.add_column("Type")
    #     option_table.add_column("Quantity")
    #     option_table.add_column("Current Price")
    #     option_table.add_column("Avg. Cost")
    #     option_table.add_column("Profit/Loss ($)")
    #     option_table.add_column("Profit/Loss (%)")

    #     for p in self.positions.option:
    #         ret_prefix = "+" if p.profit >= 0 else ""
    #         per_prefix = "🚀 " if p.profit_percent >= 0.1 else ""
    #         option_table.add_row(
    #             f"{p.base_symbol}",
    #             f"{p.strike}",
    #             f"{p.expiration}",
    #             f"{p.option_type}",
    #             f"{p.quantity}",
    #             f"${p.current_price}",
    #             f"${p.avg_cost}",
    #             f"{per_prefix} {ret_prefix} {red_or_green(p.profit)}",
    #             f"{per_prefix} {ret_prefix} {red_or_green(p.profit_percent)}",
    #         )
    #     self.console.print(option_table)

    # def _print_status(self) -> None:
    #     self._print_account()
    #     self._print_positions()

    # def _setup_stats(self) -> None:
    #     """Initializes local cache of stocks, options, and crypto positions."""

    #     # Get any pending orders
    #     ret = self.trade_broker_ref.fetch_order_queue()
    #     self.orders.init(ret)
    #     self.update_order_queue()

    #     debugger.debug(f"Fetched orders:\n{self.orders}")

    #     # Get currently held positions
    #     self._fetch_account_data()

    # def _setup_account(self) -> None:
    #     """Initializes local cache of account info.
    #     For testing, it should manually be specified
    #     """
    #     ret = self.trade_broker_ref.fetch_account()
    #     if ret is None:
    #         raise Exception("Failed to load account info from broker.")
    #     self.account.init(ret)

    # def _storage_init(self, all_history: bool) -> None:
    #     """
    #     Initializes the storage.
    #     :all_history: bool :
    #     """

    #     for sym in self.stats.watchlist_cfg.keys():
    #         for inter in [self.stats.watchlist_cfg[sym]["interval"]] + self.stats.watchlist_cfg[sym]["aggregations"]:
    #             start = None if all_history else utc_current_time() - dt.timedelta(days=3)
    #             df = self.data_broker_ref.fetch_price_history(sym, inter, start)
    #             self.storage.store(sym, inter, df)

    # ================== Functions for main routine =====================

    def tick(self, df_dict: Dict[str, pl.DataFrame]) -> None:
        """
        Main loop of the Trader.
        """
        # # Periodically refresh access tokens
        # if self.stats.timestamp.hour % 12 == 0 and self.stats.timestamp.minute == 0:
        #     self.streamer.refresh_cred()

        debugger.debug(f"{df_dict}")

        # self.storage.add_performance_data(self.account.equity, self.stats.timestamp)
        # self.storage.add_calendar_data(self.data_broker_ref.fetch_market_hours(self.stats.timestamp.date()))

        # Save the data locally
        # for sym in df_dict:
        #     self.storage.store(sym, self.stats.watchlist_cfg[sym]["interval"], df_dict[sym])

        # Aggregate the data to other intervals
        # for sym in df_dict:
        #     for agg in self.stats.watchlist_cfg[sym]["aggregations"]:
        #         self.storage.aggregate(sym, self.stats.watchlist_cfg[sym]["interval"], agg)

        # If an order was processed, fetch the latest position info from the brokerage.
        # Otherwise, calculate current positions locally
        is_order_filled = self.update_order_queue()
        if is_order_filled:
            self._fetch_account_data()

        # self._update_local_cache(df_dict)

        # self._print_positions()
        applicable_intervals = applicable_intervals_for_time(self.stats.broker_timestamp)

        for interval in applicable_intervals:
            algorithms = self._interval_table[interval]["algorithms"]
            for a in algorithms:
                a.main()
        #     try:
        #         # debugger.info(f"Running algo: {a}")
        #         a.main()
        #         new_algo.append(a)
        #     except Exception as e:
        #         debugger.warning(f"Algorithm {a} failed, removing from algorithm list.\n")
        #         debugger.warning(f"Exception: {e}\n")
        #         debugger.warning(f"Traceback: {traceback.format_exc()}\n")
        #         self.console.print_exception(show_locals=True)

        # if len(new_algo) <= 0:
        #     debugger.critical("No algorithms to run")
        #     exit()

        # self.algo = new_algo

        # self.trade_broker_ref.exit()
        # self.data_broker_ref.exit()

    def update_order_queue(self) -> bool:
        """Check to see if outstanding orders have been accepted or rejected
        and update the order queue accordingly.
        """
        debugger.debug(f"Updating order queue: {self._order_queue}")
        for order in self._order_queue:
            if order.order_type == AssetType.STOCK:
                stat = self.broker.fetch_stock_order_status(order.order_id)
            elif order.order_type == AssetType.OPTION:
                stat = self.broker.fetch_option_order_status(order.order_id)
            elif order.order_type == AssetType.CRYPTO:
                stat = self.broker.fetch_crypto_order_status(order.order_id)

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
            elif symbol not in self.watch_list:  # handle cases when user has an asset not in watchlist
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

    def buy(self, symbol: str, quantity: int, in_force: str, extended: bool) -> Order:
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
            symbol = self.watch_list[0]
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
        self.watch_list = symbol if isinstance(symbol, list) else [symbol]

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
