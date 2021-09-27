# Builtins
import pathlib
import unittest
import datetime as dt
import os

from harvest.utils import not_gh_action
from harvest.api.paper import PaperBroker
from harvest.api.dummy import DummyStreamer
from harvest.api.webull import Webull
from harvest.utils import *


class TestWebull(unittest.TestCase):
    def not_gh_action(func):
        def wrapper(*args, **kwargs):
            if "GITHUB_ACTION" in os.environ:
                return
            func(*args, **kwargs)

        return wrapper

    @not_gh_action
    def test_fetch_prices(self):
        wb = Webull()
        interval = {
            "@BTC": {"interval": Interval.MIN_1, "aggregations": []},
            "SPY": {"interval": Interval.MIN_1, "aggregations": []},
        }
        wb.setup(interval)
        df = wb.fetch_price_history("SPY", interval=Interval.MIN_1)["SPY"]
        self.assertEqual(
            sorted(list(df.columns.values)),
            sorted(["open", "high", "low", "close", "volume"]),
        )
        df = wb.fetch_price_history("BTC", interval=Interval.MIN_1)["BTC"]
        self.assertEqual(
            sorted(list(df.columns.values)),
            sorted(["open", "high", "low", "close", "volume"]),
        )

    @not_gh_action
    def test_setup(self):
        wb = Webull()
        watch = ["SPY", "@BTC"]
        interval = {
            "@BTC": {"interval": Interval.MIN_1, "aggregations": []},
            "SPY": {"interval": Interval.MIN_1, "aggregations": []},
        }
        wb.setup(interval)
        self.assertEqual(wb.watch_stock, ["SPY"])
        self.assertEqual(wb.watch_crypto, ["@BTC"])

    @not_gh_action
    def test_main(self):
        def test_main(df):
            self.assertEqual(len(df), 2)
            self.assertEqual(df["SPY"].columns[0][0], "SPY")
            self.assertEqual(df["@BTC"].columns[0][0], "@BTC")

        wb = Webull()
        watch = ["SPY", "@BTC"]
        interval = {
            "@BTC": {"interval": Interval.MIN_1, "aggregations": []},
            "SPY": {"interval": Interval.MIN_1, "aggregations": []},
        }
        wb.setup(interval, None, test_main)
        wb.main()

    @not_gh_action
    def test_main_single(self):
        def test_main(df):
            self.assertEqual(len(df), 1)
            self.assertEqual(df["SPY"].columns[0][0], "SPY")

        wb = Webull()
        watch = ["SPY"]
        interval = {"SPY": {"interval": Interval.MIN_1, "aggregations": []}}
        wb.setup(interval, None, test_main)
        wb.main()

    @not_gh_action
    def test_chain_info(self):
        wb = Webull()
        watch = ["SPY"]
        interval = {"SPY": {"interval": Interval.MIN_1, "aggregations": []}}
        wb.setup(interval)
        info = wb.fetch_chain_info("SPY")
        self.assertGreater(len(info["exp_dates"]), 0)

    @not_gh_action
    def test_chain_data(self):
        wb = Webull()
        watch = ["LMND"]
        interval = {"LMND": {"interval": Interval.MIN_1, "aggregations": []}}
        wb.setup(interval)
        dates = wb.fetch_chain_info("LMND")["exp_dates"]
        data = wb.fetch_chain_data("LMND", dates[0])
        self.assertGreater(len(data), 0)
        self.assertListEqual(list(data.columns), ["exp_date", "strike", "type", "id"])
        sym = data.index[0]
        df = wb.fetch_option_market_data(sym)
        self.assertTrue(True)

    @not_gh_action
    def test_order_option_limit(self):
        dummy = PaperBroker()
        dummy.streamer = Webull()
        interval = {"A": {"interval": Interval.MIN_1, "aggregations": []}}
        dummy.setup(interval)
        exp_date = dt.datetime.now() + dt.timedelta(hours=5)
        order = dummy.order_option_limit(
            "buy", "A", 5, 50000, "OPTION", exp_date, 50001
        )
        self.assertEqual(order["type"], "OPTION")
        self.assertEqual(order["id"], 0)
        self.assertEqual(order["symbol"], "A")

    @not_gh_action
    def test_sell(self):
        dummy = PaperBroker()
        dummy.streamer = Webull()
        interval = {"A": {"interval": Interval.MIN_1, "aggregations": []}}
        dummy.setup(interval)
        order = dummy.sell("A", 2)
        self.assertEqual(order["type"], "STOCK")
        self.assertEqual(order["id"], 0)
        self.assertEqual(order["symbol"], "A")

    @not_gh_action
    def test_sell_order_limit(self):
        dummy = PaperBroker()
        dummy.streamer = Webull()
        interval = {"A": {"interval": Interval.MIN_1, "aggregations": []}}
        dummy.setup(interval)
        order = dummy.order_limit("sell", "A", 2, 50000)
        self.assertEqual(order["type"], "STOCK")
        self.assertEqual(order["id"], 0)
        self.assertEqual(order["symbol"], "A")

    @not_gh_action
    def test_buy(self):
        dummy = PaperBroker()
        dummy.streamer = Webull()
        interval = {"A": {"interval": Interval.MIN_1, "aggregations": []}}
        dummy.setup(interval)
        order = dummy.buy("A", 5)
        self.assertEqual(order["type"], "STOCK")
        self.assertEqual(order["id"], 0)
        self.assertEqual(order["symbol"], "A")

    @not_gh_action
    def test_buy_order_limit(self):
        dummy = PaperBroker()
        dummy.streamer = Webull()
        interval = {"A": {"interval": Interval.MIN_1, "aggregations": []}}
        dummy.setup(interval)
        order = dummy.order_limit("buy", "A", 5, 50000)
        self.assertEqual(order["type"], "STOCK")
        self.assertEqual(order["id"], 0)
        self.assertEqual(order["symbol"], "A")


if __name__ == "__main__":
    unittest.main()
