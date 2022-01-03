import unittest
from harvest.api.alpaca import Alpaca

from harvest.utils import *
import datetime as dt
import time
import os

secret_path = os.environ["SECRET_PATH"]
debugger.setLevel("DEBUG")

class TestLiveAlpaca(unittest.TestCase):
    def test_fetch_stock_prices(self):
        """
        Test if stock price history can be properly fetched for every interval supported
        """
        api = Alpaca(secret_path, is_basic_account=True, paper_trader=True)
        intervals = api.interval_list

        interval = {
            "TWTR": {"interval": intervals[0], "aggregations": intervals[1:]},
        }
        stats = Stats(watchlist_cfg=interval)
        api.setup(stats, Account()) 

        for i in intervals:
            df = api.fetch_price_history("TWTR", interval=i, start=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=100))
            debugger.debug(f"{api} fetch_price_history TWTR {i} returned {df}")
            df = df["TWTR"]
            self.assertEqual(
                sorted(list(df.columns.values)),
                sorted(["open", "high", "low", "close", "volume"]),
            )

    def test_fetch_crypto_prices(self):
        """
        Test if crypro price history can be properly fetched for every interval supported
        """
        api = Alpaca(secret_path)
        intervals = api.interval_list
        interval = {
            "@BTC": {"interval": intervals[0], "aggregations": intervals[1:]},
        }
        stats = Stats(watchlist_cfg=interval)
        api.setup(stats, Account())

        for i in intervals:
            df = api.fetch_price_history("@BTC", interval=i, start=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=100))
            debugger.debug(f"{api} fetch_price_history @BTC {i} returned {df}")
            df = df["@BTC"]
            self.assertEqual(
                sorted(list(df.columns.values)),
                sorted(["open", "high", "low", "close", "volume"]),
            )

    def test_main_mix(self):
        """
        Test if latest prices can be fetched when there are both
        crypto and stock assets specified in the watchlist.
        """

        api = Alpaca(secret_path)

        def test_main(df):
            self.assertEqual(len(df), 2)

        interval = {
            "TWTR": {"interval": Interval.MIN_5, "aggregations": []},
            "@BTC": {"interval": Interval.MIN_5, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        api.setup(stats, Account(), test_main)

        # Override timestamp to ensure is_freq() evaluates to True
        stats.timestamp = epoch_zero()
        api.main()


if __name__ == "__main__":
    unittest.main()
