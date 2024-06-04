import datetime as dt
import itertools
import time
from typing import Callable, Dict, Union

import numpy as np
import pandas as pd

from harvest.broker._base import Broker
from harvest.definitions import Account, Stats
from harvest.enum import Interval
from harvest.util.date import convert_input_to_datetime
from harvest.util.helper import (
    aggregate_df,
    data_to_occ,
    debugger,
    expand_interval,
    interval_to_timedelta,
    utc_current_time,
)


class DummyDataBroker(Broker):
    """
    A dummy broker designed to generate fake data for testing purposes.
    """

    interval_list = [
        Interval.MIN_1,
        Interval.MIN_5,
        Interval.MIN_15,
        Interval.MIN_30,
        Interval.HR_1,
        Interval.DAY_1,
    ]

    def __init__(
        self,
        current_time: Union[str, dt.datetime] = None,
        stock_market_times: bool = False,
        realistic_simulation: bool = True,
    ) -> None:
        # Whether or not to include time outside of the typical time that US stock market operates.
        self.stock_market_times = stock_market_times

        # `True` means a one minute interval will take one minute in real time, and `False` will make a one minute interval run as fast as possible.
        self.realistic_simulation = realistic_simulation

        # The current_time is used to let users go back in time.
        self.current_time = convert_input_to_datetime(current_time)
        if self.current_time is None:
            self.current_time = utc_current_time()

        # Fake the epoch so the difference between the time Harvest starts and the epoch is fixed
        self.epoch = utc_current_time() - dt.timedelta(days=365 * 30)

        # Store random values and generates for each asset to make `fetch_price_history` fixed
        self.randomness = {}

        # Set a default poll interval in case `setup` is not called.
        self.poll_interval = Interval.MIN_1

    def setup(self, stats: Stats, account: Account, trader_main: Callable = None) -> None:
        super().setup(stats, account, trader_main)
        # Override the time set in the base class with the user specified time
        self.stats.timestamp = self.get_current_time()

    def start(self) -> None:
        val, unit = expand_interval(self.poll_interval)

        debugger.debug(f"{type(self).__name__} started...")
        while True:
            if unit == "MIN":
                sleep = val * 60
            elif unit == "HR":
                sleep = val * 3600
            elif unit == "DAY":
                sleep = val * 86400

            self.stats.timestamp = self.get_current_time()
            self.step()
            if self.realistic_simulation:
                # Simulate realistic wait times
                time.sleep(sleep)

    def step(self) -> None:
        self.tick()
        df_dict = self.fetch_latest_ohlc()
        self.broker_hub_cb(df_dict)

    # -------------- Streamer methods -------------- #

    def get_current_time(self) -> dt.datetime:
        return self.current_time

    def fetch_price_history(
        self,
        symbol: str,
        interval: Interval,
        start: Union[str, dt.datetime] = None,
        end: Union[str, dt.datetime] = None,
    ) -> pd.DataFrame:
        start = convert_input_to_datetime(start)
        end = convert_input_to_datetime(end)

        if start is None:
            if interval in [
                Interval.MIN_1,
                Interval.MIN_5,
                Interval.MIN_15,
                Interval.MIN_30,
            ]:
                start = self.get_current_time() - dt.timedelta(days=2)
            elif interval == Interval.HR_1:
                start = self.get_current_time() - dt.timedelta(days=14)
            else:
                start = self.get_current_time() - dt.timedelta(days=365)

        if end is None:
            end = self.get_current_time()

        results = self._generate_history(symbol, interval, start, end)

        if self.stock_market_times:
            debugger.debug("Dummy Broker excluding information when the stock market is closed.")
            open_time = dt.time(hour=13, minute=30)
            close_time = dt.time(hour=20)

            # Removes data points when the stock marked is closed. Does not handle holidays.
            results = results.loc[(open_time < results.index.time) & (results.index.time < close_time)]
            results = results[(results.index.dayofweek != 5) & (results.index.dayofweek != 6)]

        return results

    def fetch_option_market_data(self, symbol: str) -> Dict[str, float]:
        price = self.fetch_price_history(symbol, self.poll_interval)[symbol].iloc[-1]["close"] / 100
        debugger.debug(f"Dummy Streamer fake fetch option market data price for {symbol}: {price}")

        return {
            "price": price,
            "ask": price * 1.05,
            "bid": price * 0.95,
        }

    def fetch_chain_data(self, symbol: str, date: Union[str, dt.datetime]) -> pd.DataFrame:
        price = self.fetch_price_history(symbol, self.poll_interval)[symbol].iloc[-1]["close"] / 100

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
        df = pd.DataFrame(data, columns=["exp_date", "strike", "type"])
        df.index = [data_to_occ(*l) for l in data]

        return df

    def fetch_chain_info(self, symbol: str) -> Dict[str, str]:
        cur_date = self.get_current_time().date()
        return {
            "chain_id": "123456",
            "exp_dates": [
                cur_date + dt.timedelta(days=1),
                cur_date + dt.timedelta(days=7),
                cur_date + dt.timedelta(days=30),
            ],
            "multiplier": 100,
        }

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

    # Not implemented:
    #   order_stock_limit
    #   order_crypto_limit
    #   order_option_limit

    # ------------- Helper methods ------------- #

    def fetch_latest_ohlc(self) -> Dict[str, pd.DataFrame]:
        df_dict = {}
        end = self.get_current_time()
        start = end - dt.timedelta(days=3)

        for symbol in self.stats.watchlist_cfg:
            df_dict[symbol] = self.fetch_price_history(
                symbol, self.stats.watchlist_cfg[symbol]["interval"], start, end
            ).iloc[[-1]]

        return df_dict

    def tick(self) -> None:
        self.current_time += interval_to_timedelta(self.poll_interval)

    def _generate_history(self, symbol: str, interval: Interval, start: dt.datetime, end: dt.datetime) -> pd.DataFrame:
        # Convert datetime to indices
        start_index = int((start - self.epoch).total_seconds() // 60)
        end_index = 1 + int((end - self.epoch).total_seconds() // 60)

        if symbol in self.randomness:
            # If we already generated data from this asset
            num_of_random = 1 + end_index

            if len(self.randomness[symbol]) < num_of_random:
                # If the new end index is greater than the data we have
                # Get the rng for this symbol
                rng = self.randomness[symbol + "_rng"]
                # Update the number of random data points
                num_of_random -= len(self.randomness[symbol])
                returns = rng.normal(loc=1e-12, scale=1e-12, size=num_of_random)
                # Calculate the change in price since the first price
                new_price_changes = np.append(self.randomness[symbol], returns).cumsum()
                # Store the new prices
                self.randomness[symbol] = np.append(self.randomness[symbol], new_price_changes)

        else:
            # If there is no information about the asset
            # Create an rng using the asset's symbol as a seed
            rng = np.random.default_rng(int.from_bytes(symbol.encode("ascii"), "big"))
            num_of_random = 1 + end_index
            # Generate a bunch of random numbers using Geometric Brownian Motion
            returns = rng.normal(loc=1e-12, scale=1e-12, size=num_of_random)
            # Store the price change since the first price
            self.randomness[symbol] = returns.cumsum()
            self.randomness[symbol + "_rng"] = rng

        # The initial price is arbitrarily calculated from the first change in price
        start_price = 100 * (self.randomness[symbol][0] + 1)

        times = []
        current_time = start

        # Get the prices for the current interval
        prices = start_price + self.randomness[symbol][start_index:end_index]
        # Prevent prices from going negative
        prices[prices < 0] = 0.01

        # Calculate ohlc from the prices
        open_s = prices - 50
        low = prices - 100
        high = prices + 100
        close = prices + 50
        volume = (1000 * (prices + 20)).astype(int)

        # Fake the timestamps
        while current_time <= end:
            times.append(current_time)
            current_time += dt.timedelta(minutes=1)

        d = {
            "timestamp": times,
            "open": open_s,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }

        results = pd.DataFrame(data=d)
        results.index = pd.DatetimeIndex(results["timestamp"], tz=dt.timezone.utc)
        results.drop(columns=["timestamp"], inplace=True)
        results.columns = pd.MultiIndex.from_product([[symbol], results.columns])
        results = aggregate_df(results, interval)
        results = results.loc[start:end]
        return results
