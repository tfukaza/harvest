# Builtins
import os
import pathlib
import unittest
import datetime as dt

from harvest.api.paper import PaperBroker

from harvest.definitions import *
from harvest.utils import *


class TestPaperBroker(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        try:
            os.remove("./.save")
        except:
            pass

    def test_account(self):
        dummy = PaperBroker()
        d = dummy.fetch_account()
        self.assertEqual(d["equity"], 1000000.0)
        self.assertEqual(d["cash"], 1000000.0)
        self.assertEqual(d["buying_power"], 1000000.0)
        self.assertEqual(d["multiplier"], 1)
        dummy._delete_account()

    def test_dummy_account(self):
        dummy = PaperBroker()

        dummy.stocks.append({"symbol": "A", "avg_price": 1.0, "quantity": 5})
        dummy.stocks.append({"symbol": "B", "avg_price": 10.0, "quantity": 5})
        dummy.cryptos.append({"symbol": "@C", "avg_price": 289.21, "quantity": 2})

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
        dummy._delete_account()

    def test_buy_order_limit(self):
        dummy = PaperBroker()
        interval = {"A": {"interval": Interval.MIN_1, "aggregations": []}}
        stats = Stats(watchlist_cfg=interval)
        dummy.setup(stats, Account())
        order = dummy.order_stock_limit("buy", "A", 5, 50000)

        self.assertEqual(order["order_id"], 0)
        self.assertEqual(order["symbol"], "A")

        status = dummy.fetch_stock_order_status(order["order_id"])
        self.assertEqual(status["order_id"], 0)
        self.assertEqual(status["symbol"], "A")
        self.assertEqual(status["quantity"], 5)
        self.assertEqual(status["filled_qty"], 5)
        self.assertEqual(status["side"], "buy")
        self.assertEqual(status["time_in_force"], "gtc")
        self.assertEqual(status["status"], "filled")
        dummy._delete_account()

    def test_buy(self):
        dummy = PaperBroker()
        interval = {"A": {"interval": Interval.MIN_1, "aggregations": []}}
        stats = Stats(watchlist_cfg=interval)
        dummy.setup(stats, Account())
        order = dummy.buy("A", 5, 1e5)

        self.assertEqual(order["order_id"], 0)
        self.assertEqual(order["symbol"], "A")

        status = dummy.fetch_stock_order_status(order["order_id"])
        self.assertEqual(status["order_id"], 0)
        self.assertEqual(status["symbol"], "A")
        self.assertEqual(status["quantity"], 5)
        self.assertEqual(status["filled_qty"], 5)
        self.assertEqual(status["side"], "buy")
        self.assertEqual(status["time_in_force"], "gtc")
        self.assertEqual(status["status"], "filled")
        dummy._delete_account()

    def test_sell_order_limit(self):
        dummy = PaperBroker()

        interval = {"A": {"interval": Interval.MIN_1, "aggregations": []}}
        stats = Stats(watchlist_cfg=interval)
        dummy.setup(stats, Account())

        dummy.stocks = [{"symbol": "A", "avg_price": 10.0, "quantity": 5}]

        order = dummy.order_stock_limit("sell", "A", 2, 50000)
        self.assertEqual(order["order_id"], 0)
        self.assertEqual(order["symbol"], "A")

        status = dummy.fetch_stock_order_status(order["order_id"])
        self.assertEqual(status["order_id"], 0)
        self.assertEqual(status["symbol"], "A")
        self.assertEqual(status["quantity"], 2)
        self.assertEqual(status["filled_qty"], 2)
        self.assertEqual(status["side"], "sell")
        self.assertEqual(status["time_in_force"], "gtc")
        self.assertEqual(status["status"], "filled")
        dummy._delete_account()

    def test_sell(self):
        dummy = PaperBroker()

        interval = {"A": {"interval": Interval.MIN_5, "aggregations": []}}
        stats = Stats(watchlist_cfg=interval)
        dummy.setup(stats, Account())
        dummy.stocks = [{"symbol": "A", "avg_price": 10.0, "quantity": 5}]

        order = dummy.sell("A", 2)
        self.assertEqual(order["order_id"], 0)
        self.assertEqual(order["symbol"], "A")

        status = dummy.fetch_stock_order_status(order["order_id"])
        self.assertEqual(status["order_id"], 0)
        self.assertEqual(status["symbol"], "A")
        self.assertEqual(status["quantity"], 2)
        self.assertEqual(status["filled_qty"], 2)
        self.assertEqual(status["side"], "sell")
        self.assertEqual(status["time_in_force"], "gtc")
        self.assertEqual(status["status"], "filled")
        dummy._delete_account()

    def test_order_option_limit(self):
        dummy = PaperBroker()

        interval = {"A": {"interval": Interval.MIN_1, "aggregations": []}}
        stats = Stats(watchlist_cfg=interval)
        dummy.setup(stats, Account())

        exp_date = dt.datetime(2021, 11, 14) + dt.timedelta(hours=5)
        order = dummy.order_option_limit(
            "buy", "A", 5, 50000, "OPTION", exp_date, 50001
        )

        self.assertEqual(order["order_id"], 0)
        self.assertEqual(order["symbol"], "A211114P50001000")

        status = dummy.fetch_option_order_status(order["order_id"])
        self.assertEqual(status["symbol"], "A211114P50001000")
        self.assertEqual(status["quantity"], 5)
        dummy._delete_account()

    def test_commission(self):
        commission_fee = {"buy": 5.76, "sell": "2%"}

        dummy = PaperBroker(commission_fee=commission_fee)
        total_cost = dummy.apply_commission(50, dummy.commission_fee, "buy")
        self.assertEqual(total_cost, 55.76)
        total_cost = dummy.apply_commission(50, dummy.commission_fee, "sell")
        self.assertEqual(total_cost, 49)
        dummy._delete_account()


if __name__ == "__main__":
    unittest.main()
