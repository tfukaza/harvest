# Builtins
import datetime as dt
from typing import Any, Dict, List, Tuple
import hashlib

# External libraries
import pytz
import pandas as pd
import numpy as np

# Submodule imports
from harvest.api._base import API
from harvest.utils import *


class DummyStreamer(API):
    """DummyStreamer, as its name implies, is a dummy broker class that can
    be useful for testing algorithms. When used as a streamer, it will return
    randomly generated prices.
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
        realistic_times: bool = False,
    ) -> None:

        self.realistic_times = realistic_times
        # Store random values and generates for each asset to make `fetch_price_history` fixed
        self.randomness = {}

    def main(self) -> None:
        df_dict = {}
        today = now()
        last = today - dt.timedelta(days=3)

        for symbol in self.stats.watchlist_cfg:
            df_dict[symbol] = self.fetch_price_history(
                symbol, self.stats.watchlist_cfg[symbol]["interval"], last, today
            ).iloc[[-1]]

        self.trader_main(df_dict)

    # -------------- Streamer methods -------------- #

    def get_current_time(self) -> dt.datetime:
        return now()

    def fetch_price_history(
        self,
        symbol: str,
        interval: Interval,
        start: dt.datetime = None,
        end: dt.datetime = None,
    ) -> pd.DataFrame:

        if start is None:
            if interval in [
                Interval.MIN_1,
                Interval.MIN_5,
                Interval.MIN_15,
                Interval.MIN_30,
            ]:
                start = self.timestamp - dt.timedelta(days=2)
            elif interval == Interval.HR_1:
                start = self.timestamp - dt.timedelta(days=14)
            else:
                start = self.timestamp - dt.timedelta(days=365)

        if end is None:
            end = self.timestamp

        if start.tzinfo is None or start.tzinfo.utcoffset(start) is None:
            start = pytz.utc.localize(start)

        if end.tzinfo is None or end.tzinfo.utcoffset(end) is None:
            end = pytz.utc.localize(end)

        results = self._generate_history(symbol, start, end)

        if self.realistic_times:
            debugger.debug(
                "Dummy Broker excluding information when the stock market is closed."
            )
            open_time = dt.time(hour=13, minute=30)
            close_time = dt.time(hour=20)

            # Removes datapoints when the stock marked is closed. Does not handle holidays.
            results = results.loc[
                (open_time < results.index.time) & (results.index.time < close_time)
            ]
            results = results[
                (results.index.dayofweek != 5) & (results.index.dayofweek != 6)
            ]

        results.columns = pd.MultiIndex.from_product([[symbol], results.columns])
        results = aggregate_df(results, interval)
        return results

    # TODO: Generate dummy option data

    def fetch_option_market_data(self, symbol: str) -> Dict[str, float]:
        # This is a placeholder so Trader doesn't crash
        message = hashlib.sha256()
        message.update(symbol.encode("utf-8"))
        message.update(str(self.timestamp).encode("utf-8"))
        hsh = message.digest()
        price = int.from_bytes(hsh[:4], "big") / (2 ** 32)
        price = (price + 1) * 1.5
        debugger.debug(
            f"Dummy Streamer fake fetch option market data price for {symbol}: {price}"
        )

        return {
            "price": price,
            "ask": price * 1.05,
            "bid": price * 0.95,
        }

    # Not implemented functions:
    #   fetch_chain_info
    #   fetch_chain_data

    # ------------- Broker methods ------------- #

    # Not implemented functions:
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

    # Not implemented functions:
    #   order_stock_limit
    #   order_crypto_limit
    #   order_option_limit

    # ------------- Helper methods ------------- #

    def _generate_history(
        self, symbol: str, start: dt.datetime, end: dt.datetime
    ) -> pd.DataFrame:
        # Convert datetime to indices
        start_index = int((start - epoch_zero()).total_seconds() // 60)
        end_index = 1 + int((end - epoch_zero()).total_seconds() // 60)

        if symbol in self.randomness:
            # If we already generated data from this asset

            num_of_random = 1 + end_index

            if len(self.randomness[symbol]) < num_of_random:
                # If the new end index is greater than the data we have

                # Get the rng for this symbol
                rng = self.randomness[symbol + "_rng"]

                # Update the number of random data points
                num_of_random -= len(self.randomness[symbol])

                # Generate a bunch of random numbers using Geometric Brownian Motion
                returns = (
                    rng.normal(loc=0.0001, scale=0.0001, size=num_of_random)
                    - rng.random(num_of_random) / 500.0
                )

                # Calculate the change in price since the first price
                new_price_changes = np.append(
                    self.randomness[symbol], 1 + returns
                ).cumprod()

                # Store the new prices
                self.randomness[symbol] = np.append(
                    self.randomness[symbol], new_price_changes
                )

        else:
            # If there is no information about the asset

            # Create an rng using the asset's symbol as a seed
            rng = np.random.default_rng(int.from_bytes(symbol.encode("ascii"), "big"))
            num_of_random = 1 + end_index

            # Generate a bunch of random numbers using Geometric Brownian Motion
            returns = (
                rng.normal(loc=0.0001, scale=0.0001, size=num_of_random)
                - rng.random(num_of_random) / 500.0
            )

            # Store the price change since the first price
            self.randomness[symbol] = (1 + returns).cumprod()
            self.randomness[symbol + "_rng"] = rng

        # The inital price is arbitarly calculated from the first change in price
        start_price = 1000 * (self.randomness[symbol][0] + 0.501)

        times = []
        current_time = start

        # Get the prices for the current interval
        prices = start_price * self.randomness[symbol][start_index:end_index]
        # Prevent prices from going negative
        prices[prices < 0] = 0.01

        # Calculate olhcv from the prices
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

        results = pd.DataFrame(data=d).set_index("timestamp")
        return results
