import datetime as dt
import os
import unittest

from harvest.broker.robinhood import RobinhoodBroker
from harvest.broker.yahoo import YahooBroker
from harvest.definitions import Account, Interval, Stats
from harvest.util.helper import debugger, utc_epoch_zero

secret_path = os.environ["SECRET_PATH"]
debugger.setLevel("DEBUG")

import functools


# A decorator to repeat the same test for all the brokers
def decorator_repeat_test(api_list):
    def decorator_test(func):
        @functools.wraps(func)
        def wrapper_repeat(*args):
            self = args[0]
            for api in api_list:
                print(f"Testing {api}")
                func(self, api)

        return wrapper_repeat

    return decorator_test


class TestLiveStreamer(unittest.TestCase):
    @decorator_repeat_test([RobinhoodBroker, YahooBroker])
    def test_setup(self, api):
        """
        Assuming that secret.yml is already created with proper parameters, test if the broker can read its contents and establish a connection with the server.
        """
        api = api(secret_path)
        interval = {
            "@DOGE": {"interval": Interval.MIN_5, "aggregations": []},
            "TWTR": {"interval": Interval.MIN_5, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        api.setup(stats, Account())
        self.assertTrue(True)

    @decorator_repeat_test([RobinhoodBroker, YahooBroker])
    def test_fetch_stock_prices(self, api):
        """
        Test if stock price history can be properly fetched for every interval supported
        """
        api = api(secret_path)
        intervals = api.interval_list
        if isinstance(api, RobinhoodBroker):
            intervals = intervals[1:]

        interval = {
            "TWTR": {"interval": intervals[0], "aggregations": intervals[1:]},
        }
        stats = Stats(watchlist_cfg=interval)
        api.setup(stats, Account())

        for i in intervals:
            df = api.fetch_price_history("TWTR", interval=i)
            debugger.debug(f"{api} fetch_price_history TWTR {i} returned {df}")
            df = df["TWTR"]
            self.assertEqual(
                sorted(list(df.columns.values)),
                sorted(["open", "high", "low", "close", "volume"]),
            )

    @decorator_repeat_test([RobinhoodBroker, YahooBroker])
    def test_fetch_crypto_prices(self, api):
        """
        Test if crypro price history can be properly fetched for every interval supported
        """
        api = api(secret_path)
        intervals = api.interval_list
        interval = {
            "@DOGE": {"interval": intervals[0], "aggregations": intervals[1:]},
        }
        stats = Stats(watchlist_cfg=interval)
        api.setup(stats, Account())

        for i in intervals:
            df = api.fetch_price_history("@DOGE", interval=i)
            debugger.debug(f"{api} fetch_price_history @DOGE {i} returned {df}")
            df = df["@DOGE"]
            self.assertEqual(
                sorted(list(df.columns.values)),
                sorted(["open", "high", "low", "close", "volume"]),
            )

    @decorator_repeat_test([RobinhoodBroker, YahooBroker])
    def test_main_mix(self, api):
        """
        Test if latest prices can be fetched when there are both
        crypto and stock assets specified in the watchlist.
        """

        api = api(secret_path)

        def test_main(df):
            self.assertEqual(len(df), 2)

        interval = {
            "TWTR": {"interval": Interval.MIN_5, "aggregations": []},
            "@DOGE": {"interval": Interval.MIN_5, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        api.setup(stats, Account(), test_main)

        # Override timestamp to ensure is_freq() evaluates to True
        stats.timestamp = utc_epoch_zero()
        api.main()

    @decorator_repeat_test([RobinhoodBroker, YahooBroker])
    def test_chain_info(self, api):
        """
        Test if chain info can be fetched
        """
        api = api(secret_path)
        interval = {
            "TWTR": {"interval": Interval.MIN_5, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        api.setup(stats, Account())

        info = api.fetch_chain_info("TWTR")
        debugger.debug(f"{api} fetch_chain_info TWTR returned {info}")
        self.assertGreater(len(info["exp_dates"]), 0)

    @decorator_repeat_test([RobinhoodBroker, YahooBroker])
    def test_chain_data(self, api):
        """
        Test if chain data can be fetched
        """
        api = api(secret_path)
        interval = {
            "TWTR": {"interval": Interval.MIN_5, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        api.setup(stats, Account())

        dates = api.fetch_chain_info("TWTR")["exp_dates"]
        data = api.fetch_chain_data("TWTR", dates[0])

        debugger.debug(f"{api} fetch_chain_data TWTR {dates[0]} returned {data}")

        self.assertGreater(len(data), 0)
        self.assertListEqual(list(data.columns), ["exp_date", "strike", "type"])

    @decorator_repeat_test([RobinhoodBroker, YahooBroker])
    def test_option_market_data(self, api):
        api = api(secret_path)
        interval = {
            "TWTR": {"interval": Interval.MIN_5, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        api.setup(stats, Account())

        dates = api.fetch_chain_info("TWTR")["exp_dates"]
        data = api.fetch_chain_data("TWTR", dates[0])
        sym = data.index[0]
        df = api.fetch_option_market_data(sym)
        debugger.debug(f"{api} fetch_option_market_data {sym} returned {df}")
        self.assertTrue(True)

    @decorator_repeat_test([RobinhoodBroker, YahooBroker])
    def test_fetch_market_hours(self, api):
        """
        Test if market hours can be fetched
        """
        api = api(secret_path)
        interval = {
            "TWTR": {"interval": Interval.MIN_5, "aggregations": []},
            "@DOGE": {"interval": Interval.MIN_5, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        api.setup(stats, Account())

        data = api.fetch_market_hours(dt.datetime.now().date())
        debugger.debug(f"{api} fetch_market_hours returned {data}")
        self.assertTrue("is_open" in data)
        if data["is_open"]:
            self.assertIsInstance(data["open_at"], dt.datetime)
            self.assertIsInstance(data["close_at"], dt.datetime)
        else:
            self.assertIsNone(data["open_at"])
            self.assertIsNone(data["close_at"])


if __name__ == "__main__":
    unittest.main()
