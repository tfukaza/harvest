import datetime as dt
import itertools
import time
import uuid
from typing import Callable, Dict
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import polars as pl

from harvest.broker._base import Broker
from harvest.definitions import (
    AssetType,
    ChainData,
    ChainInfo,
    OptionData,
    Order,
    OrderSide,
    OrderStatus,
    OrderTimeInForce,
    Position,
    RuntimeData,
    TickerCandle,
    TickerFrame,
)
from harvest.enum import Interval, IntervalUnit
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
        current_time: dt.datetime | None = None,
        epoch: dt.datetime | None = None,
        stock_market_times: bool = False,
        realistic_simulation: bool = True,
    ) -> None:
        # Whether or not to include time outside of the typical time that US stock market operates.
        self.stock_market_times = stock_market_times

        # `True` means a one minute interval will take one minute in real time, and `False` will make a one minute interval run as fast as possible.
        self.realistic_simulation = realistic_simulation

        # The current_time is used to let users go back in time.
        if current_time is None:
            self.current_time = utc_current_time()
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

        self.stats = RuntimeData(broker_timezone=ZoneInfo("UTC"), utc_timestamp=self.current_time)

        self.orders: Dict[str, Order] = {}
        self.positions: Dict[str, Position] = {}

    def setup(self, runtime_data: RuntimeData) -> None:
        pass

    def start(
        self,
        watch_dict: dict[Interval, list[str]],
        step_callback: Callable[[dict[Interval, dict[str, pd.DataFrame]]], None],
    ) -> None:
        self.watch_dict = watch_dict
        self.step_callback = step_callback
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

        while self.continue_polling():
            self.tick()
            if self.realistic_simulation:
                time.sleep(poll_seconds)

    def tick(self) -> None:
        super().tick()

    # -------------- Streamer methods -------------- #

    def get_current_time(self) -> dt.datetime:
        return self.stats.utc_timestamp

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
            end = self.stats.utc_timestamp

        count = int((end - start).total_seconds() // interval_to_timedelta(interval).total_seconds())

        start = self.stats.utc_timestamp
        if interval.unit == IntervalUnit.MIN:
            start = start.replace(
                minute=start.minute // interval.interval_value * interval.interval_value, second=0, microsecond=0
            )
        elif interval.unit == IntervalUnit.HR:
            start = start.replace(hour=start.hour, minute=0, second=0, microsecond=0)
        elif interval.unit == IntervalUnit.DAY:
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)

        start = start - interval_to_timedelta(interval) * count

        frame = generate_ticker_frame(
            symbol,
            interval,
            count,
            start,
        )
        # Frame will have candles for intervals up to but not including the current time.
        # For example if the current time is 10:00 AM and interval is 5 minute,
        # the frame will have candles up to 9:55 AM.
        frame = frame.df
        if start:
            frame = frame.filter(pl.col("timestamp") >= start)
        if end:
            frame = frame.filter(pl.col("timestamp") <= end)

        # if self.stock_market_times:
        #     open_time = dt.time(hour=13, minute=30)
        #     close_time = dt.time(hour=20)

        #     # Removes data points when the stock marked is closed. Does not handle holidays.
        #     results = results.loc[(open_time < results.index.time) & (results.index.time < close_time)]
        #     results = results[(results.index.dayofweek != 5) & (results.index.dayofweek != 6)]

        return TickerFrame(frame)

    def fetch_latest_price(self, symbol: str, interval: Interval) -> TickerCandle:
        return self.fetch_price_history(symbol, interval, end=self.stats.utc_timestamp)[-1]

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

    # Not implemented:
    #   fetch_stock_positions
    #   fetch_option_positions
    #   fetch_crypto_positions
    #   update_option_positions
    #   fetch_account
    #   fetch_stock_order_status
    #   fetch_option_order_status
    #   fetch_crypto_order_status
    #   fetch_order_queue

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
            order_id=uuid.uuid4(),
            status=OrderStatus.OPEN,
            filled_time=None,
            filled_price=None,
            filled_quantity=None,
            base_symbol=None,
        )
        self.orders[order.order_id] = order
        return order

    def test_fulfill_order(self, order: Order) -> None:
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

    # def fetch_latest_ohlc(self) -> Dict[str, pd.DataFrame]:
    #     df_dict = {}
    #     end = self.get_current_time()
    #     start = end - dt.timedelta(days=3)

    #     for symbol in self.stats.watchlist_cfg:
    #         df_dict[symbol] = self.fetch_price_history(
    #             symbol, self.stats.watchlist_cfg[symbol]["interval"], start, end
    #         ).iloc[[-1]]

    #     return df_dict

    def advance_time(self) -> None:
        self.stats.utc_timestamp += interval_to_timedelta(self.poll_interval)

    def generate_random_data(
        self, symbol: str, start: dt.datetime, num_of_random: int, rng: np.random.Generator | None = None
    ) -> tuple[np.random.Generator, pl.DataFrame]:
        rng = rng or np.random.default_rng(int.from_bytes(symbol.encode("ascii"), "big"))
        returns = rng.normal(loc=1e-12, scale=1e-12, size=num_of_random)
        df = {
            "timestamp": [start + dt.timedelta(minutes=i) for i in range(num_of_random)],
            "price": returns,
        }
        return rng, pl.DataFrame(df)

    def generate_history(
        self, symbol: str, interval: Interval, start: dt.datetime | None = None, end: dt.datetime | None = None
    ) -> pl.DataFrame:
        if start is None:
            start = self.epoch
        if end is None:
            end = self.stats.utc_timestamp

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

        print(original_start, original_end, start, end)

        start_index = int((start - self.epoch).total_seconds() // divider)
        end_index = int(((end - self.epoch).total_seconds() - divider) // divider) + 1
        num_of_random = end_index - start_index

        print(start_index, end_index, num_of_random, interval)

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
                    print(one_min_history)
                    print(f"Aggregated {interval} from {Interval.MIN_1} for {symbol}")
                    print(history)
                # else:
                #     self.generate_history(symbol, Interval.MIN_1, original_start, original_end)
                #     one_min_history = self.mock_price_history[symbol][Interval.MIN_1]
                #     history = aggregate_pl_df(one_min_history, interval)

            # If there is not enough data to generate the new interval, we generate more data
            if len(history) < num_of_random:
                print("Generating more data")
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

        # The initial price is arbitrarily calculated from the first change in price
        # start_price = 100 * self.mock_price_history[symbol][interval].select("price").row(0)[0]

        times = []
        # current_time = start

        # Get the prices for the current interval
        prices = self.mock_price_history[symbol][interval]
        # get the rows by index
        prices = prices.filter(pl.col("timestamp") >= start, pl.col("timestamp") <= end)
        # Prevent prices from going negative
        print(prices)
        prices = prices.with_columns(pl.when(pl.col("price") < 0).then(0.01).otherwise(pl.col("price")))

        # Calculate ohlc from the prices
        open_s = prices - 50
        low = prices - 100
        high = prices + 100
        close = prices + 50
        volume = (1000 * (prices + 20)).cast(pl.Int64)

        # Fake the timestamps
        for row in prices.iter_rows():
            times.append(row[0])

        d = {
            "timestamp": times,
            "open": open_s,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }

        results = pl.DataFrame(data=d)
        results = results.with_columns(pl.col("timestamp").cast(pl.Datetime(time_zone="UTC")))
        results = results.with_columns(pl.col("open").alias(symbol))
        # results = aggregate_df(results, interval)
        results = results.filter(pl.col("timestamp") >= start)
        results = results.filter(pl.col("timestamp") <= end)

        return results
