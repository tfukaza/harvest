import unittest
from harvest.api.robinhood import Robinhood
from harvest.api.paper import PaperBroker
from harvest.utils import *
import time
import os

secret_path = os.environ["SECRET_PATH"]
debugger.setLevel("DEBUG")


class TestLiveRobinhood(unittest.TestCase):
    def test_setup(self):
        """
        Assuming that secret.yml is already created with proper parameters,
        test if the broker can read its contents and establish a connection with the server.
        """
        rh = Robinhood(secret_path)
        interval = {
            "@DOGE": {"interval": Interval.MIN_5, "aggregations": []},
            "TWTR": {"interval": Interval.MIN_5, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        rh.setup(stats, Account())
        self.assertTrue(True)

    def test_fetch_prices(self):
        """
        Test if price history can be properly fetched for every interval supported
        """
        rh = Robinhood(secret_path)
        intervals = rh.interval_list
        interval = {
            "TWTR": {"interval": intervals[0], "aggregations": intervals[1:]},
            "@DOGE": {"interval": intervals[0], "aggregations": intervals[1:]},
        }
        stats = Stats(watchlist_cfg=interval)
        rh.setup(stats, Account())

        for i in intervals:
            df = rh.fetch_price_history("TWTR", interval=i)["TWTR"]
            self.assertEqual(
                sorted(list(df.columns.values)),
                sorted(["open", "high", "low", "close", "volume"]),
            )
            df = rh.fetch_price_history("@DOGE", interval=i)["@DOGE"]
            self.assertEqual(
                sorted(list(df.columns.values)),
                sorted(["open", "high", "low", "close", "volume"]),
            )

    def test_main(self):
        """
        Test if latest prices can be fetched.
        """

        def test_main(df):
            self.assertEqual(len(df), 2)

        rh = Robinhood(secret_path)
        interval = {
            "TWTR": {"interval": Interval.MIN_5, "aggregations": []},
            "@DOGE": {"interval": Interval.MIN_5, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        rh.setup(stats, Account(), test_main)

        # Override timestamp to ensure is_freq() evaluates to True
        stats.timestamp = epoch_zero()
        rh.main()

    def test_chain_info(self):
        """
        Test if chain info can be fetched
        """
        rh = Robinhood(secret_path)
        interval = {
            "TWTR": {"interval": Interval.MIN_5, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        rh.setup(stats, Account())

        info = rh.fetch_chain_info("TWTR")
        self.assertGreater(len(info["exp_dates"]), 0)

    def test_chain_data(self):
        """
        Test if chain data can be fetched
        """
        rh = Robinhood(secret_path)
        interval = {
            "TWTR": {"interval": Interval.MIN_5, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        rh.setup(stats, Account())

        dates = rh.fetch_chain_info("TWTR")["exp_dates"]
        data = rh.fetch_chain_data("TWTR", dates[0])

        self.assertGreater(len(data), 0)
        self.assertListEqual(list(data.columns), ["exp_date", "strike", "type"])

        sym = data.index[0]
        df = rh.fetch_option_market_data(sym)
        self.assertTrue(True)

    def test_buy_option(self):
        rh = Robinhood(secret_path)
        interval = {
            "TWTR": {"interval": Interval.MIN_5, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        rh.setup(stats, Account())

        # Get a list of all options
        dates = rh.fetch_chain_info("TWTR")["exp_dates"]
        data = rh.fetch_chain_data("TWTR", dates[0])
        option = data.iloc[0]

        exp_date = option["exp_date"]
        strike = option["strike"]

        ret = rh.order_option_limit("buy", "TWTR", 1, 0.01, "call", exp_date, strike)

        time.sleep(5)

        rh.cancel_option_order(ret["order_id"])

        self.assertTrue(True)

    def test_buy_stock(self):
        """
        Test that it can buy stocks
        """
        rh = Robinhood(secret_path)
        interval = {
            "TWTR": {"interval": Interval.MIN_5, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        rh.setup(stats, Account())

        # Limit order TWTR stock at an extremely low limit price
        # to ensure the order is not actually filled.
        ret = rh.order_stock_limit("buy", "TWTR", 1, 10.0)

        time.sleep(5)

        rh.cancel_stock_order(ret["order_id"])


if __name__ == "__main__":
    unittest.main()
