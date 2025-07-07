# Standard library imports
import asyncio
import datetime as dt
import threading
import time
from abc import abstractmethod
from os.path import exists
from typing import Any, Callable, Dict

# Third-party imports
import pandas as pd
import polars as pl
import yaml

# Local imports
from harvest.definitions import (
    Account,
    AssetType,
    BrokerCapabilities,
    ChainData,
    ChainInfo,
    OptionData,
    Order,
    OrderList,
    OrderSide,
    OrderTimeInForce,
    Positions,
    RuntimeData,
    TickerCandle,
    TickerFrame,
)
from harvest.enum import Interval, IntervalUnit
from harvest.util.helper import (
    check_interval,
    data_to_occ,
    debugger,
    expand_interval,
    interval_to_timedelta,
    occ_to_data,
    symbol_type,
    utc_current_time,
)
from harvest.events.event_bus import EventBus
from harvest.events.events import PriceUpdateEvent


class Broker:
    """
    The Broker class is used to communicate with various API endpoints of the respective broker.

    It is used to perform operations like fetching historical data and placing orders,
    as well as generating events for price updates and order statuses.

    Note that some brokers may not support all features, such as options trading or crypto trading.
    Furthermore, some brokers are specialized for specific role, such as data retrieval or order placement.
    For example, PaperBroker is specialized for order placement and does not support data retrieval.
    """

    # List of supported intervals
    # interval_list = [
    #     Interval.MIN_1,
    #     Interval.MIN_5,
    #     Interval.MIN_15,
    #     Interval.MIN_30,
    #     Interval.HR_1,
    #     Interval.DAY_1,
    # ]
    interval_list: list[Interval]
    # Name of the exchange this API trades on
    exchange: str
    # List of attributes that are required to be in the secret file, e.g. 'api_key'
    req_keys: list[str]

    def __init__(self, secret_path: str | None = None) -> None:
        """
        Performs initializations of the class, such as setting the
        timestamp and loading credentials.

        All subclass implementations should call this __init__ method
        using `super().__init__(path)`.

        :path: path to the YAML file containing credentials to communicate with the API.
            If not specified, defaults to './secret.yaml'
        """
        if secret_path is None:
            secret_path = "./secret.yaml"

        self.secret_path = secret_path
        self.watch_dict: dict[Interval, list[str]] = {} # Maps intervals to lists of symbols to watch
        self.event_bus: EventBus | None = None   # Event bus for publishing price updates

    def setup(self, runtime_data: RuntimeData) -> None:
        """
        This function is called right before the algorithm begins,
        and initializes several runtime parameters like
        the symbols to watch and what interval data is needed.

        :stats: The Stats object that contains the watchlist and other configurations.
        :account: The Account object that contains the user's account information.
        :broker_hub_cb: The callback function that the broker calls every time it fetches new data.
        """

        config = {}

        # Check if file exists. If not, create a secret file
        if not exists(self.secret_path):
            config = self.create_secret()
        else:
            with open(self.secret_path, "r") as stream:
                config = yaml.safe_load(stream)
                # Check if the file contains all the required parameters
                if any(key not in config for key in self.req_keys):
                    config.update(self.create_secret())

        with open(self.secret_path, "w") as f:
            yaml.dump(config, f)

        self.config = config
        self.stats = runtime_data
        # debugger.debug(f"Poll Interval: {interval_enum_to_string(self.poll_interval)}")
        debugger.debug(f"{type(self).__name__} setup finished")

    def set_event_bus(self, event_bus: EventBus) -> None:
        """
        Set the event bus for publishing price update events.

        :event_bus: The event bus instance to use for publishing events
        """
        self.event_bus = event_bus

    def _publish_ticker_candle(self, symbol: str, price_data: TickerCandle, interval: Interval) -> None:
        """
        Publish a price update event to the event bus.

        Publishes a single ticker update event with format:
        `price_update:[broker_name]:[interval]:[ticker]`

        :symbol: The symbol that was updated
        :price_data: The new price data as a TickerCandle
        :interval: The interval this data represents
        """
        # Convert TickerCandle to TickerFrame for consistency
        df = pl.DataFrame({
            "timestamp": [price_data.timestamp],
            "symbol": [price_data.symbol],
            "open": [price_data.open],
            "high": [price_data.high],
            "low": [price_data.low],
            "close": [price_data.close],
            "volume": [price_data.volume],
        })
        ticker_frame = TickerFrame(df)

        # Create the event with broker and interval information
        event = PriceUpdateEvent(
            symbol=symbol,
            price_data=ticker_frame,
            timestamp=price_data.timestamp,
            interval=interval,
            broker_id=self.__class__.__name__,
            exchange=self.exchange
        )

        # Publish single ticker event if available
        if self.event_bus:
            broker_name = self.__class__.__name__
            event_name = f"price_update:{broker_name}:{interval.value}:{symbol}"
            self.event_bus.publish(event_name, event.__dict__)

    def _publish_all_ticker_candle(self, interval: Interval, all_data: dict[str, TickerCandle]) -> None:
        """
        Publish an event when all tickers for an interval are ready.

        Event format: `price_update:[broker_name]:[interval]:all`

        :interval: The interval for which all data is ready
        :all_data: Dictionary mapping symbols to their ticker data
        """
        if not self.event_bus:
            return

        broker_name = self.__class__.__name__

        # Create combined event data
        combined_event = {
            "interval": interval,
            "broker_id": broker_name,
            "exchange": self.exchange,
            "timestamp": self.stats.utc_timestamp if self.stats else None,
            "symbols": list(all_data.keys()),
            "ticker_data": {}
        }

        # Convert all ticker candles to ticker frames
        for symbol, candle in all_data.items():
            df = pl.DataFrame({
                "timestamp": [candle.timestamp],
                "symbol": [candle.symbol],
                "open": [candle.open],
                "high": [candle.high],
                "low": [candle.low],
                "close": [candle.close],
                "volume": [candle.volume],
            })
            combined_event["ticker_data"][symbol] = TickerFrame(df).__dict__

        event_name = f"price_update:{broker_name}:{interval.value}:all"
        self.event_bus.publish(event_name, combined_event)

    def _publish_periodic_event(self, interval: Interval) -> None:
        """
        Publish a periodic event regardless of ticker data availability.

        Event format: `price_update:[broker_name]:[interval]`

        :interval: The interval for this periodic event
        """
        if not self.event_bus:
            return

        broker_name = self.__class__.__name__

        periodic_event = {
            "interval": interval,
            "broker_id": broker_name,
            "exchange": self.exchange,
            "timestamp": self.stats.utc_timestamp if self.stats else None,
            "event_type": "periodic"
        }

        event_name = f"price_update:{broker_name}:{interval.value}"
        self.event_bus.publish(event_name, periodic_event)


    def continue_polling(self) -> bool:
        return True

    def start(
        self,
        watch_dict: dict[Interval, list[str]],
    ) -> None:
        """
        Tells broker to start fetching data at the specified intervals.
        """
        self.watch_dict = watch_dict
        debugger.debug(f"{type(self).__name__} started with event-driven approach...")

        # Start the polling system in its own thread
        self._start_polling_system()

    def _start_polling_system(self) -> None:
        """
        Start the polling system in its own thread.

        This method runs a single thread that tracks time for both price polling
        and periodic events, calling the appropriate functions at their specified intervals.
        """
        # Find the lowest interval in the watch_dict for polling frequency
        lowest_interval = min(self.watch_dict.keys())
        self.polling_interval = lowest_interval

        # Start single polling thread
        self._polling_thread = threading.Thread(
            target=self._polling_loop,
            args=(lowest_interval,),
            daemon=True
        )
        self._polling_thread.start()

    def _polling_loop(self, poll_interval: Interval) -> None:
        """
        Main polling loop that handles both price data events and periodic events.

        This method tracks time and calls the appropriate functions at the correct intervals.

        Args:
            poll_interval: Interval enum representing the polling frequency
        """
        # Define the polling tasks for this broker type using Interval enums
        polling_tasks = [
            {
                'function': self._poll_and_publish_price_events,
                'interval': poll_interval,
            },
            {
                'function': self._publish_periodic_events,
                'interval': Interval.SEC_15,  # Check every 15 seconds for periodic events
            }
        ]

        self._common_polling_loop(polling_tasks)

    def _common_polling_loop(self, polling_tasks: list[dict]) -> None:
        """
        Common polling loop that executes tasks at time-aligned intervals.

        This method provides a reusable polling framework that fires events at exact
        time boundaries (e.g., :00, :15, :30, :45 for 15-minute intervals) to ensure
        accurate and synchronized timing across all brokers.

        All time operations use UTC timezone for consistency.

        Args:
            polling_tasks: List of dictionaries, each containing:
                - 'function': The function to call
                - 'interval': Interval enum representing how often to call it
                - 'next_fire_time': When this task should next execute (UTC timestamp)
        """
        # Initialize next fire times for all tasks based on time alignment (UTC)
        current_time = utc_current_time().timestamp()
        for task in polling_tasks:
            task['next_fire_time'] = self._calculate_next_aligned_time(current_time, task['interval'])

        while self.continue_polling():
            current_time = utc_current_time().timestamp()

            # Find the earliest next fire time among all tasks
            next_fire_time = min(task['next_fire_time'] for task in polling_tasks)

            # If it's time to fire the earliest task(s)
            if current_time >= next_fire_time:
                # Execute all tasks that are ready to fire
                for task in polling_tasks:
                    if current_time >= task['next_fire_time']:
                        task['function']()
                        # Recalculate next fire time from current actual time to prevent drift
                        task['next_fire_time'] = self._calculate_next_aligned_time(current_time, task['interval'])

                # Short sleep to prevent excessive CPU usage when firing multiple tasks
                time.sleep(0.01)
            else:
                # Calculate how long to sleep until the next event
                sleep_duration = min(next_fire_time - current_time, 0.1)  # Cap at 100ms
                if sleep_duration > 0:
                    time.sleep(sleep_duration)

    def _calculate_next_aligned_time(self, current_time: float, interval: Interval) -> float:
        """
        Calculate the next time-aligned firing time for a given Interval enum.

        This ensures events fire at exact time boundaries in UTC:
        - 15-second intervals: fire at :00, :15, :30, :45
        - 1-minute intervals: fire at :00 of each minute
        - 5-minute intervals: fire at :00, :05, :10, :15, etc.
        - 1-hour intervals: fire at :00 of each hour
        - 1-day intervals: fire at midnight UTC

        All calculations are performed in UTC timezone to ensure consistency
        across different system timezones.

        Args:
            current_time: Current UTC timestamp (seconds since Unix epoch)
            interval: Interval enum representing the interval

        Returns:
            UTC timestamp for the next aligned firing time
        """
        import math

        # Handle different interval units directly using UTC-based calculations
        if interval.unit == "SEC":
            # For second intervals, align within the current minute
            minute_start = math.floor(current_time / 60) * 60
            elapsed_in_minute = current_time - minute_start
            intervals_passed = math.floor(elapsed_in_minute / interval.interval_value)
            next_time = minute_start + (intervals_passed + 1) * interval.interval_value

            # If we've gone past this minute, move to the next minute
            if next_time >= minute_start + 60:
                next_time = minute_start + 60

        elif interval.unit == "MIN":
            if interval.interval_value == 1:
                # Align to the next minute boundary
                next_time = math.ceil(current_time / 60) * 60
            else:
                # Align to interval boundaries within the hour
                hour_start = math.floor(current_time / 3600) * 3600
                elapsed_in_hour = current_time - hour_start
                minute_interval = interval.interval_value * 60
                intervals_passed = math.floor(elapsed_in_hour / minute_interval)
                next_time = hour_start + (intervals_passed + 1) * minute_interval

        elif interval.unit == "HR":
            if interval.interval_value == 1:
                # Align to the next hour boundary
                next_time = math.ceil(current_time / 3600) * 3600
            else:
                # Align to interval boundaries within the day
                day_start = math.floor(current_time / 86400) * 86400
                elapsed_in_day = current_time - day_start
                hour_interval = interval.interval_value * 3600
                intervals_passed = math.floor(elapsed_in_day / hour_interval)
                next_time = day_start + (intervals_passed + 1) * hour_interval

        elif interval.unit == "DAY":
            # Align to day boundaries (midnight UTC)
            if interval.interval_value == 1:
                next_time = math.ceil(current_time / 86400) * 86400
            else:
                # Multi-day intervals align to interval boundaries from Unix epoch
                day_interval = interval.interval_value * 86400
                intervals_passed = math.floor(current_time / day_interval)
                next_time = (intervals_passed + 1) * day_interval

        else:
            raise ValueError(f"Unsupported interval unit: {interval.unit}")

        return next_time



    def _poll_and_publish_price_events(self) -> None:
        """
        Poll for new price data and publish price update events.

        This method handles:
        1. Individual ticker updates as they become available
        2. "All tickers ready" events when all tickers for an interval are complete

        Includes retry logic to ensure we get the latest expected timestamps.
        """
        df_dict = {}
        retry_queue = []
        interval_completion = {}  # Track completed tickers per interval
        interval_expected = {}    # Track expected tickers per interval

        # Initialize tracking for each interval
        for interval, symbols in self.watch_dict.items():
            if check_interval(self.stats.utc_timestamp, interval):
                interval_expected[interval] = set(symbols)
                interval_completion[interval] = {}
                df_dict[interval] = {}

        # First pass: collect data and identify items that need retry
        for interval, symbols in self.watch_dict.items():
            interval_delta = interval_to_timedelta(interval)
            if not check_interval(self.stats.utc_timestamp, interval):
                continue

            for symbol in symbols:
                try:
                    candle = self.fetch_latest_price(symbol, interval)
                    if self.check_if_latest_candle(interval, candle):
                        # Publish individual ticker event immediately
                        self._publish_ticker_candle(symbol, candle, interval)
                        df_dict[interval][symbol] = candle
                        interval_completion[interval][symbol] = candle
                    else:
                        # Add to retry queue if timestamp is not the expected latest
                        retry_queue.append((symbol, interval, self.stats.utc_timestamp - interval_delta))
                except Exception as e:
                    debugger.error(f"Error fetching price for {symbol}: {e}")
                    # Add failed fetch to retry queue
                    retry_queue.append((symbol, interval, self.stats.utc_timestamp - interval_delta))

        # Retry logic: attempt to get correct timestamps up to 5 times
        retries = 5
        while retry_queue and retries > 0:
            symbol, interval, timestamp = retry_queue.pop(0)
            try:
                candle = self.fetch_latest_price(symbol, interval)
                if self.check_if_latest_candle(interval, candle):
                    # Publish individual ticker event and track completion
                    self._publish_ticker_candle(symbol, candle, interval)
                    if interval not in df_dict:
                        df_dict[interval] = {}
                    df_dict[interval][symbol] = candle
                    if interval not in interval_completion:
                        interval_completion[interval] = {}
                    interval_completion[interval][symbol] = candle
                else:
                    # Re-add to retry queue if still not the correct timestamp
                    retry_queue.append((symbol, interval, timestamp))
                    retries -= 1
            except Exception as e:
                debugger.error(f"Error in retry for {symbol}: {e}")
                retry_queue.append((symbol, interval, timestamp))
                retries -= 1

        # Check for completed intervals and publish "all tickers ready" events
        for interval in interval_expected:
            if interval in interval_completion:
                completed_symbols = set(interval_completion[interval].keys())
                expected_symbols = interval_expected[interval]

                # If all expected symbols are completed, publish "all" event
                if completed_symbols == expected_symbols:
                    self._publish_all_ticker_candle(interval, interval_completion[interval])

    def _publish_periodic_events(self) -> None:
        """
        Publish periodic events for all active intervals.

        This method publishes periodic events regardless of ticker data availability.
        """
        for interval in self.watch_dict.keys():
            if check_interval(self.stats.utc_timestamp, interval):
                self._publish_periodic_event(interval)


    @classmethod
    def get_single_ticker_event_name(cls, interval: Interval, symbol: str) -> str:
        """
        Get the event name for single ticker updates.
        Format: `price_update:[broker_name]:[interval]:[ticker]`

        :interval: The interval to subscribe to
        :symbol: The specific symbol to subscribe to
        :returns: Event name string
        """
        return f"price_update:{cls.__name__}:{interval.value}:{symbol}"

    @classmethod
    def get_all_tickers_event_name(cls, interval: Interval) -> str:
        """
        Get the event name for when all tickers are ready.
        Format: `price_update:[broker_name]:[interval]:all`

        :interval: The interval to subscribe to
        :returns: Event name string
        """
        return f"price_update:{cls.__name__}:{interval.value}:all"

    @classmethod
    def get_periodic_event_name(cls, interval: Interval) -> str:
        """
        Get the event name for periodic events.
        Format: `price_update:[broker_name]:[interval]`

        :interval: The interval to subscribe to
        :returns: Event name string
        """
        return f"price_update:{cls.__name__}:{interval.value}"

    def check_if_latest_candle(self, interval: Interval, candle: TickerCandle) -> bool:
        """
        Checks if the candle is the latest candle for the given interval for the current time.
        This function only returns true for full candles, not partial candles.
        For example, if the current time is 10:23 AM, interval is 5 minute, and the candle timestamp is 10:00 AM,
        this function will return false since the candle is not a full candle.
        """
        timestamp = candle.timestamp
        return timestamp == self.stats.utc_timestamp - interval_to_timedelta(interval)

    def exit(self) -> None:
        """
        Exit the broker.
        """
        debugger.debug(f"{type(self).__name__} exited")

    @abstractmethod
    def create_secret(self) -> Dict[str, str]:
        """
        This method is called when the yaml file with credentials is not found.
        Each broker should implement a wizard to instruct users on how to create the necessary credentials.
        """
        debugger.warning("Assuming API does not need account information.")

    @abstractmethod
    def refresh_cred(self) -> None:
        """
        Most API endpoints, for security reasons, require a refresh of the access token
        every now and then. This method should perform a refresh of the access token.
        """
        debugger.info(f"Refreshing credentials for {type(self).__name__}.")

    @abstractmethod
    def get_current_time(self) -> dt.datetime:
        """
        Returns the current time in UTC timezone, accurate to the minute.
        """
        return utc_current_time()

    # ------------- Data fetching methods ------------- #

    @abstractmethod
    def fetch_price_history(
        self,
        symbol: str,
        interval: Interval,
        start: dt.datetime | None = None,
        end: dt.datetime | None = None,
    ) -> TickerFrame:
        """
        Fetches historical price data for the specified asset and period
        using the API. The first row is the earliest entry and the last
        row is the latest entry.

        :param symbol: The stock/crypto to get data for. Note options are not supported.
        :param interval: The interval of requested historical data.
        :param start: The starting date of the period, inclusive.
        :param end: The ending date of the period, inclusive.
        :returns: A pandas dataframe, same format as self.step()
        """
        pass

    @abstractmethod
    def fetch_latest_price(self, symbol: str, interval: Interval) -> TickerCandle:
        """
        Fetches the latest price of the specified asset.

        :param symbol: The stock/crypto to get data for. Note options are not supported.
        """
        pass

    @abstractmethod
    def fetch_chain_info(self, symbol: str) -> ChainInfo:
        """
        Returns information about the symbol's options

        :param symbol: Stock symbol. Cannot use crypto.
        :returns: A dict with the following keys and values:
            - chain_id: ID of the option chain
            - exp_dates: List of expiration dates as datetime objects
            - multiplier: Multiplier of the option, usually 100
        """
        pass

    @abstractmethod
    def fetch_chain_data(self, symbol: str, date: dt.datetime) -> ChainData:
        """
        Returns the option chain for the specified symbol.

        :param symbol: Stock symbol. Cannot use crypto.
        :param date: Expiration date.
        :returns: A dataframe in the following format:

                    exp_date strike  type
            OCC
            ---     ---      ---     ---
        exp_date should be a timezone-aware datetime object localized to UTC
        """
        pass

    @abstractmethod
    def fetch_option_market_data(self, symbol: str) -> OptionData:
        """
        Retrieves data of specified option.

        :param symbol:    OCC symbol of option
        :returns:   A dictionary:
            - price: price of option
            - ask: ask price
            - bid: bid price
        """
        pass

    @abstractmethod
    def fetch_market_hours(self, date: dt.date) -> Dict[str, Any]:
        """
        Returns the market hours for a given day.
        Hours are based on the exchange specified in the class's 'exchange' attribute.

        :returns: A dictionary with the following keys and values:
            - is_open: Boolean indicating whether the market is open or closed
            - open_at: Time the market opens in UTC timezone.
            - close_at: Time the market closes in UTC timezone.
        """
        pass

    # ------------- Account information methods ------------- #

    @abstractmethod
    def fetch_stock_positions(self) -> Positions:
        """
        Returns all current stock positions

        :returns: A list of dictionaries with the following keys and values:
            - symbol: Ticker symbol of the stock
            - avg_price: The average price the stock was bought at
            - quantity: Quantity owned
        """
        pass

    @abstractmethod
    def fetch_option_positions(self) -> Positions:
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
        pass

    @abstractmethod
    def fetch_crypto_positions(self) -> Positions:
        """
        Returns all current crypto positions

        :returns: A list of dictionaries with the following keys and values:
            - symbol: Ticker symbol for the crypto, prepended with an '@'
            - avg_price: The average price the crypto was bought at
            - quantity: Quantity owned
        """
        pass

    @abstractmethod
    def fetch_account(self) -> Account:
        """
        Returns current account information from the brokerage.

        :returns: An Account object
        """
        pass

    @abstractmethod
    def fetch_stock_order_status(self, id) -> Order:
        """
        Returns the status of a stock order with the given id.

        :id: ID of the stock order

        :returns: A dictionary with the following keys and values:
            - type: 'STOCK'
            - order_id: ID of the order
            - quantity: Quantity ordered
            - filled_quantity: Quantity filled so far
            - side: 'buy' or 'sell'
            - time_in_force: Time the order is in force
            - status: Status of the order
            - filled_time: Time the order was filled
            - filled_price: Price the order was filled at
        """
        pass

    @abstractmethod
    def fetch_option_order_status(self, id) -> Order:
        """
        Returns the status of a option order with the given id.

        :id: ID of the option order

        :returns: A dictionary with the following keys and values:
            - type: 'OPTION'
            - order_id: ID of the order
            - quantity: Quantity ordered
            - filled_quantity: Quantity filled so far
            - side: 'buy' or 'sell'
            - time_in_force: Time the order is in force
            - status: Status of the order
            - filled_time: Time the order was filled
            - filled_price: Price the order was filled at
        """
        pass

    @abstractmethod
    def fetch_crypto_order_status(self, id) -> Order:
        """
        Returns the status of a crypto order with the given id.

        :id: ID of the crypto order

        :returns: A dictionary with the following keys and values:
            - type: 'CRYPTO'
            - order_id: ID of the order
            - quantity: Quantity ordered
            - filled_quantity: Quantity filled so far
            - side: 'buy' or 'sell'
            - time_in_force: Time the order is in force
            - status: Status of the order
            - filled_time: Time the order was filled
            - filled_price: Price the order was filled at
        """
        pass

    @abstractmethod
    def fetch_order_queue(self) -> OrderList:
        """
        Returns all current pending orders

        returns: A list of dictionaries with the following keys and values:
            For stocks and crypto:
                - order_type: "STOCK" or "CRYPTO"
                - symbol: Symbol of asset
                - quantity: Quantity ordered
                - time_in_force: Time in force
                - side: 'buy' or 'sell'
                - order_id: ID of order
                - status: Status of the order
                - filled_qty: Quantity filled
                - filled_time: Time the order was filled
                - filled_price: Price the order was filled at
            For options:
                - order_type: "OPTION",
                - symbol: OCC symbol of option
                - base_symbol:
                - quantity: Quantity ordered
                - order_id: ID of order
                - time_in_force: Time in force
                - side: 'buy' or 'sell'
                - status: Status of the order
                - filled_qty: Quantity filled
                - filled_time: Time the order was filled
                - filled_price: Price the order was filled at

        """
        pass

    # --------------- Methods for Trading --------------- #

    @abstractmethod
    def order_stock_limit(
        self,
        side: OrderSide,
        symbol: str,
        quantity: float,
        limit_price: float,
        in_force: OrderTimeInForce = OrderTimeInForce.GTC,
        extended: bool = False,
    ) -> Order:
        """
        Places a limit order.

        :symbol:    symbol of stock
        :side:      'buy' or 'sell'
        :quantity:  quantity to buy or sell
        :limit_price:   limit price
        :in_force:  'gtc' by default
        :extended:  'False' by default

        :returns: A Order object
        """
        pass

    @abstractmethod
    def order_crypto_limit(
        self,
        side: str,
        symbol: str,
        quantity: float,
        limit_price: float,
        in_force: str = "gtc",
        extended: bool = False,
    ) -> Order:
        """
        Places a limit order.

        :symbol:    symbol of crypto
        :side:      'buy' or 'sell'
        :quantity:  quantity to buy or sell
        :limit_price:   limit price
        :in_force:  'gtc' by default
        :extended:  'False' by default

        :returns: A Order object
        """
        pass

    @abstractmethod
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
    ) -> Order:
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

        :returns: A Order object
        """
        pass

    @abstractmethod
    def cancel_stock_order(self, order_id) -> None:
        pass

    @abstractmethod
    def cancel_crypto_order(self, order_id) -> None:
        pass

    @abstractmethod
    def cancel_option_order(self, order_id) -> None:
        pass

    # -------------- Built-in methods -------------- #
    # These do not need to be re-implemented in a subclass

    def buy(
        self,
        symbol: str,
        quantity: int,
        limit_price: float,
        in_force: str = "gtc",
        extended: bool = False,
    ) -> Order:
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
            return self.order_stock_limit(OrderSide.BUY, symbol, quantity, limit_price, OrderTimeInForce.GTC if in_force == "gtc" else OrderTimeInForce.GTD, extended)
        elif typ == "CRYPTO":
            return self.order_crypto_limit("buy", symbol[1:], quantity, limit_price, in_force, extended)
        elif typ == "OPTION":
            sym, exp_date, option_type, strike = occ_to_data(symbol)
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
            raise Exception(f"Invalid asset type for {symbol}")

    def sell(
        self,
        symbol: str,
        quantity: int = 0,
        limit_price: float = 0.0,
        in_force: str = "gtc",
        extended: bool = False,
    ) -> Order:
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
            return self.order_stock_limit(OrderSide.SELL, symbol, quantity, limit_price, OrderTimeInForce.GTC if in_force == "gtc" else OrderTimeInForce.GTD, extended)
        elif typ == "CRYPTO":
            return self.order_crypto_limit("sell", symbol[1:], quantity, limit_price, in_force, extended)
        elif typ == "OPTION":
            sym, exp_date, option_type, strike = occ_to_data(symbol)
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
            raise Exception(f"Invalid asset type for {symbol}")

    def get_broker_capabilities(self) -> BrokerCapabilities:
        """
        Get broker capabilities including supported intervals and tickers.

        :returns: BrokerCapabilities object containing broker capabilities
        """
        return BrokerCapabilities(
            broker_id=self.__class__.__name__,
            exchange=self.exchange,
            supported_intervals_tickers=self._get_supported_intervals_tickers(),
            supported_asset_types=self._get_supported_asset_types(),
            features=self._get_broker_features()
        )

    def _get_supported_intervals_tickers(self) -> dict[Interval, list[str]]:
        """
        Get mapping of supported intervals to supported tickers.

        Default implementation returns all intervals with empty ticker lists.
        Subclasses should override this to provide actual ticker support.
        """
        # Default implementation - subclasses should override with actual ticker support
        return {interval: [] for interval in self.interval_list}

    def _get_supported_asset_types(self) -> list[AssetType]:
        """Get list of supported asset types (stocks, crypto, options)"""
        # Default implementation - subclasses should override if they have limitations
        return [AssetType.STOCK, AssetType.CRYPTO, AssetType.OPTION]

    def _get_broker_features(self) -> list[str]:
        """Get list of broker-specific features"""
        # Default implementation - subclasses should override
        return ["real_time_data", "historical_data", "order_placement"]

    def supports_interval(self, interval: Interval) -> bool:
        """Check if broker supports the specified interval"""
        return interval in self.interval_list

    def supports_symbol(self, symbol: str) -> bool:
        """
        Check if broker supports trading the specified symbol.
        Default implementation always returns True - subclasses should override.
        """
        # Default implementation - real brokers should implement symbol validation
        return True




class StreamBroker(Broker):
    """
    Class for brokers that support streaming APIs.

    Whenever possible, it is preferred to use a streaming API over polling as it helps offload
    interval handling to the server. This class provides a framework for handling asynchronous
    data streams while maintaining compatibility with the event-driven broker architecture.

    The StreamBroker follows this design pattern:
    1. When streaming data arrives, it immediately publishes individual ticker events
    2. Data is cached by interval until either:
       - All expected tickers for that interval arrive
       - A configurable timeout expires
    3. When the cache is flushed, it publishes "all tickers ready" events
    4. Periodic events are also published to maintain compatibility

    """

    def __init__(self, path: str | None = None) -> None:
        """
        Initialize the streaming broker.

        Streaming APIs often return data asynchronously, so this class additionally defines a lock to
        prevent race conditions in case different data arrives close to each other.

        Args:
            path: Optional path to configuration file.
        """
        super().__init__(path)

        # Lock for streams that receive data asynchronously
        self._stream_lock = threading.Lock()
        self._interval_cache: dict[Interval, dict[str, TickerCandle]] = {}
        self._expected_tickers: dict[Interval, set[str]] = {}
        self._timeout_timers: dict[Interval, threading.Timer] = {}
        self._timeout_duration: float = 1.0
        self._is_streaming: bool = False

    def start(
        self,
        watch_dict: dict[Interval, list[str]],
    ) -> None:
        """
        Start the streaming broker by connecting to the streaming API.

        This method connects to a streaming API and sets up subscriptions for the
        specified intervals and symbols. Unlike the polling approach, this method
        establishes persistent connections and handles data as it arrives.

        Args:
            watch_dict: Dictionary mapping intervals to lists of symbols to watch
            step_callback: Optional callback function for backward compatibility
        """
        self.watch_dict = watch_dict

        # Initialize expected tickers for each interval
        for interval, tickers in watch_dict.items():
            self._expected_tickers[interval] = set(tickers)
            self._interval_cache[interval] = {}

        debugger.debug(f"{type(self).__name__} starting streaming API connection...")

        # Initialize streaming connection (placeholder - subclasses will implement)
        self._initialize_stream_connection()
        # Set up subscriptions for all tickers and intervals (placeholder)
        self._setup_subscriptions()

        # Mark as streaming
        self._is_streaming = True

        debugger.debug(f"{type(self).__name__} streaming started successfully")

        # Start the polling system (will use overridden _polling_loop for periodic events only)
        self._start_polling_system()

        # Start the streaming connection in its own thread
        self._streaming_task = threading.Thread(target=self.stream, daemon=True)
        self._streaming_task.start()

    def stream(self) -> None:
        """
        Abstract method to run the streaming connection.

        This method should be implemented by subclasses to maintain the actual
        connection to the streaming API and handle incoming data.
        """
        pass


    def stop_streaming(self) -> None:
        """
        Stop the streaming broker and cleanup resources.

        This method stops streaming, cancels all timers, and cleans up subscriptions.
        """
        debugger.debug(f"{type(self).__name__} stopping streaming...")
        self._is_streaming = False

        # Cancel all timeout timers
        with self._stream_lock:
            for timer in self._timeout_timers.values():
                if timer:
                    timer.cancel()
            self._timeout_timers.clear()

        # Cleanup subscriptions
        self._cleanup_subscriptions()

    def on_streaming_data(self, ticker: str, candle: TickerCandle, interval: Interval) -> None:
        """
        Handle incoming streaming data for a specific ticker.

        This method should be called by subclasses when new data arrives from the streaming API.
        It immediately publishes the price update event and caches the data for "all tickers ready" events.

        Args:
            ticker: The ticker symbol for the data
            candle: The ticker candle data
            interval: The interval this data represents
        """
        # Immediately publish individual ticker update event
        self._publish_ticker_candle(ticker, candle, interval)

        # Cache the data and check if we should flush
        with self._stream_lock:
            if interval not in self._interval_cache:
                self._interval_cache[interval] = {}

            self._interval_cache[interval][ticker] = candle

            # Check if we have all expected tickers for this interval
            if interval in self._expected_tickers:
                cached_tickers = set(self._interval_cache[interval].keys())
                expected_tickers = self._expected_tickers[interval]

                if cached_tickers >= expected_tickers:
                    # All tickers for this interval are ready, flush immediately
                    self._flush_interval_cache(interval)
                else:
                    # Start or restart timeout timer for this interval
                    self._start_timeout_timer(interval)

    def _start_timeout_timer(self, interval: Interval) -> None:
        """
        Start a timeout timer for a specific interval.

        Args:
            interval: The interval to start the timer for
        """
        # Cancel existing timer for this interval
        if interval in self._timeout_timers and self._timeout_timers[interval]:
            self._timeout_timers[interval].cancel()

        # Start new timer
        timer = threading.Timer(
            self._timeout_duration,
            lambda: self._handle_timeout(interval)
        )
        self._timeout_timers[interval] = timer
        timer.start()

    def _handle_timeout(self, interval: Interval) -> None:
        """
        Handle timeout for a specific interval.

        Args:
            interval: The interval that timed out
        """
        debugger.debug(f"Timeout for interval {interval} - flushing cached data")
        self._flush_interval_cache(interval)

    def _flush_interval_cache(self, interval: Interval) -> None:
        """
        Flush the cached data for a specific interval and publish "all tickers ready" event.

        Args:
            interval: The interval to flush
        """
        with self._stream_lock:
            if interval not in self._interval_cache or not self._interval_cache[interval]:
                return

            cached_data = self._interval_cache[interval].copy()
            self._interval_cache[interval].clear()

            # Cancel timer for this interval
            if interval in self._timeout_timers and self._timeout_timers[interval]:
                self._timeout_timers[interval].cancel()
                del self._timeout_timers[interval]

        # Publish "all tickers ready" event
        self._publish_all_ticker_candle(interval, cached_data)

        # Publish periodic event
        self._publish_periodic_event(interval)

    def set_timeout_duration(self, duration: float) -> None:
        """
        Set the timeout duration for waiting for complete data.

        Args:
            duration: Timeout duration in seconds
        """
        self._timeout_duration = duration

    @abstractmethod
    def _setup_subscriptions(self) -> None:
        """
        Set up subscriptions for all tickers and intervals.

        This method sets up subscriptions for all ticker/interval combinations
        specified in the watch_dict.
        """
        pass

    @abstractmethod
    def _cleanup_subscriptions(self) -> None:
        """
        Clean up all subscriptions.

        This method unsubscribes from all ticker/interval combinations.
        """
        pass

    @abstractmethod
    def _initialize_stream_connection(self) -> None:
        """
        Initialize the streaming connection.

        Subclasses must implement this method to establish their specific streaming API connection.
        This method should set up the necessary websocket connections, authentication, etc.
        """
        pass

    def _polling_loop(self, poll_interval: Interval) -> None:
        """
        Overridden polling loop for StreamBroker that only handles periodic events.

        Unlike the base Broker class, StreamBroker gets price data from streaming callbacks,
        so this polling loop only needs to handle periodic events.

        Args:
            poll_interval: Interval enum representing the polling frequency (inherited but not used for timing)
        """
        # Define the polling tasks for StreamBroker (only periodic events)
        polling_tasks = [
            {
                'function': self._publish_periodic_events,
                'interval': Interval.SEC_15,  # Check every 15 seconds for periodic events
            }
        ]

        self._common_polling_loop(polling_tasks)
