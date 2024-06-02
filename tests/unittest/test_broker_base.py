import datetime as dt
import unittest
from functools import wraps
from unittest import mock

import pandas as pd
from _util import mock_get_local_timezone, mock_utc_current_time

from harvest.definitions import Account, Stats
from harvest.enum import Interval
from harvest.util.helper import debugger

debugger.setLevel("DEBUG")

"""
For testing purposes, assume:
- Current day is September 15th, 2008
- Current time is 10:00 AM
- Current timezone is US/Eastern
"""


def repeat_test(broker_list):
    def decorator_test(func):
        @wraps(func)
        def wrapper_repeat(*args):
            self = args[0]
            for broker in broker_list:
                print(f"Testing {broker}")
                func(self, broker)

        return wrapper_repeat

    return decorator_test


class TestBroker(object):
    """
    Base class for testing Broker implementations.
    Each brokers should inherit from this class and implement the necessary
    setup and teardown procedures specific to the broker, and call the code
    in this class to test the common functionalities.

    """

    def _define_patch(self, path, side_effect):
        patcher = mock.patch(path)
        func = patcher.start()
        func.side_effect = side_effect
        self.addCleanup(patcher.stop)

    def setUp(self):
        self._define_patch("harvest.util.date.get_local_timezone", mock_get_local_timezone)
        self._define_patch("harvest.util.date.utc_current_time", mock_utc_current_time)

    def test_fetch_stock_price(self, broker):
        """
        Test fetching stock price history
        The returned DataFrame should be in the format:
                    [Ticker]
                    open  high   low  close  volume
        timestamp

        Where timestamp is a pandas datetime object in UTC timezone,
        and open, high, low, close, and volume are float values.
        """

        broker = broker()

        end = mock_utc_current_time()
        start = end - dt.timedelta(days=1)
        results = broker.fetch_price_history("AAPL", Interval.MIN_1, start, end)
        # Check that the returned DataFrame is not empty
        self.assertGreaterEqual(len(results), 1)
        self.assertTrue(results.shape[1] == 5)
        # Check that the returned DataFrame has the correct columns
        self.assertListEqual(
            list(results.columns),
            [("AAPL", "open"), ("AAPL", "high"), ("AAPL", "low"), ("AAPL", "close"), ("AAPL", "volume")],
        )
        # Check that the returned DataFrame has the correct index
        self.assertTrue(results.index[0] >= start)
        self.assertTrue(results.index[-1] <= end)
        # Check that the returned DataFrame has the correct data types
        self.assertEqual(results.dtypes["AAPL", "open"], float)
        self.assertEqual(results.dtypes["AAPL", "high"], float)
        self.assertEqual(results.dtypes["AAPL", "low"], float)
        self.assertEqual(results.dtypes["AAPL", "close"], float)
        self.assertEqual(results.dtypes["AAPL", "volume"], float)

        # Check that the returned DataFrame has the correct index type
        self.assertEqual(type(results.index[0]), pd.Timestamp)
        self.assertEqual(results.index.tzinfo, dt.timezone.utc)

    def test_fetch_stock_price_timezone(self, broker):
        """
        Test that the price history returned
        correctly adjusts the input to utc timezone.
        """
        broker = broker()

        # Create an end date in ETC timezone
        end = dt.datetime(2008, 9, 15, 10, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=-4)))
        start = end - dt.timedelta(days=1)
        results = broker.fetch_price_history("AAPL", Interval.MIN_1, start, end)

        # The last timestamp in the returned DataFrame should be 4 hours ahead of the end date,
        # since UTC-0 is 4 hours ahead of UTC-4
        self.assertEqual(results.index[-1], end.astimezone(dt.timezone.utc))

    def test_fetch_stock_price_str_input(self, broker):
        """
        Test fetching stock price history using Yahoo Broker
        with string input for start and end dates.
        As with datetime objects, time is converted from local timezone to UTC.
        """
        broker = broker()
        # Use ISO 8601 string for start and end
        start = "2008-09-15T09:00"
        end = "2008-09-15T10:00"
        results = broker.fetch_price_history("AAPL", Interval.MIN_1, start, end)
        self.assertEqual(type(results.index[0]), pd.Timestamp)
        self.assertEqual(results.index.tzinfo, dt.timezone.utc)
        self.assertEqual(results.index[-1], dt.datetime(2008, 9, 15, 14, 0, 0, tzinfo=dt.timezone.utc))

    def test_setup(self, broker):
        """
        Test that the broker is correctly set up with the stats and account objects.
        """
        broker = broker()
        interval = {
            "SPY": {"interval": Interval.MIN_15, "aggregations": []},
            "AAPL": {"interval": Interval.MIN_1, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        broker.setup(stats, Account())

        self.assertEqual(broker.poll_interval, Interval.MIN_1)
        self.assertListEqual(list(broker.stats.watchlist_cfg.keys()), ["SPY", "AAPL"])

    def test_main(self, broker):
        """
        Test that the main function is called with the correct security data.
        """
        interval = {
            "SPY": {"interval": Interval.MIN_1, "aggregations": []},
            "AAPL": {"interval": Interval.MIN_1, "aggregations": []},
            "@BTC": {"interval": Interval.MIN_1, "aggregations": []},
        }

        def test_main(df):
            self.assertEqual(len(df), 3)
            self.assertEqual(df["SPY"].columns[0][0], "SPY")
            self.assertEqual(df["AAPL"].columns[0][0], "AAPL")
            self.assertEqual(df["@BTC"].columns[0][0], "@BTC")

        broker = broker()

        stats = Stats(watchlist_cfg=interval)
        broker.setup(stats, Account(), test_main)

        # Call the main function
        broker.step()

    def test_chain_info(self, broker):
        broker = broker()

        interval = {"SPY": {"interval": Interval.MIN_1, "aggregations": []}}
        stats = Stats(watchlist_cfg=interval)
        broker.setup(stats, Account())

        info = broker.fetch_chain_info("SPY")

        self.assertGreater(len(info["exp_dates"]), 0)

    def test_chain_data(self, broker):
        broker = broker()

        interval = {"SPY": {"interval": Interval.MIN_1, "aggregations": []}}
        stats = Stats(watchlist_cfg=interval)
        broker.setup(stats, Account())

        dates = broker.fetch_chain_info("SPY")
        print(dates)
        dates = dates["exp_dates"]
        chain = broker.fetch_chain_data("SPY", dates[0])
        self.assertGreater(len(chain), 0)
        self.assertListEqual(list(chain.columns), ["exp_date", "strike", "type"])

        print(chain)

        # TODO test getting market data

    # def test_buy_option(self, api):
    #     api = api(secret_path)
    #     interval = {
    #         "TWTR": {"interval": Interval.MIN_5, "aggregations": []},
    #     }
    #     stats = Stats(watchlist_cfg=interval)
    #     api.setup(stats, Account())

    #     # Get a list of all options
    #     dates = api.fetch_chain_info("TWTR")["exp_dates"]
    #     data = api.fetch_chain_data("TWTR", dates[1])
    #     option = data.iloc[0]

    #     exp_date = option["exp_date"]
    #     strike = option["strike"]

    #     ret = api.order_option_limit("buy", "TWTR", 1, 0.01, "call", exp_date, strike)

    #     time.sleep(5)

    #     api.cancel_option_order(ret["order_id"])

    #     self.assertTrue(True)

    # def test_buy_stock(self, api):
    #     """
    #     Test that it can buy stocks
    #     """
    #     api = api(secret_path)
    #     interval = {
    #         "TWTR": {"interval": Interval.MIN_5, "aggregations": []},
    #     }
    #     stats = Stats(watchlist_cfg=interval)
    #     api.setup(stats, Account())

    #     # Limit order TWTR stock at an extremely low limit price
    #     # to ensure the order is not actually filled.
    #     ret = api.order_stock_limit("buy", "TWTR", 1, 10.0)

    #     time.sleep(5)

    #     api.cancel_stock_order(ret["order_id"])

    # def test_buy_crypto(self, api):
    #     """
    #     Test that it can buy crypto
    #     """
    #     api = api(secret_path)
    #     interval = {
    #         "@DOGE": {"interval": Interval.MIN_5, "aggregations": []},
    #     }
    #     stats = Stats(watchlist_cfg=interval)
    #     api.setup(stats, Account())

    #     # Limit order DOGE at an extremely low limit price
    #     # to ensure the order is not actually filled.
    #     ret = api.order_crypto_limit("buy", "@DOGE", 1, 0.10)

    #     time.sleep(5)

    #     api.cancel_crypto_order(ret["order_id"])


if __name__ == "__main__":
    unittest.main()
