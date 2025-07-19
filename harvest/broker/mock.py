import datetime as dt
import itertools
import time
import uuid
from typing import Callable, Dict, Any
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl

from harvest.broker._base import Broker
from harvest.definitions import (
    Account,
    AssetType,
    ChainData,
    ChainInfo,
    OptionData,
    Order,
    OrderList,
    OrderSide,
    OrderStatus,
    OrderTimeInForce,
    Position,
    Positions,
    RuntimeData,
    TickerCandle,
    TickerFrame,
)
from harvest.enum import Interval, IntervalUnit
from harvest.events.events import PriceUpdateEvent
from harvest.events.event_bus import EventBus
from harvest.util.helper import (
    aggregate_pl_df,
    data_to_occ,
    debugger,
    expand_interval,
    generate_ticker_frame,
    interval_to_timedelta,
    utc_current_time,
)


class MockBroker(Broker):
    """
    A mock broker designed to generate fake data for testing purposes.
    """

    def __init__(
        self,
        current_time: dt.datetime | str | None = None,
        epoch: dt.datetime | None = None,
        stock_market_times: bool = False,
        realistic_simulation: bool = True,
        secret_path: str | None = None,
        time_provider: Callable[[], dt.datetime] | None = None,
        sleep_function: Callable[[float], None] | None = None,
    ) -> None:
        super().__init__(secret_path)

        # Set up exchange and supported intervals
        self.exchange = "MOCK"
        self.interval_list = [
            Interval.SEC_15,
            Interval.MIN_1,
            Interval.MIN_5,
            Interval.MIN_15,
            Interval.MIN_30,
            Interval.HR_1,
            Interval.DAY_1,
        ]
        self.req_keys = []

        # Whether or not to include time outside of the typical time that US stock market operates.
        self.stock_market_times = stock_market_times

        # `True` means a one minute interval will take one minute in real time, and `False` will make a one minute interval run as fast as possible.
        self.realistic_simulation = realistic_simulation

        # The current_time is used to let users go back in time.
        if current_time is None:
            self.current_time = utc_current_time()
        elif isinstance(current_time, str):
            # Parse string datetime in format "YYYY-MM-DD HH:MM"
            self.current_time = dt.datetime.strptime(current_time, "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc)
        else:
            self.current_time = current_time

        # Fake the epoch so the difference between the time Harvest starts and the epoch is fixed
        if epoch is None:
            self.epoch = utc_current_time() - dt.timedelta(days=365 * 30)
        else:
            self.epoch = epoch

        # Stores generated mock price history
        self.mock_price_history: Dict[str, Dict[Interval, pl.DataFrame]] = {}
        # Stores rngs for each asset to make `fetch_price_history` fixed
        self.rng: Dict[str, np.random.Generator] = {}

        # Set a default poll interval in case `setup` is not called.
        self.poll_interval = Interval.MIN_1

        # Initialize broker state
        self.orders: Dict[str, Order] = {}
        self.positions: Dict[str, Position] = {}

        # Initialize RuntimeData with current time and timezone
        broker_timezone = ZoneInfo("UTC") if self.current_time.tzinfo is None else self.current_time.tzinfo
        if not isinstance(broker_timezone, ZoneInfo):
            broker_timezone = ZoneInfo("UTC")

        self.stats = RuntimeData(
            utc_timestamp=self.current_time,
            broker_timezone=broker_timezone,
        )

        self._continue_polling = True

        # Testing control - injectable dependencies
        self.time_provider = time_provider or self._default_time_provider
        self.sleep_function = sleep_function or time.sleep

        # Testing control - tick limits for deterministic testing
        self._max_ticks: int | None = None  # Limit number of ticks for testing
        self._tick_count: int = 0  # Current tick count

    def setup(self, runtime_data: RuntimeData) -> None:
        """Setup the mock broker with runtime data"""
        self.stats = runtime_data

    def continue_polling(self) -> bool:
        """Check if polling should continue"""
        return self._continue_polling

    def stop_polling(self) -> None:
        """Stop the polling loop"""
        self._continue_polling = False

    def start(
        self,
        watch_dict: dict[Interval, list[str]],
    ) -> None:
        """
        Start the mock broker with the specified intervals and symbols.

        Args:
            watch_dict: Dictionary mapping intervals to lists of symbols to watch
        """
        self.watch_dict = watch_dict
        debugger.debug(f"{type(self).__name__} started...")

        # Find the lowest interval in the watch_dict
        lowest_interval = min(watch_dict.keys())
        self.polling_interval = lowest_interval
        value, unit = expand_interval(lowest_interval)

        # For now, simply convert the interval to seconds and poll at that interval
        poll_seconds = 0
        if unit == "SEC":
            poll_seconds = value
        elif unit == "MIN":
            poll_seconds = value * 60
        elif unit == "HR":
            poll_seconds = value * 60 * 60
        elif unit == "DAY":
            poll_seconds = value * 60 * 60 * 24
        else:
            raise Exception(f"Unsupported interval {lowest_interval}.")

        # Reset tick counter
        self._tick_count = 0

        while self.continue_polling():
            # Check if we've exceeded max ticks (for testing)
            if self._max_ticks is not None and self._tick_count >= self._max_ticks:
                break

            self.tick()
            self._tick_count += 1

            # Only sleep if realistic_simulation is True
            if self.realistic_simulation:
                self.sleep_function(poll_seconds)
            # In fast mode, we don't sleep at all - tests run as fast as possible

    def tick(self) -> None:
        # Update the current time to simulate time passing
        self.advance_time()

        # Note: In the new service-oriented architecture,
        # the MarketDataService will handle publishing price updates
        # This method is kept for compatibility but event publishing
        # should be handled by the MarketDataService

    # -------------- Streamer methods -------------- #

    def get_current_time(self) -> dt.datetime:
        """Get the current time for the mock broker"""
        return self.stats.utc_timestamp if self.stats else self.current_time

    def fetch_price_history(
        self,
        symbol: str,
        interval: Interval,
        start: dt.datetime | None = None,
        end: dt.datetime | None = None,
    ) -> TickerFrame:
        if not start:
            start = self.epoch
        if not end:
            end = self.get_current_time()

        count = int((end - start).total_seconds() // interval_to_timedelta(interval).total_seconds())

        # Use the generate_ticker_frame function to create mock data
        frame = generate_ticker_frame(
            symbol,
            interval,
            count,
            start,
        )

        # Filter by the requested time range
        frame_df = frame.df
        if start:
            frame_df = frame_df.filter(pl.col("timestamp") >= start)
        if end:
            frame_df = frame_df.filter(pl.col("timestamp") <= end)

        return TickerFrame(frame_df)

    def fetch_latest_price(self, symbol: str, interval: Interval) -> TickerCandle:
        return self.fetch_price_history(symbol, interval, end=self.get_current_time())[-1]

    def fetch_option_market_data(self, symbol: str) -> OptionData:
        price = self.fetch_latest_price(symbol, self.poll_interval).close
        debugger.debug(f"Dummy Streamer fake fetch option market data price for {symbol}: {price}")

        return OptionData(
            symbol=symbol,
            expiration=self.get_current_time(),
            strike=price,
            price=price,
            ask=price * 1.05,
            bid=price * 0.95,
        )

    def fetch_chain_data(self, symbol: str, date: dt.datetime) -> ChainData:
        price = self.fetch_latest_price(symbol, self.poll_interval).close

        # Types = call, put
        types = ["call", "put"]
        # Strike prices are price +- 200%
        strikes = np.linspace(price * 0.2, price * 2.0, 10)
        # Expirations are the next day, next week, and next month
        expirations = [date + dt.timedelta(days=1), date + dt.timedelta(days=7), date + dt.timedelta(days=30)]

        # Create a permutation of all the data
        data = []
        for typ, strike, expiration in itertools.product(types, strikes, expirations):
            data.append([symbol, expiration, typ, strike])

        # Create a DataFrame from the data
        # Columns are exp_date, strike, and type, with the index being the OCC symbol
        df = pl.DataFrame(
            {
                "exp_date": [d[1] for d in data],
                "strike": [d[3] for d in data],
                "type": [d[2] for d in data],
                "symbol": [data_to_occ(*d) for d in data],
            }
        )
        df = df.set_sorted("symbol")

        return ChainData(df)

    def fetch_chain_info(self, symbol: str) -> ChainInfo:
        cur_date = self.get_current_time().date()
        return ChainInfo(
            "123456",
            [
                cur_date + dt.timedelta(days=1),
                cur_date + dt.timedelta(days=7),
                cur_date + dt.timedelta(days=30),
            ],
        )

    # ------------- Broker methods ------------- #

    # ------------- Abstract methods implementation ------------- #

    def create_secret(self) -> Dict[str, str]:
        """Mock broker doesn't need real credentials"""
        return {}

    def refresh_cred(self) -> None:
        """Mock broker doesn't need credential refresh"""
        pass

    def fetch_market_hours(self, date: dt.date) -> Dict[str, Any]:
        """Return mock market hours - always open for testing"""
        return {
            "is_open": True,
            "open_at": dt.datetime.combine(date, dt.time(9, 30), tzinfo=dt.timezone.utc),
            "close_at": dt.datetime.combine(date, dt.time(16, 0), tzinfo=dt.timezone.utc),
        }

    def fetch_stock_positions(self) -> Positions:
        """Return mock stock positions"""
        return Positions(self.positions)

    def fetch_option_positions(self) -> Positions:
        """Return mock option positions"""
        option_positions = {k: v for k, v in self.positions.items() if v.symbol.count(":") > 0}
        return Positions(option_positions)

    def fetch_crypto_positions(self) -> Positions:
        """Return mock crypto positions"""
        crypto_positions = {k: v for k, v in self.positions.items() if v.symbol.startswith("@")}
        return Positions(crypto_positions)

    def fetch_account(self) -> Account:
        """Return mock account information"""
        return Account(
            account_name="MockAccount",
            positions=Positions(self.positions),
            orders=OrderList(self.orders),
            asset_value=sum(p.value for p in self.positions.values()),
            cash=10000.0,
            equity=10000.0 + sum(p.value for p in self.positions.values()),
            buying_power=20000.0,
            multiplier=1.0
        )

    def fetch_stock_order_status(self, id) -> Order:
        """Return mock stock order status"""
        if id in self.orders:
            return self.orders[id]
        else:
            # Return a filled mock order
            return Order(
                order_type=AssetType.STOCK,
                symbol="SPY",
                quantity=100.0,
                time_in_force=OrderTimeInForce.GTC,
                side=OrderSide.BUY,
                order_id=id,
                status=OrderStatus.FILLED,
                filled_time=self.get_current_time(),
                filled_price=400.0,
                filled_quantity=100.0,
                base_symbol=None,
            )

    def fetch_option_order_status(self, id) -> Order:
        """Return mock option order status"""
        if id in self.orders:
            return self.orders[id]
        else:
            # Return a filled mock order
            return Order(
                order_type=AssetType.OPTION,
                symbol="SPY:20241215:400:C",
                quantity=1.0,
                time_in_force=OrderTimeInForce.GTC,
                side=OrderSide.BUY,
                order_id=id,
                status=OrderStatus.FILLED,
                filled_time=self.get_current_time(),
                filled_price=5.0,
                filled_quantity=1.0,
                base_symbol="SPY",
            )

    def fetch_crypto_order_status(self, id) -> Order:
        """Return mock crypto order status"""
        if id in self.orders:
            return self.orders[id]
        else:
            # Return a filled mock order
            return Order(
                order_type=AssetType.CRYPTO,
                symbol="@BTC",
                quantity=0.1,
                time_in_force=OrderTimeInForce.GTC,
                side=OrderSide.BUY,
                order_id=id,
                status=OrderStatus.FILLED,
                filled_time=self.get_current_time(),
                filled_price=50000.0,
                filled_quantity=0.1,
                base_symbol=None,
            )

    def fetch_order_queue(self) -> OrderList:
        """Return mock order queue"""
        return OrderList(self.orders)

    # --------------- Methods for Trading --------------- #

    def order_stock_limit(
        self,
        side: OrderSide,
        symbol: str,
        quantity: float,
        limit_price: float,
        in_force: OrderTimeInForce = OrderTimeInForce.GTC,
        extended: bool = False,
    ) -> Order:
        # For the purposes of testing, every order is initially not filled
        order = Order(
            order_type=AssetType.STOCK,
            symbol=symbol,
            quantity=quantity,
            time_in_force=in_force,
            side=side,
            order_id=str(uuid.uuid4()),
            status=OrderStatus.OPEN,
            filled_time=None,
            filled_price=None,
            filled_quantity=None,
            base_symbol=None,
        )
        self.orders[order.order_id] = order
        return order

    def order_crypto_limit(
        self,
        side: str,
        symbol: str,
        quantity: float,
        limit_price: float,
        in_force: str = "gtc",
        extended: bool = False,
    ) -> Order:
        """Place a crypto limit order"""
        order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        time_in_force = OrderTimeInForce.GTC if in_force.lower() == "gtc" else OrderTimeInForce.GTD

        order = Order(
            order_type=AssetType.CRYPTO,
            symbol=symbol,
            quantity=quantity,
            time_in_force=time_in_force,
            side=order_side,
            order_id=str(uuid.uuid4()),
            status=OrderStatus.OPEN,
            filled_time=None,
            filled_price=None,
            filled_quantity=None,
            base_symbol=None,
        )
        self.orders[order.order_id] = order
        return order

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
        """Place an option limit order"""
        order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        time_in_force = OrderTimeInForce.GTC if in_force.lower() == "gtc" else OrderTimeInForce.GTD

        # Create OCC symbol for the option
        occ_symbol = data_to_occ(symbol, exp_date, option_type, strike)

        order = Order(
            order_type=AssetType.OPTION,
            symbol=occ_symbol,
            quantity=quantity,
            time_in_force=time_in_force,
            side=order_side,
            order_id=str(uuid.uuid4()),
            status=OrderStatus.OPEN,
            filled_time=None,
            filled_price=None,
            filled_quantity=None,
            base_symbol=symbol,
        )
        self.orders[order.order_id] = order
        return order

    def cancel_stock_order(self, order_id) -> None:
        """Cancel a stock order"""
        if order_id in self.orders:
            del self.orders[order_id]

    def cancel_crypto_order(self, order_id) -> None:
        """Cancel a crypto order"""
        if order_id in self.orders:
            del self.orders[order_id]

    def cancel_option_order(self, order_id) -> None:
        """Cancel an option order"""
        if order_id in self.orders:
            del self.orders[order_id]

    def fulfill_order(self, order: Order) -> None:
        """Fulfill an order for testing purposes"""
        order.status = OrderStatus.FILLED
        order.filled_time = self.get_current_time()
        order.filled_price = self.fetch_latest_price(order.symbol, self.poll_interval).close
        order.filled_quantity = order.quantity

        position = Position(
            symbol=order.symbol,
            quantity=order.quantity,
            avg_price=order.filled_price,
        )
        self.positions[order.symbol] = position
        del self.orders[order.order_id]

    # ------------- Helper methods ------------- #

    # def fetch_latest_ohlc(self) -> Dict[str, pl.DataFrame]:
    #     df_dict = {}
    #     end = self.get_current_time()
    #     start = end - dt.timedelta(days=3)

    #     for symbol in self.stats.watchlist_cfg:
    #         df_dict[symbol] = self.fetch_price_history(
    #             symbol, self.stats.watchlist_cfg[symbol]["interval"], start, end
    #         ).iloc[[-1]]

    #     return df_dict

    def advance_time(self) -> None:
        """Advance the mock time by the poll interval"""
        if self.stats:
            self.stats.utc_timestamp += interval_to_timedelta(self.poll_interval)
        else:
            self.current_time += interval_to_timedelta(self.poll_interval)

    def clear_mock_data(self) -> None:
        """Clear all mock price history data to free memory"""
        self.mock_price_history.clear()
        self.rng.clear()

    def limit_mock_data_size(self, max_candles_per_symbol: int = 10000) -> None:
        """Limit the size of mock data to prevent memory issues"""
        for symbol in self.mock_price_history:
            for interval in self.mock_price_history[symbol]:
                df = self.mock_price_history[symbol][interval]
                if len(df) > max_candles_per_symbol:
                    # Keep only the most recent candles
                    self.mock_price_history[symbol][interval] = df.tail(max_candles_per_symbol)

    def generate_random_data(
        self, symbol: str, start: dt.datetime, num_of_random: int, rng: np.random.Generator | None = None
    ) -> tuple[np.random.Generator, pl.DataFrame]:
        """Generate random price data with size limits for performance"""
        if num_of_random > 1000000:  # Increased limit from 100000 to 1000000
            raise ValueError(f"Requested {num_of_random} candles, but maximum is 1000000 for performance.")

        rng = rng or np.random.default_rng(int.from_bytes(symbol.encode("ascii"), "big"))
        returns = rng.normal(loc=1e-12, scale=1e-12, size=num_of_random)

        # Generate timestamps efficiently
        timestamps = [start + dt.timedelta(minutes=i) for i in range(num_of_random)]

        df = pl.DataFrame({
            "timestamp": timestamps,
            "price": returns,
        })

        return rng, df

    def generate_history(
        self, symbol: str, interval: Interval, start: dt.datetime | None = None, end: dt.datetime | None = None
    ) -> pl.DataFrame:
        if start is None:
            start = self.epoch
        if end is None:
            end = self.get_current_time()

        original_start = start
        original_end = end

        # Start time is rounded up to the nearest complete candle
        if interval.unit == IntervalUnit.MIN:
            adjusted_min = start.minute // interval.interval_value * interval.interval_value + (
                interval.interval_value if start.minute % interval.interval_value != 0 else 0
            )
            if adjusted_min >= 60:
                hour = start.hour + 1
                adjusted_min = adjusted_min - 60
            else:
                hour = start.hour
            start = start.replace(
                minute=adjusted_min,
                hour=hour,
                second=0,
                microsecond=0,
            )
        elif interval.unit == IntervalUnit.HR:
            if start.minute != 0 or start.second != 0 or start.microsecond != 0:
                add_hour = True
            else:
                add_hour = False
            start = start.replace(hour=start.hour, minute=0, second=0, microsecond=0)
            if add_hour:
                start = start + dt.timedelta(hours=1)
        elif interval.unit == IntervalUnit.DAY:
            if start.hour != 0 or start.minute != 0 or start.second != 0 or start.microsecond != 0:
                add_day = True
            else:
                add_day = False
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            if add_day:
                start = start + dt.timedelta(days=1)

        # End time is rounded down to the nearest complete candle
        if interval.unit == IntervalUnit.MIN:
            adjusted_min = end.minute // interval.interval_value * interval.interval_value - (
                interval.interval_value if end.minute % interval.interval_value != 0 else 0
            )
            if adjusted_min < 0:
                hour = end.hour - 1
                adjusted_min = 60 + adjusted_min
            else:
                hour = end.hour
            end = end.replace(
                minute=adjusted_min,
                hour=hour,
                second=0,
                microsecond=0,
            )
        elif interval.unit == IntervalUnit.HR:
            if end.minute != 0 or end.second != 0 or end.microsecond != 0:
                subtract_hour = True
            else:
                subtract_hour = False
            end = end.replace(hour=end.hour, minute=0, second=0, microsecond=0)
            if subtract_hour:
                end = end - dt.timedelta(hours=1)
        elif interval.unit == IntervalUnit.DAY:
            if end.hour != 0 or end.minute != 0 or end.second != 0 or end.microsecond != 0:
                subtract_day = True
            else:
                subtract_day = False
            end = end.replace(hour=0, minute=0, second=0, microsecond=0)
            if subtract_day:
                end = end - dt.timedelta(days=1)

        # Convert datetime to indices
        if interval.unit == IntervalUnit.SEC:
            divider = interval.interval_value
        elif interval.unit == IntervalUnit.MIN:
            divider = interval.interval_value * 60
        elif interval.unit == IntervalUnit.HR:
            divider = interval.interval_value * 60 * 60
        elif interval.unit == IntervalUnit.DAY:
            divider = interval.interval_value * 60 * 60 * 24
        else:
            raise Exception(f"Unsupported interval {interval}.")

        start_index = int((start - self.epoch).total_seconds() // divider)
        end_index = int(((end - self.epoch).total_seconds() - divider) // divider) + 1
        num_of_random = end_index - start_index


        if symbol in self.mock_price_history:
            if interval in self.mock_price_history[symbol]:
                history = self.mock_price_history[symbol][interval]
            else:
                # if Interval.MIN_1 in self.mock_price_history[symbol]:
                if interval == Interval.MIN_1:
                    if Interval.MIN_1 not in self.mock_price_history[symbol]:
                        rng, df = self.generate_random_data(symbol, original_start, num_of_random)
                        self.rng[symbol] = rng
                        self.mock_price_history[symbol][Interval.MIN_1] = df
                    history = self.mock_price_history[symbol][Interval.MIN_1]
                else:
                    one_min_history = self.mock_price_history[symbol][Interval.MIN_1]
                    history = aggregate_pl_df(one_min_history, interval)
                # else:
                #     self.generate_history(symbol, Interval.MIN_1, original_start, original_end)
                #     one_min_history = self.mock_price_history[symbol][Interval.MIN_1]
                #     history = aggregate_pl_df(one_min_history, interval)

            # If there is not enough data to generate the new interval, we generate more data
            if len(history) < num_of_random:
                rng = self.rng[symbol]
                adjusted_num_of_random = num_of_random - len(history)
                if interval == Interval.MIN_1:
                    # returns = rng.normal(loc=1e-12, scale=1e-12, size=num_of_random)
                    additional_returns = rng.normal(loc=1e-12, scale=1e-12, size=adjusted_num_of_random)
                    # Add the last price of the current history to the additional returns
                    additional_returns = np.append(additional_returns, history[-1])
                    df = {
                        "timestamp": [start + dt.timedelta(minutes=i) for i in range(adjusted_num_of_random)],
                        "price": additional_returns,
                    }
                    current_df = self.mock_price_history[symbol][Interval.MIN_1]
                    history = current_df.extend(pl.DataFrame(df))
                else:
                    self.generate_history(symbol, Interval.MIN_1, original_start, original_end)
                    one_min_history = self.mock_price_history[symbol][Interval.MIN_1]
                    history = aggregate_pl_df(one_min_history, interval)
                    history = history.filter(pl.col("timestamp") >= start, pl.col("timestamp") <= end)

            self.mock_price_history[symbol][interval] = history

        else:
            self.mock_price_history[symbol] = {}
            if Interval.MIN_1 not in self.mock_price_history[symbol]:
                if interval == Interval.MIN_1:
                    rng, df = self.generate_random_data(symbol, start, num_of_random)
                    self.mock_price_history[symbol][Interval.MIN_1] = df
                    self.rng[symbol] = rng
                else:
                    self.generate_history(symbol, Interval.MIN_1, original_start, original_end)
                    one_min_history = self.mock_price_history[symbol][Interval.MIN_1]

            history = aggregate_pl_df(self.mock_price_history[symbol][Interval.MIN_1], interval)
            history = history.filter(pl.col("timestamp") >= start, pl.col("timestamp") <= end)
            self.mock_price_history[symbol][interval] = history

        # Generate OHLC data more efficiently
        prices_df = self.mock_price_history[symbol][interval]

        # Filter once and reuse
        filtered_prices = prices_df.filter(pl.col("timestamp") >= start, pl.col("timestamp") <= end)

        # Prevent prices from going negative
        filtered_prices = filtered_prices.with_columns(
            pl.when(pl.col("price") < 0).then(0.01).otherwise(pl.col("price")).alias("price")
        )

        # Calculate OHLC from the prices using vectorized operations
        price_col = filtered_prices.select("price").to_series()
        timestamp_col = filtered_prices.select("timestamp").to_series()

        # Generate realistic OHLC data
        opens = price_col - 50
        lows = price_col - 100
        highs = price_col + 100
        closes = price_col + 50
        volumes = (1000 * (price_col + 20)).cast(pl.Int64)

        # Create result DataFrame efficiently
        results = pl.DataFrame({
            "timestamp": timestamp_col,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        })

        # Apply timezone and symbol column efficiently
        results = results.with_columns([
            pl.col("timestamp").cast(pl.Datetime(time_zone="UTC")),
            pl.col("open").alias(symbol)
        ])

        return results

    def _get_supported_intervals_tickers(self) -> dict[Interval, list[str]]:
        """
        Get mapping of supported intervals to supported tickers for MockBroker.

        MockBroker supports common tickers for all intervals.
        """
        # Common test tickers
        common_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "NFLX", "DIS"]

        # MockBroker supports all intervals with the same ticker set
        return {interval: common_tickers for interval in self.interval_list}

    def supports_symbol(self, symbol: str) -> bool:
        """
        Check if MockBroker supports the specified symbol.

        MockBroker supports common test symbols.
        """
        supported_symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "NFLX", "DIS"]
        return symbol in supported_symbols

    # ------------- Testing Helper Methods ------------- #

    def set_price_data(self, symbol: str, candle: TickerCandle) -> None:
        """Set mock price data for testing."""
        if symbol not in self.mock_price_history:
            self.mock_price_history[symbol] = {}

        # Create a simple DataFrame with the candle data
        df = pl.DataFrame({
            "timestamp": [candle.timestamp],
            "open": [candle.open],
            "high": [candle.high],
            "low": [candle.low],
            "close": [candle.close],
            "volume": [candle.volume],
        })

        # Store for MIN_1 interval by default (can be extended for other intervals)
        self.mock_price_history[symbol][Interval.MIN_1] = df

    def reset_state(self) -> None:
        """Reset broker state for testing"""
        self.orders.clear()
        self.positions.clear()
        self.mock_price_history.clear()
        self.rng.clear()
        self.rng.clear()

    def _default_time_provider(self) -> dt.datetime:
        """Default time provider that returns current UTC time"""
        return self.get_current_time()

    def set_max_ticks(self, max_ticks: int | None) -> None:
        """Set maximum number of ticks for testing control"""
        self._max_ticks = max_ticks
        self._tick_count = 0

    def get_tick_count(self) -> int:
        """Get current tick count"""
        return self._tick_count

    def reset_tick_count(self) -> None:
        """Reset tick counter"""
        self._tick_count = 0

    def step(self) -> None:
        """
        Perform one step of the broker's operation for testing purposes.
        This method fetches the latest data for all watched symbols and publishes
        price update events through the event bus system.

        Note: This method does not advance time - that should be done externally
        via time.increment_time() in tests.
        """
        if not self.watch_dict:
            return

        # Build the data dictionary for event publishing
        df_dict: dict[Interval, dict[str, TickerCandle]] = {}

        # Fetch data and publish events
        for interval, symbols in self.watch_dict.items():
            df_dict[interval] = {}
            for symbol in symbols:
                try:
                    candle = self.fetch_latest_price(symbol, interval)
                    df_dict[interval][symbol] = candle
                    # Publish individual ticker event
                    self._publish_ticker_candle(symbol, candle, interval)
                except Exception as e:
                    debugger.error(f"Error fetching price for {symbol}: {e}")
                    continue

            # Publish "all tickers ready" event for this interval
            if df_dict[interval]:
                self._publish_all_ticker_candle(interval, df_dict[interval])
