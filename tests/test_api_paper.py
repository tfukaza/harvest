# Builtins
import pathlib
import unittest
import datetime as dt

from harvest.api.paper import PaperBroker
from harvest.api.dummy import DummyStreamer

from harvest.utils import *


class TestPaperBroker(unittest.TestCase):
    def test_account(self):
        dummy = PaperBroker()
        d = dummy.fetch_account()
        self.assertEqual(d["equity"], 1000000.0)
        self.assertEqual(d["cash"], 1000000.0)
        self.assertEqual(d["buying_power"], 1000000.0)
        self.assertEqual(d["multiplier"], 1)

    def test_dummy_account(self):
        directory = pathlib.Path(__file__).parent.resolve()
        dummy = PaperBroker(str(directory) + "/../dummy_account.yaml")
        stocks = dummy.fetch_stock_positions()
        self.assertEqual(len(stocks), 2)
        self.assertEqual(stocks[0]["symbol"], "A")
        self.assertEqual(stocks[0]["avg_price"], 1.0)
        self.assertEqual(stocks[0]["quantity"], 5)

        cryptos = dummy.fetch_crypto_positions()
        self.assertEqual(len(cryptos), 1)
        self.assertEqual(cryptos[0]["symbol"], "@C")
        self.assertEqual(cryptos[0]["avg_price"], 289.21)
        self.assertEqual(cryptos[0]["quantity"], 2)

    def test_buy_order_limit(self):
        dummy = PaperBroker()
        interval = {"A": {"interval": Interval.MIN_1, "aggregations": []}}
        stats = Stats(interval=interval)
        dummy.setup(stats)
        order = dummy.order_stock_limit("buy", "A", 5, 50000)
        self.assertEqual(order["type"], "STOCK")
        self.assertEqual(order["id"], 0)
        self.assertEqual(order["symbol"], "A")

        status = dummy.fetch_stock_order_status(order["id"])
        self.assertEqual(status["id"], 0)
        self.assertEqual(status["symbol"], "A")
        self.assertEqual(status["quantity"], 5)
        self.assertEqual(status["filled_qty"], 5)
        self.assertEqual(status["side"], "buy")
        self.assertEqual(status["time_in_force"], "gtc")
        self.assertEqual(status["status"], "filled")

    def test_buy(self):
        dummy = PaperBroker()
        interval = {"A": {"interval": Interval.MIN_1, "aggregations": []}}
        stats = Stats(interval=interval)
        dummy.setup(stats)
        order = dummy.buy("A", 5, 1e5)
        self.assertEqual(order["type"], "STOCK")
        self.assertEqual(order["id"], 0)
        self.assertEqual(order["symbol"], "A")

        status = dummy.fetch_stock_order_status(order["id"])
        self.assertEqual(status["id"], 0)
        self.assertEqual(status["symbol"], "A")
        self.assertEqual(status["quantity"], 5)
        self.assertEqual(status["filled_qty"], 5)
        self.assertEqual(status["side"], "buy")
        self.assertEqual(status["time_in_force"], "gtc")
        self.assertEqual(status["status"], "filled")

    def test_sell_order_limit(self):
        directory = pathlib.Path(__file__).parent.resolve()
        dummy = PaperBroker(str(directory) + "/../dummy_account.yaml")

        interval = {"A": {"interval": Interval.MIN_1, "aggregations": []}}
        stats = Stats(interval=interval)
        dummy.setup(stats)

        order = dummy.order_stock_limit("sell", "A", 2, 50000)
        self.assertEqual(order["type"], "STOCK")
        self.assertEqual(order["id"], 0)
        self.assertEqual(order["symbol"], "A")

        status = dummy.fetch_stock_order_status(order["id"])
        self.assertEqual(status["id"], 0)
        self.assertEqual(status["symbol"], "A")
        self.assertEqual(status["quantity"], 2)
        self.assertEqual(status["filled_qty"], 2)
        self.assertEqual(status["side"], "sell")
        self.assertEqual(status["time_in_force"], "gtc")
        self.assertEqual(status["status"], "filled")

    def test_sell(self):
        directory = pathlib.Path(__file__).parent.resolve()
        dummy = PaperBroker(str(directory) + "/../dummy_account.yaml")

        interval = {"A": {"interval": Interval.MIN_1, "aggregations": []}}
        stats = Stats(interval=interval)
        dummy.setup(stats)

        order = dummy.sell("A", 2)
        self.assertEqual(order["type"], "STOCK")
        self.assertEqual(order["id"], 0)
        self.assertEqual(order["symbol"], "A")

        status = dummy.fetch_stock_order_status(order["id"])
        self.assertEqual(status["id"], 0)
        self.assertEqual(status["symbol"], "A")
        self.assertEqual(status["quantity"], 2)
        self.assertEqual(status["filled_qty"], 2)
        self.assertEqual(status["side"], "sell")
        self.assertEqual(status["time_in_force"], "gtc")
        self.assertEqual(status["status"], "filled")

    def test_order_option_limit(self):
        dummy = PaperBroker()

        interval = {"A": {"interval": Interval.MIN_1, "aggregations": []}}
        stats = Stats(interval=interval)
        dummy.setup(stats)

        exp_date = dt.datetime(2021, 11, 14) + dt.timedelta(hours=5)
        order = dummy.order_option_limit(
            "buy", "A", 5, 50000, "OPTION", exp_date, 50001
        )
        self.assertEqual(order["type"], "OPTION")
        self.assertEqual(order["id"], 0)
        self.assertEqual(order["symbol"], "A     211114P50001000")

        status = dummy.fetch_option_order_status(order["id"])
        self.assertEqual(status["symbol"], "A     211114P50001000")
        self.assertEqual(status["quantity"], 5)

    def test_commission(self):
        commission_fee = {"buy": 5.76, "sell": "2%"}

        dummy = PaperBroker(commission_fee=commission_fee)
        total_cost = dummy.apply_commission(50, dummy.commission_fee, "buy")
        self.assertEqual(total_cost, 55.76)
        total_cost = dummy.apply_commission(50, dummy.commission_fee, "sell")
        self.assertEqual(total_cost, 49)


if __name__ == "__main__":
    unittest.main()
