import dataclasses
import math
import datetime as dt
from datetime import timezone
from enum import StrEnum
from typing import TYPE_CHECKING, Literal, Any

import numpy as np
import polars as pl
from finta import TA

from harvest.definitions import Account, RuntimeData, OptionData, ChainInfo, ChainData, Order, TickerFrame, Position, OptionPosition, Transaction, TransactionFrame, OrderSide, OrderEvent
from harvest.enum import Interval
from harvest.plugin._base import Plugin
from harvest.util.date import convert_input_to_datetime, datetime_utc_to_local, pandas_timestamp_to_local
from harvest.util.helper import (
    debugger,
    interval_string_to_enum,
    mark_up,
    symbol_type,
)
from harvest.storage._base import LocalAlgorithmStorage
from harvest.services.discovery import ServiceRegistry
from harvest.events.event_bus import EventBus
from harvest.events.events import PriceUpdateEvent, OrderFilledEvent, AccountUpdateEvent

if TYPE_CHECKING:
    from harvest.services.market_data_service import MarketDataService
    from harvest.services.broker_service import BrokerService
    from harvest.services.central_storage_service import CentralStorageService

from zoneinfo import ZoneInfo


class AlgorithmStatus(StrEnum):
    PENDING = "pending"
    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    CRASHED = "crashed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclasses.dataclass
class AlgorithmHealth:
    status: AlgorithmStatus = AlgorithmStatus.PENDING
    last_update: dt.datetime | None = None
    error_count: int = 0
    last_error: str | None = None


"""
Algo class is the main interface between users and the program.
"""


class Algorithm:
    """The Algorithm class is an abstract class defining the interface for users to
    track assets, monitor their accounts, and place orders.
    It also provides function for technical analysis.
    """

    watch_list: list[str]  # List of assets this algorithm tracks
    interval: Interval  # Interval to run the algorithm
    aggregations: list[Interval]  # List of aggregation intervals

    # Algorithm-owned storage
    local_storage: LocalAlgorithmStorage

    # Service discovery and events
    service_registry: ServiceRegistry
    event_bus: EventBus

    # Shared services (will be discovered)
    market_data_service: "MarketDataService | None" = None
    broker_services: list["BrokerService"] = []
    central_storage_services: list["CentralStorageService"] = []

    # Runtime data
    stats: RuntimeData | None = None
    account: Account | None = None
    health: AlgorithmHealth

    def __init__(self, watch_list: list[str], interval: Interval, aggregations: list[Interval]):
        self.interval = interval
        self.aggregations = aggregations
        self.watch_list = watch_list

        # Algorithm-owned storage
        self.local_storage = LocalAlgorithmStorage(
            algorithm_name=self.__class__.__name__,
            db_path=f"sqlite:///algorithms/{self.__class__.__name__}.db"
        )

        # Service discovery and events
        self.service_registry = ServiceRegistry()
        self.event_bus = EventBus()

        # Shared services (will be discovered)
        self.market_data_service = None
        self.broker_services = []
        self.central_storage_services = []

        # Runtime data
        self.stats = None
        self.account = None
        self.health = AlgorithmHealth()

    @property
    def broker_service(self) -> "BrokerService | None":
        """Returns the default broker service."""
        if self.broker_services:
            return self.broker_services[0]
        return None

    @property
    def central_storage_service(self) -> "CentralStorageService | None":
        """Returns the default central storage service."""
        if self.central_storage_services:
            return self.central_storage_services[0]
        return None

    async def discover_services(self) -> None:
        """Discover and connect to required services"""
        self.market_data_service = self.service_registry.discover_service("market_data")  # type: ignore
        self.broker_services = self.service_registry.discover_services("broker")  # type: ignore
        self.central_storage_services = self.service_registry.discover_services("central_storage")  # type: ignore

        if not all([self.market_data_service, self.broker_services, self.central_storage_services]):
            raise Exception("Required services not found")

    def setup_event_subscriptions(self) -> None:
        """Subscribe to relevant events"""
        self.event_bus.subscribe('price_update', self._handle_price_update_event)
        self.event_bus.subscribe('order_filled', self._handle_order_filled_event)
        self.event_bus.subscribe('account_update', self._handle_account_update_event)

    def subscribe_to_price_updates(self, symbols: list[str] | None = None,
                                 intervals: list[Interval] | None = None,
                                 broker_id: str | None = None) -> str:
        """
        Subscribe to price updates with optional filtering.

        :symbols: List of symbols to filter by (None for all symbols in watchlist)
        :intervals: List of intervals to filter by (None for all intervals)
        :broker_id: Specific broker ID to filter by (None for all brokers)
        :returns: Subscription ID for later unsubscription
        """
        # Use watchlist if no specific symbols provided
        if symbols is None:
            symbols = self.watch_list

        # Create filters for the subscription
        filters = {}

        # Add symbol filter if specific symbols requested
        if symbols and len(symbols) == 1:
            filters['symbol'] = symbols[0]

        # Add interval filter if specific interval requested
        if intervals and len(intervals) == 1:
            filters['interval'] = intervals[0].value

        # Add broker filter if specific broker requested
        if broker_id:
            filters['broker_id'] = broker_id

        # Subscribe with filters
        return self.event_bus.subscribe('price_update', self._handle_filtered_price_update, filters)

    def _handle_filtered_price_update(self, event_data: dict) -> None:
        """Handle filtered price update events"""
        # Check if symbol is in our watchlist (additional validation)
        symbol = event_data.get('symbol', '')
        if symbol in self.watch_list:
            self._handle_price_update_event(event_data)

    def _handle_price_update_event(self, event_data: dict) -> None:
        """Handle incoming price update events from event bus"""
        # Convert dict to PriceUpdateEvent dataclass
        event = PriceUpdateEvent(
         **event_data  # Unpack the event data directly
        )
        self._handle_price_update(event)

    def _handle_order_filled_event(self, event_data: dict) -> None:
        """Handle order fill events from event bus"""
        # Convert dict to OrderFilledEvent
        event = OrderFilledEvent(
            order_id=event_data['order_id'],
            algorithm_name=event_data['algorithm_name'],
            symbol=event_data['symbol'],
            fill_price=event_data['fill_price'],
            fill_quantity=event_data['fill_quantity'],
            side=event_data['side'],
            timestamp=event_data['timestamp'],
            order=event_data.get('order')
        )
        self._handle_order_filled(event)

    def _handle_account_update_event(self, event_data: dict) -> None:
        """Handle account update events from event bus"""
        # Convert dict to AccountUpdateEvent
        event = AccountUpdateEvent(
            algorithm_name=event_data['algorithm_name'],
            equity=event_data['equity'],
            buying_power=event_data['buying_power'],
            cash=event_data['cash'],
            asset_value=event_data['asset_value'],
            timestamp=event_data['timestamp'],
            account=event_data.get('account')
        )
        self._handle_account_update(event)

    def _handle_price_update(self, event: PriceUpdateEvent) -> None:
        """Handle incoming price updates"""
        if event.symbol in self.watch_list:
            # Update internal state, trigger algorithm logic if needed
            pass

    def _handle_order_filled(self, event: OrderFilledEvent) -> None:
        """Handle order fill notifications"""
        # Update local performance tracking
        pass

    def _handle_account_update(self, event: AccountUpdateEvent) -> None:
        """Handle account updates"""
        self.account = event.account

    def setup(self) -> None:
        """
        Method called right before algorithm begins.
        """
        pass

    async def main(self) -> None:
        """
        Main method to run the algorithm.
        """
        pass

    def add_plugin(self, plugin: Plugin) -> None:
        """
        Adds a plugin to the algorithm.
        """
        value = getattr(self, plugin.name, None)
        if value is None:
            setattr(self, plugin.name, plugin)
        else:
            debugger.error(f"Plugin name is already in use! {plugin.name} points to {value}.")

    ############ Functions interfacing with broker through the trader #################

    async def buy(
        self,
        symbol: str,
        quantity: int,
        in_force: Literal["gtc", "gtd"] = "gtc",
        extended: bool = False,
        broker: str | None = None,
    ) -> Order | None:
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
        :param str? broker: Name of broker to use (optional, defaults to first)

        :returns: The following Python dictionary
            - order_id: str, ID of order
            - symbol: str, symbol of asset

        :raises Exception: There is an error in the order process.
        """
        debugger.debug(f"Submitted buy order for {symbol} with quantity {quantity}")

        # Get the specified broker service
        broker_service = self.get_broker_service(name=broker)
        if not broker_service:
            await self.discover_services()
            broker_service = self.get_broker_service(name=broker)

        if not broker_service:
            raise Exception(f"Broker service not found (name: {broker})")

        order = await broker_service.place_order(  # type: ignore
            symbol=symbol,
            side=OrderSide.BUY,
            quantity=quantity,
            order_type="market",  # or limit with price calculation
            time_in_force=in_force,
            extended_hours=extended
        )

        if order:
            # Store in local transaction history
            transaction = Transaction(
                timestamp=dt.datetime.utcnow(),
                symbol=symbol,
                side=OrderSide.BUY,
                quantity=quantity,
                price=0.0,  # Will be updated on fill
                event=OrderEvent.ORDER,
                algorithm_name=self.__class__.__name__
            )
            self.local_storage.insert_transaction(transaction)

        return order

    async def sell(
        self,
        symbol: str,
        quantity: int,
        in_force: Literal["gtc", "gtd"] = "gtc",
        extended: bool = False,
        broker: str | None = None,
    ) -> Order | None:
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
        :param str? broker: Name of broker to use (optional, defaults to first)

        :returns: A dictionary with the following keys:
            - order_id: str, ID of order
            - symbol: str, symbol of asset

        :raises Exception: There is an error in the order process.
        """

        debugger.debug(f"Submitted sell order for {symbol} with quantity {quantity}")

        broker_service = self.get_broker_service(name=broker)
        if not broker_service:
            await self.discover_services()
            broker_service = self.get_broker_service(name=broker)

        if not broker_service:
            raise Exception("Broker service not available")

        order = await broker_service.place_order(  # type: ignore
            symbol=symbol,
            side=OrderSide.SELL,
            quantity=quantity,
            order_type="market",  # or limit with price calculation
            time_in_force=in_force,
            extended_hours=extended
        )

        if order:
            # Store in local transaction history
            transaction = Transaction(
                timestamp=dt.datetime.utcnow(),
                symbol=symbol,
                side=OrderSide.SELL,
                quantity=quantity,
                price=0.0,  # Will be updated on fill
                event=OrderEvent.ORDER,
                algorithm_name=self.__class__.__name__
            )
            self.local_storage.insert_transaction(transaction)

        return order

    def get_price_history(self, symbol: str, interval: Interval | None = None,
                         start: dt.datetime | None = None, end: dt.datetime | None = None,
                         storage: str | None = None) -> TickerFrame:
        """Get market data from central storage service

        :param str symbol: Symbol to get price history for
        :param Interval? interval: Interval for price data (defaults to algorithm interval)
        :param datetime? start: Start time for price history
        :param datetime? end: End time for price history
        :param str? storage: Name of storage to use (optional, defaults to first)
        :returns: TickerFrame with price history
        """
        storage_service = self.get_central_storage_service(name=storage)
        if not storage_service:
            raise Exception("Central storage service not available")

        return storage_service.get_price_history(symbol, interval or self.interval, start, end)  # type: ignore

    def get_my_transactions(self, symbol: str) -> TransactionFrame:
        """Get this algorithm's transaction history"""
        return self.local_storage.get_transaction_history(symbol)

    def update_my_performance(self, equity: float) -> None:
        """Update this algorithm's performance metrics"""
        previous_performance = self.local_storage.get_latest_performance("5min_1day")
        previous_equity = previous_performance["equity"] if previous_performance else None

        self.local_storage.update_performance_data(
            timestamp=dt.datetime.utcnow(),
            equity=equity,
            previous_equity=previous_equity
        )

    async def sell_all_options(self, symbol: str | None = None, in_force: str = "gtc",
                              broker: str | None = None) -> list[Order | None]:
        """Sells all options based on the specified stock.

        For example, if you call this function with `symbol` set to "TWTR", it will sell
        all options you own that is related to TWTR.

        :param str? symbol: symbol of stock. defaults to first symbol in watchlist
        :param str? in_force: Duration the order is in force. defaults to "gtc"
        :param str? broker: Name of broker to use (optional, defaults to first)
        :returns: A list of dictionaries with the following keys:
            - order_id: str, ID of order
            - symbol: str, symbol of asset
        """
        if symbol is None:
            symbol = self.watch_list[0]

        broker_service = self.get_broker_service(name=broker)
        if not broker_service:
            await self.discover_services()
            broker_service = self.get_broker_service(name=broker)

        if not broker_service:
            raise Exception("Broker service not available")

        # Get option positions from broker service
        positions = await broker_service.get_positions()
        option_positions = [pos for pos in positions if pos.symbol.startswith(symbol) and symbol_type(pos.symbol) == "OPTION"]

        ret = []
        for pos in option_positions:
            debugger.debug(f"Algo SELL OPTION: {pos.symbol}")
            order = await self.sell(pos.symbol, int(pos.quantity), in_force, True, broker)  # type: ignore
            ret.append(order)

        return ret

    async def filter_option_chain(
        self,
        symbol: str | None = None,
        type: str | None = None,
        lower_exp: str | dt.datetime | None = None,
        upper_exp: str | dt.datetime | None = None,
        lower_strike: float | None = None,
        upper_strike: float | None = None,
    ) -> TickerFrame:
        """Returns a TickerFrame of options that satisfies the criteria specified.

        The lower_exp and upper_exp input can either be a string in the format "YYYY-MM-DD" or a datetime object.

        :param str symbol: Symbol of stock. defaults to first symbol in watchlist.
        :param str? type: 'call' or 'put'
        :param str? lower_exp: Minimum expiration date of the option, inclusive.
        :param str? upper_exp: Maximum expiration date of the option, inclusive.
        :param float lower_strike: The minimum strike price of the option, inclusive.
        :param float upper_strike: The maximum strike price of the option, inclusive.

        :returns: A TickerFrame, with an index of strings representing the OCC symbol of options, and the following columns
        |symbol | type | strike
        |-------|------|-------
        |(str) ticker of stock | 'call' or 'put' | (float) strike price

        """
        if symbol is None:
            symbol = self.watch_list[0]
        utc_zone = ZoneInfo("UTC")
        lower_exp = convert_input_to_datetime(lower_exp, utc_zone) if lower_exp is not None else None
        upper_exp = convert_input_to_datetime(upper_exp, utc_zone) if upper_exp is not None else None
        # Remove timezone from datetime objects

        chain_info = await self.get_option_chain_info(symbol)
        exp_dates = chain_info.expiration_list
        if lower_exp is not None:
            lower_exp = lower_exp.replace(tzinfo=None)
            exp_dates = list(filter(lambda x: x >= lower_exp, exp_dates))
        if upper_exp is not None:
            upper_exp = upper_exp.replace(tzinfo=None)
            exp_dates = list(filter(lambda x: x <= upper_exp, exp_dates))
        exp_dates = sorted(exp_dates)

        exp_date = exp_dates[0]

        chain = await self.get_option_chain(symbol, exp_date)
        chain_df = chain._df
        if lower_strike is not None:
            chain_df = chain_df.filter(pl.col("strike") >= lower_strike)
        if upper_strike is not None:
            chain_df = chain_df.filter(pl.col("strike") <= upper_strike)

        if type is not None:
            chain_df = chain_df.filter(pl.col("type") == type)

        chain_df = chain_df.sort(["strike", "exp_date"])

        return TickerFrame(chain_df)

    # ------------------ Functions to trade options ----------------------

    async def get_option_chain_info(self, symbol: str | None = None) -> ChainInfo:
        """Returns data of a stock's option chain.

        Given a stock's symbol, this function returns a ChainInfo dataclass with two data.
        The first is a list indicating the available expiration dates of the option.
        The second is the multiplier, which indicates how many contracts are in a single option.
        For example, if you buy an option priced at $1.20 and the multiplier is 100,
        you will need to pay $120 to buy one option.

        This function is often used in conjunction with the get_option_chain function.

        :param str? symbol: symbol of stock. defaults to first symbol in watchlist
        :returns: A ChainInfo dataclass with the following attributes:
            - chain_id: ID of the option chain
            - expiration_list: List of expiration dates as datetime objects
        """
        if symbol is None:
            symbol = self.watch_list[0]

        if not self.market_data_service:
            await self.discover_services()

        assert symbol is not None, "Symbol cannot be None"
        assert self.market_data_service is not None
        return await self.market_data_service.fetch_chain_info(symbol)

    async def get_option_chain(self, symbol: str | None, date) -> ChainData:
        """Returns the option chain for the specified symbol and expiration date.

        The date parameter can either be a string in the format "YYYY-MM-DD" or a datetime object.
        This function is often used in conjunction with the get_option_chain_info function in order to
        retrieve the available expiration dates.

        :param str symbol: symbol of stock
        :param date: date of option expiration
        :returns: A ChainData dataclass containing a DataFrame with the following columns:

            - exp_date(datetime.datetime): The expiration date, as offset-naive DateTime object
            *with timezone adjusted to the timezone of the exchange being used*
            - strike(float): Strike price
            - type(str): 'call' or 'put'

        The index is the OCC symbol of the option.
        """
        if symbol is None:
            symbol = self.watch_list[0]

        if not self.market_data_service:
            await self.discover_services()

        assert symbol is not None, "Symbol cannot be None"

        # Use UTC timezone as default if stats not available
        timezone = self.stats.broker_timezone if self.stats else ZoneInfo("UTC")
        date = convert_input_to_datetime(date, timezone)

        assert self.market_data_service is not None
        result = await self.market_data_service.fetch_chain_data(symbol, date)
        # Handle brokers that might return different types
        if isinstance(result, ChainData):
            return result
        else:
            # Convert or handle other return types as needed
            # For now, assume it should be ChainData and let runtime handle it
            return result  # type: ignore

    async def get_option_market_data(self, symbol: str | None = None) -> OptionData:
        """Retrieves data of specified option.

        Note that the price returned by this function returns the price per contract,
        not the total price of the option.

        :param str? symbol: OCC symbol of option
        :returns: An OptionData dataclass with the following attributes:
            - symbol: OCC symbol of the option
            - price: price of option per contract
            - ask: ask price
            - bid: bid price
            - expiration: expiration date
            - strike: strike price
        """
        if symbol is None:
            symbol = self.watch_list[0]

        if not self.market_data_service:
            await self.discover_services()

        assert symbol is not None, "Symbol cannot be None"
        assert self.market_data_service is not None
        result = await self.market_data_service.fetch_option_market_data(symbol)
        return result

    # ------------------ Technical Indicators -------------------

    def _default_param(self, symbol: str | None, interval: Interval | str | None, ref: str, prices: list | None,
                      storage: str | None = None) -> tuple[str, Interval, str, list]:
        if symbol is None:
            symbol = self.watch_list[0]

        if interval is None:
            # Use algorithm interval if no specific interval config is available
            interval = self.interval
        elif isinstance(interval, str):
            interval = interval_string_to_enum(interval)

        if prices is None:
            storage_service = self.get_central_storage_service(name=storage)
            if not storage_service:
                raise Exception("Central storage service not available")
            ticker_frame = storage_service.get_price_history(symbol, interval)
            prices = list(ticker_frame.get_column(ref))

        return symbol, interval, ref, prices

    def rsi(
        self,
        symbol: str | None = None,
        period: int = 14,
        interval: Interval | None = None,
        ref: str = "close",
        prices=None,
        storage: str | None = None,
    ) -> np.ndarray | None:
        """Calculate RSI

        :param str? symbol:     Symbol to perform calculation on. defaults to first symbol in watchlist
        :param int? period:     Period of RSI. defaults to 14
        :param str? interval:   Interval to perform the calculation. defaults to interval of algorithm
        :param str? ref:        'close', 'open', 'high', or 'low'. defaults to 'close'
        :param list? prices:    When specified, this function will use the values provided in the
                                list to perform calculations and ignore other parameters. defaults to None
        :param str? storage: Name of storage to use (optional, defaults to first)
        :returns: A list in numpy format, containing RSI values
        """
        symbol, interval, ref, prices = self._default_param(symbol, interval, ref, prices, storage)

        if len(prices) < period:
            debugger.warning("Not enough data to calculate RSI, returning None")
            return None

        ohlc = pl.DataFrame(
            {
                "close": np.array(prices),
                "open": np.zeros(len(prices)),
                "high": np.zeros(len(prices)),
                "low": np.zeros(len(prices)),
            }
        )
        return TA.RSI(ohlc.to_pandas(), period=period).to_numpy()

    def sma(
        self,
        symbol: str | None = None,
        period: int = 14,
        interval: Interval | None = None,
        ref: str = "close",
        prices=None,
        storage: str | None = None,
    ) -> np.ndarray | None:
        """Calculate SMA

        :param str? symbol:    Symbol to perform calculation on. defaults to first symbol in watchlist
        :param int? period:    Period of SMA. defaults to 14
        :param str? interval:  Interval to perform the calculation. defaults to interval of algorithm
        :param str? ref:       'close', 'open', 'high', or 'low'. defaults to 'close'
        :param list? prices:    When specified, this function will use the values provided in the
                                list to perform calculations and ignore other parameters. defaults to None
        :param str? storage: Name of storage to use (optional, defaults to first)
        :returns: A list in numpy format, containing SMA values
        """
        symbol, interval, ref, prices = self._default_param(symbol, interval, ref, prices, storage)

        if len(prices) < period:
            debugger.warning("Not enough data to calculate SMA, returning None")
            return None

        ohlc = pl.DataFrame(
            {
                "close": np.array(prices),
                "open": np.zeros(len(prices)),
                "high": np.zeros(len(prices)),
                "low": np.zeros(len(prices)),
            }
        )
        return TA.SMA(ohlc.to_pandas(), period=period).to_numpy()

    def ema(
        self,
        symbol: str | None = None,
        period: int = 14,
        interval: Interval | None = None,
        ref: str = "close",
        prices=None,
        storage: str | None = None,
    ) -> np.ndarray | None:
        """Calculate EMA

        :param str? symbol:    Symbol to perform calculation on. defaults to first symbol in watchlist
        :param int? period:    Period of EMA. defaults to 14
        :param str? interval:  Interval to perform the calculation. defaults to interval of algorithm
        :param str? ref:       'close', 'open', 'high', or 'low'. defaults to 'close'
        :param list? prices:    When specified, this function will use the values provided in the
                                list to perform calculations and ignore other parameters. defaults to None
        :param str? storage: Name of storage to use (optional, defaults to first)
        :returns: A list in numpy format, containing EMA values
        """
        symbol, interval, ref, prices = self._default_param(symbol, interval, ref, prices, storage)

        if len(prices) < period:
            debugger.warning("Not enough data to calculate EMA, returning None")
            return None

        ohlc = pl.DataFrame(
            {
                "close": np.array(prices),
                "open": np.zeros(len(prices)),
                "high": np.zeros(len(prices)),
                "low": np.zeros(len(prices)),
            }
        )
        return TA.EMA(ohlc.to_pandas(), period=period).to_numpy()

    def bbands(
        self,
        symbol: str | None = None,
        period: int = 14,
        interval: Interval | None = None,
        ref: str = "close",
        dev: float = 1.0,
        prices=None,
        storage: str | None = None,
    ) -> tuple[np.ndarray | None, np.ndarray | None, np.ndarray | None]:
        """Calculate Bollinger Bands

        :param str? symbol:    Symbol to perform calculation on. defaults to first symbol in watchlist
        :param int? period:    Period of BBands. defaults to 14
        :param str? interval:  Interval to perform the calculation. defaults to interval of algorithm
        :param str? ref:       'close', 'open', 'high', or 'low'. defaults to 'close'
        :param float? dev:         Standard deviation of the bands. defaults to 1.0
        :param list? prices:    When specified, this function will use the values provided in the
                                list to perform calculations and ignore other parameters. defaults to None
        :param str? storage: Name of storage to use (optional, defaults to first)
        :returns: A tuple of numpy lists, each a list of BBand top, average, and bottom values
        """
        symbol, interval, ref, prices = self._default_param(symbol, interval, ref, prices, storage)

        if len(prices) < period:
            debugger.warning("Not enough data to calculate BBands, returning None")
            return None, None, None

        ohlc = pl.DataFrame(
            {
                "close": np.array(prices),
                "open": np.zeros(len(prices)),
                "high": np.zeros(len(prices)),
                "low": np.zeros(len(prices)),
            }
        )

        pandas_ohlc = ohlc.to_pandas()
        t, m, b = TA.BBANDS(pandas_ohlc, period=period, std_multiplier=dev, MA=TA.SMA(pandas_ohlc, period)).T.to_numpy()
        return t, m, b

    def crossover(self, prices_0: list[float], prices_1: list[float]) -> bool:
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

    async def get_asset_quantity(self, symbol: str | None = None, include_pending_buy=True, include_pending_sell=False,
                                broker: str | None = None) -> float:
        """Returns the quantity owned of a specified asset.

        :param str? symbol:  Symbol of asset. defaults to first symbol in watchlist
        :param bool? include_pending_buy:  Include pending buy orders in quantity. defaults to True
        :param bool? include_pending_sell:  Include pending sell orders in quantity. defaults to False
        :param str? broker: Name of broker to use (optional, defaults to first)
        :returns: Quantity of asset as float. 0 if quantity is not owned.
        :raises:
        """
        if symbol is None:
            symbol = self.watch_list[0]

        broker_service = self.get_broker_service(name=broker)
        if not broker_service:
            await self.discover_services()
            broker_service = self.get_broker_service(name=broker)

        if not broker_service:
            raise Exception("Broker service not available")

        positions = await broker_service.get_positions()
        for position in positions:
            if position.symbol == symbol:
                return position.quantity

        return 0.0

    async def get_asset_avg_cost(self, symbol: str | None = None,
                                broker: str | None = None) -> float:
        """Returns the average cost of a specified asset.

        :param str? symbol:  Symbol of asset. defaults to first symbol in watchlist
        :param str? broker: Name of broker to use (optional, defaults to first)
        :returns: Average cost of asset. Returns None if asset is not being tracked.
        :raises Exception: If symbol is not currently owned.
        """
        if symbol is None:
            symbol = self.watch_list[0]
        symbol = symbol.replace(" ", "")

        broker_service = self.get_broker_service(name=broker)
        if not broker_service:
            await self.discover_services()
            broker_service = self.get_broker_service(name=broker)

        if not broker_service:
            raise Exception("Broker service not available")

        positions = await broker_service.get_positions()
        for position in positions:
            if position.symbol == symbol:
                return position.avg_price

        raise Exception(f"{symbol} is not currently owned")

    async def get_asset_current_price(self, symbol: str | None = None,
                                     broker: str | None = None,
                                     storage: str | None = None) -> float:
        """Returns the current price of a specified asset.

        :param str? symbol: Symbol of asset. defaults to first symbol in watchlist
        :param str? broker: Name of broker to use (optional, defaults to first)
        :param str? storage: Name of storage to use (optional, defaults to first)
        :returns:           Price of asset.
        :raises Exception:  If symbol is not in the watchlist.
        """
        if symbol is None:
            symbol = self.watch_list[0]

        if symbol_type(symbol) != "OPTION":
            storage_service = self.get_central_storage_service(name=storage)
            if not storage_service:
                raise Exception("Central storage service not available")
            ticker_frame = storage_service.get_price_history(symbol, self.interval)
            return ticker_frame.get_column("close")[-1]

        # For options, first check positions
        broker_service = self.get_broker_service(name=broker)
        if not broker_service:
            await self.discover_services()
            broker_service = self.get_broker_service(name=broker)

        if not broker_service:
            raise Exception("Broker service not available")

        positions = await broker_service.get_positions()
        for pos in positions:
            if pos.symbol == symbol:
                return pos.current_price * 100  # Remove multiplier reference

        # If not in positions, get from market data
        option_data = await self.get_option_market_data(symbol)
        return option_data.price * 100

    def get_asset_price_list(self, symbol: str | None = None, interval: str | None = None, ref: str = "close",
                            storage: str | None = None) -> list[float] | None:
        """Returns a list of recent prices for an asset.

        This function is not compatible with options.

        :param str? symbol:     Symbol of stock or crypto asset. defaults to first symbol in watchlist
        :param str? interval:   Interval of data. defaults to the interval of the algorithm
        :param str? ref:        'close', 'open', 'high', or 'low'. defaults to 'close'
        :param str? storage: Name of storage to use (optional, defaults to first)
        :returns: List of prices
        """
        if symbol is None:
            symbol = self.watch_list[0]

        interval_enum = self.interval
        if interval is not None:
            interval_enum = interval_string_to_enum(interval)

        if symbol_type(symbol) != "OPTION":
            storage_service = self.get_central_storage_service(name=storage)
            if not storage_service:
                raise Exception("Central storage service not available")
            ticker_frame = storage_service.get_price_history(symbol, interval_enum)
            return list(ticker_frame.get_column(ref))

        debugger.warning("Price list not available for options")
        return None

    def get_asset_current_candle(self, symbol: str | None = None, interval=None,
                                storage: str | None = None) -> TickerFrame | None:
        """Returns the most recent candle as a TickerFrame

        This function is not compatible with options.

        :param str? symbol:  Symbol of stock or crypto asset. defaults to first symbol in watchlist
        :param str? storage: Name of storage to use (optional, defaults to first)
        :returns: Price of asset as a TickerFrame with the following columns:
            - timestamp
            - symbol
            - open
            - high
            - low
            - close
            - volume

        :raises Exception: If symbol is not in the watchlist.
        """
        if symbol is None:
            symbol = self.watch_list[0]

        interval_enum = self.interval
        if interval is not None:
            interval_enum = interval_string_to_enum(interval) if isinstance(interval, str) else interval

        if len(symbol) <= 6:  # Stock or crypto symbol
            storage_service = self.get_central_storage_service(name=storage)
            if not storage_service:
                raise Exception("Central storage service not available")
            ticker_frame = storage_service.get_price_history(symbol, interval_enum)
            # Get last row
            last_row = ticker_frame.tail(1)
            # Add timezone handling if stats available
            if self.stats:
                last_row_with_timezone = pandas_timestamp_to_local(last_row._df, self.stats.broker_timezone)
                return TickerFrame(last_row_with_timezone)
            return last_row

        debugger.warning("Candles not available for options")
        return None

    def get_asset_candle_list(self, symbol: str | None = None, interval=None,
                             storage: str | None = None) -> TickerFrame | None:
        """Returns the candles of an asset as a TickerFrame

        This function is not compatible with options.

        :param str? symbol:  Symbol of stock or crypto asset. defaults to first symbol in watchlist
        :param str? storage: Name of storage to use (optional, defaults to first)
        :returns: Prices of asset as a TickerFrame with the following columns:
            - timestamp
            - symbol
            - open
            - high
            - low
            - close
            - volume

        :raises Exception: If symbol is not in the watchlist.
        """
        if symbol is None:
            symbol = self.watch_list[0]

        interval_enum = self.interval
        if interval is not None:
            interval_enum = interval_string_to_enum(interval) if isinstance(interval, str) else interval

        storage_service = self.get_central_storage_service(name=storage)
        if not storage_service:
            raise Exception("Central storage service not available")

        ticker_frame = storage_service.get_price_history(symbol, interval_enum)
        # Add timezone handling if stats available
        if self.stats:
            df_with_timezone = pandas_timestamp_to_local(ticker_frame._df, self.stats.broker_timezone)
            return TickerFrame(df_with_timezone)
        return ticker_frame

    async def get_asset_profit_percent(self, symbol: str | None = None,
                                      broker: str | None = None) -> float | None:
        """Returns the return of a specified asset.

        :param str? symbol:  Symbol of stock, crypto, or option. Options should be in OCC format.
                        defaults to first symbol in watchlist
        :param str? broker: Name of broker to use (optional, defaults to first)
        :returns: Return of asset, expressed as a decimal.
        """
        if symbol is None:
            symbol = self.watch_list[0]

        broker_service = self.get_broker_service(name=broker)
        if not broker_service:
            await self.discover_services()
            broker_service = self.get_broker_service(name=broker)

        if not broker_service:
            raise Exception("Broker service not available")

        positions = await broker_service.get_positions()
        for position in positions:
            if position.symbol == symbol:
                return position.profit_percent

        debugger.warning(
            f"{symbol} is not currently owned. You either don't have it or it's still in the order queue."
        )
        return None

    async def get_asset_max_quantity(self, symbol: str | None = None) -> float:
        """Calculates the maximum quantity of an asset that can be bought given the current buying power.

        :param str? symbol:  Symbol of stock, crypto, or option. Options should be in OCC format.
            defaults to first symbol in watchlist
        :returns: Quantity that can be bought.
        """
        if symbol is None:
            symbol = self.watch_list[0]

        power = self.get_account_buying_power()
        price = await self.get_asset_current_price(symbol)

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
        if not self.account:
            return 0.0
        return self.account.buying_power

    def get_account_equity(self) -> float:
        """Returns the current equity.

        :returns: The current equity as a float.
        """
        if not self.account:
            return 0.0
        return self.account.equity

    async def get_account_stock_positions(self, broker: str | None = None) -> list[Position]:
        """Returns the current stock positions.

        :param str? broker: Name of broker to use (optional, defaults to first)
        :returns: A list of Position objects for all currently owned stocks.
        """
        broker_service = self.get_broker_service(name=broker)
        if not broker_service:
            await self.discover_services()
            broker_service = self.get_broker_service(name=broker)

        if not broker_service:
            raise Exception("Broker service not available")

        positions = await broker_service.get_positions()
        return [pos for pos in positions if symbol_type(pos.symbol) == "STOCK"]

    async def get_account_crypto_positions(self, broker: str | None = None) -> list[Position]:
        """Returns the current crypto positions.

        :param str? broker: Name of broker to use (optional, defaults to first)
        :returns: A list of Position objects for all currently owned crypto.
        """
        broker_service = self.get_broker_service(name=broker)
        if not broker_service:
            await self.discover_services()
            broker_service = self.get_broker_service(name=broker)

        if not broker_service:
            raise Exception("Broker service not available")

        positions = await broker_service.get_positions()
        return [pos for pos in positions if symbol_type(pos.symbol) == "CRYPTO"]

    async def get_account_option_positions(self, broker: str | None = None) -> list[Position]:
        """Returns the current option positions.

        :param str? broker: Name of broker to use (optional, defaults to first)
        :returns: A list of Position objects for all currently owned options.
        """
        broker_service = self.get_broker_service(name=broker)
        if not broker_service:
            await self.discover_services()
            broker_service = self.get_broker_service(name=broker)

        if not broker_service:
            raise Exception("Broker service not available")

        positions = await broker_service.get_positions()
        return [pos for pos in positions if symbol_type(pos.symbol) == "OPTION"]

    def get_watchlist(self) -> list[str]:
        """Returns the current watchlist."""
        return self.watch_list

    def get_stock_watchlist(self) -> list[str]:
        """Returns the current watchlist."""
        return [s for s in self.watch_list if symbol_type(s) == "STOCK"]

    def get_crypto_watchlist(self) -> list[str]:
        """Returns the current watchlist."""
        return [s for s in self.watch_list if symbol_type(s) == "CRYPTO"]

    def get_time(self) -> dt.time:
        """Returns the current hour and minute.

        This returns the current time, which is different from the timestamp
        of stock prices. For example, if you are running an algorithm every 5 minutes,
        at 11:30am you will get price data with a timestamp of 11:25am. This function will return
        11:30am.

        :returns: The current time as a datetime object
        """
        return self.get_datetime().time()

    def get_date(self) -> dt.date:
        """Returns the current date.

        :returns: The current date as a datetime object
        """
        return self.get_datetime().date()

    def get_datetime(self) -> dt.datetime:
        """Returns the current date and time.

        The returned datetime object is offset-naive, adjusted to the local timezone.

        :returns: The current date and time as a datetime object
        """
        if self.stats and self.stats.utc_timestamp and self.stats.broker_timezone:
            return datetime_utc_to_local(self.stats.utc_timestamp, self.stats.broker_timezone)
        else:
            # Fallback to current UTC time if stats not available
            return dt.datetime.utcnow()

    async def check_broker_capabilities(self, symbols: list[str] | None = None,
                                       intervals: list[Interval] | None = None) -> dict[str, bool]:
        """
        Check if the current broker service supports the required symbols and intervals.

        :symbols: List of symbols to check (defaults to watchlist)
        :intervals: List of intervals to check (defaults to algorithm intervals)
        :returns: Dictionary indicating support status for each requirement
        """
        if not self.broker_service:
            await self.discover_services()

        symbols = symbols or self.watch_list
        intervals = intervals or self.aggregations

        results = {}

        if self.broker_service:
            # Check broker capabilities
            try:
                capabilities = self.broker_service.get_all_broker_capabilities()
                results['brokers_available'] = len(capabilities) > 0

                # Check symbol and interval support for default broker
                for symbol in symbols:
                    for interval in intervals:
                        key = f"{symbol}_{interval}"
                        results[key] = self.broker_service.supports_symbol_and_interval(
                            symbol, str(interval), "default"
                        )

            except Exception as e:
                results['error'] = str(e)
                results['brokers_available'] = False
        else:
            results['brokers_available'] = False

        return results

    def get_broker_service(self, name: str | None = None) -> "BrokerService | None":
        """
        Get a specific broker service by name.

        :name: Name of the broker service (optional, defaults to first)
        :returns: BrokerService instance or None if not found
        """
        if name is not None:
            # Search by name
            for service in self.broker_services:
                if hasattr(service, 'service_name') and service.service_name == name:
                    return service
            return None

        # Get first service by default
        if len(self.broker_services) > 0:
            return self.broker_services[0]
        return None

    def get_central_storage_service(self, name: str | None = None) -> "CentralStorageService | None":
        """
        Get a specific central storage service by name.

        :name: Name of the storage service (optional, defaults to first)
        :returns: CentralStorageService instance or None if not found
        """
        if name is not None:
            # Search by name
            for service in self.central_storage_services:
                if hasattr(service, 'service_name') and service.service_name == name:
                    return service
            return None

        # Get first service by default
        if len(self.central_storage_services) > 0:
            return self.central_storage_services[0]
        return None

    # def is_day_trade(self, symbol=None, action="buy") -> bool:
    #     """
    #     Checks if performing a buy or sell will be considered day trading.
    #     """

    #     # Get transaction history
    #     history = self.trader.load_daytrade()
    #     # False if less than 3 transactions
    #     if len(history) < 3:
    #         return False

    # Used for testing
    def add_symbol(self, symbol: str) -> None:
        """Adds a symbol to the watchlist.

        :param str symbol: Symbol of stock or crypto asset.
        """
        self.watch_list.append(symbol)

# mypy: disable-error-code="attr-defined"
# Service method calls are properly typed at runtime through service discovery
