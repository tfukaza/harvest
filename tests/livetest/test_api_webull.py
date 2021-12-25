# Builtins
import pathlib
import unittest
import datetime as dt
import os

from harvest.api.paper import PaperBroker
from harvest.api.webull import Webull
from harvest.utils import not_gh_action
from harvest.utils import *


class TestWebull(unittest.TestCase):
    def test_setup(self):
        """
        Assuming that secret.yml is already created with proper parameters,
        test if the broker can read its contents and establish a connection with the server.
        """
        wb = Webull()
        interval = {
            "@DOGE": {"interval": Interval.MIN_1, "aggregations": []},
            "TWTR": {"interval": Interval.MIN_1, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        wb.setup(stats, Account())

    def test_fetch_prices(self):
        """
        Test if price history can be properly fetched for every interval supported
        """

        wb = Webull()
        intervals = wb.interval_list
        interval = {
            "@DOGE": {"interval": intervals[0], "aggregations": intervals[1:]},
            "TWTR": {"interval": intervals[0], "aggregations": intervals[1:]},
        }
        stats = Stats(watchlist_cfg=interval)
        wb.setup(stats, Account())

        for i in intervals:
            df = wb.fetch_price_history("TWTR", interval=i)["TWTR"]
            self.assertEqual(
                sorted(list(df.columns.values)),
                sorted(["open", "high", "low", "close", "volume"]),
            )
            df = wb.fetch_price_history("@DOGE", interval=i)["@DOGE"]
            self.assertEqual(
                sorted(list(df.columns.values)),
                sorted(["open", "high", "low", "close", "volume"]),
            )

    def test_main(self):
        def test_main(df):
            self.assertEqual(len(df), 2)

        wb = Webull()
        interval = {
            "@DOGE": {"interval": Interval.MIN_5, "aggregations": []},
            "TWTR": {"interval": Interval.MIN_5, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        wb.setup(stats, Account(), test_main)
        stats.timestamp = epoch_zero()
        wb.main()

    def test_chain_info(self):

        wb = Webull()
        interval = {"TWTR": {"interval": Interval.MIN_1, "aggregations": []}}
        stats = Stats(watchlist_cfg=interval)
        wb.setup(stats, Account())

        info = wb.fetch_chain_info("TWTR")
        self.assertGreater(len(info["exp_dates"]), 0)

    def test_chain_data(self):

        wb = Webull()
        interval = {"TWTR": {"interval": Interval.MIN_1, "aggregations": []}}
        stats = Stats(watchlist_cfg=interval)
        wb.setup(stats, Account())

        dates = wb.fetch_chain_info("TWTR")["exp_dates"]
        data = wb.fetch_chain_data("TWTR", dates[0])
        self.assertGreater(len(data), 0)
        self.assertListEqual(list(data.columns), ["exp_date", "strike", "type", "id"])
        sym = data.index[0]
        df = wb.fetch_option_market_data(sym)
        self.assertTrue(True)

    def test_order_option_limit(self):

        wb = Webull()
        interval = {"TWTR": {"interval": Interval.MIN_1, "aggregations": []}}
        stats = Stats(watchlist_cfg=interval)
        wb.setup(stats, Account())

        dates = wb.fetch_chain_info("TWTR")["exp_dates"]
        data = wb.fetch_chain_data("TWTR", dates[0])
        option = data.iloc[0]

        exp_date = option["exp_date"]
        strike = option["strike"]

        ret = wb.order_option_limit("buy", "TWTR", 1, 0.01, "call", exp_date, strike)

        time.sleep(5)

        wb.cancel_option_order(ret["order_id"])
        # self.assertEqual(order["order_id"], 0)
        # self.assertEqual(order["symbol"], "A")

    # def test_sell(self):
    #     paper = PaperBroker()
    #     paper.streamer = Webull()
    #     interval = {"A": {"interval": Interval.MIN_1, "aggregations": []}}
    #     paper.setup(interval)
    #     order = paper.sell("A", 2)
    #     self.assertEqual(order["type"], "STOCK")
    #     self.assertEqual(order["id"], 0)
    #     self.assertEqual(order["symbol"], "A")

    # @not_gh_action
    # def test_sell_order_limit(self):
    #     paper = PaperBroker()
    #     paper.streamer = Webull()
    #     interval = {"A": {"interval": Interval.MIN_1, "aggregations": []}}
    #     paper.setup(interval)
    #     order = paper.order_limit("sell", "A", 2, 50000)
    #     self.assertEqual(order["type"], "STOCK")
    #     self.assertEqual(order["id"], 0)
    #     self.assertEqual(order["symbol"], "A")

    def test_buy_stock(self):
        wb = Webull()
        interval = {"TWTR": {"interval": Interval.MIN_5, "aggregations": []}}
        stats = Stats(watchlist_cfg=interval)
        wb.setup(stats, Account())

        ret = wb.order_stock_limit("buy", "TWTR", 1, 10.0)
        self.assertEqual(ret["order_id"], 0)
        self.assertEqual(ret["symbol"], "TWTR")

        time.sleep(5)

        wb.cancel_stock_order(ret["order_id"])

    # @not_gh_action
    # def test_buy_order_limit(self):
    #     paper = PaperBroker()
    #     paper.streamer = Webull()
    #     interval = {"A": {"interval": Interval.MIN_1, "aggregations": []}}
    #     paper.setup(interval)
    #     order = paper.order_limit("buy", "A", 5, 50000)
    #     self.assertEqual(order["type"], "STOCK")
    #     self.assertEqual(order["id"], 0)
    #     self.assertEqual(order["symbol"], "A")


if __name__ == "__main__":
    unittest.main()
