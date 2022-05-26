# Builtins
import os
import pathlib
import unittest
import datetime as dt

from harvest.api.paper import PaperBroker

from harvest.definitions import *
from harvest.utils import *
from _util import *


class TestPaperBroker(unittest.TestCase):
    @delete_save_files(".")
    def test_account(self):
        """
        By default, the account is created with a balance of 1 million dollars.
        """
        paper = PaperBroker()
        d = paper.fetch_account()
        self.assertEqual(d["equity"], 1000000.0)
        self.assertEqual(d["cash"], 1000000.0)
        self.assertEqual(d["buying_power"], 1000000.0)
        self.assertEqual(d["multiplier"], 1)

    @delete_save_files(".")
    def test_dummy_account(self):
        """
        Test if positions can be saved correctly.
        """
        paper = PaperBroker()

        paper.stocks.append({"symbol": "A", "avg_price": 1.0, "quantity": 5})
        paper.stocks.append({"symbol": "B", "avg_price": 10.0, "quantity": 5})
        paper.cryptos.append({"symbol": "@C", "avg_price": 289.21, "quantity": 2})

        stocks = paper.fetch_stock_positions()

        self.assertEqual(len(stocks), 2)
        self.assertEqual(stocks[0]["symbol"], "A")
        self.assertEqual(stocks[0]["avg_price"], 1.0)
        self.assertEqual(stocks[0]["quantity"], 5)

        cryptos = paper.fetch_crypto_positions()
        self.assertEqual(len(cryptos), 1)
        self.assertEqual(cryptos[0]["symbol"], "@C")
        self.assertEqual(cryptos[0]["avg_price"], 289.21)
        self.assertEqual(cryptos[0]["quantity"], 2)

    @delete_save_files(".")
    def test_buy_order_limit(self):
        """
        Test if buy orders can be placed correctly.
        """

        _, dummy, paper = create_trader_and_api("dummy", "paper", "5MIN", ["A"])
        account = paper.fetch_account()

        # First, check that there is $1m in the account
        self.assertEqual(account["equity"], 1000000.0)
        self.assertEqual(account["cash"], 1000000.0)
        self.assertEqual(account["buying_power"], 1000000.0)
        # Get the current price of A
        A_price = dummy.fetch_latest_price("A")
        # Place an order to buy A
        order = paper.order_stock_limit("buy", "A", 5, A_price * 1.05)

        self.assertEqual(order["order_id"], 0)
        self.assertEqual(order["symbol"], "A")

        # Since this is a simulation, orders are immediately filled
        status = paper.fetch_stock_order_status(order["order_id"])

        self.assertEqual(status["order_id"], 0)
        self.assertEqual(status["symbol"], "A")
        self.assertEqual(status["quantity"], 5)
        self.assertEqual(status["filled_qty"], 0)
        # self.assertEqual(status["filled_price"], 0)
        self.assertEqual(status["side"], "buy")
        self.assertEqual(status["time_in_force"], "gtc")
        self.assertEqual(status["status"], "filled")

        # Assume order will be filled at the price of A
        filled_price = A_price
        filled_qty = status["quantity"]
        cost_1 = filled_price * filled_qty

        # Advance time so broker status gets updated
        dummy.main()

        account_after = paper.fetch_account()
        self.assertEqual(account_after["equity"], account["equity"])
        self.assertEqual(account_after["cash"], account["cash"] - cost_1)
        self.assertEqual(
            account_after["buying_power"], account["buying_power"] - cost_1
        )

    # def test_buy(self):

    #     trader, dummy, paper = create_trader_and_api("dummy", "paper", "1MIN", ["A"])

    #     order = paper.buy("A", 5, 1e5)

    #     self.assertEqual(order["order_id"], 0)
    #     self.assertEqual(order["symbol"], "A")

    #     status = paper.fetch_stock_order_status(order["order_id"])
    #     self.assertEqual(status["order_id"], 0)
    #     self.assertEqual(status["symbol"], "A")
    #     self.assertEqual(status["quantity"], 5)
    #     self.assertEqual(status["filled_qty"], 5)
    #     self.assertEqual(status["side"], "buy")
    #     self.assertEqual(status["time_in_force"], "gtc")
    #     self.assertEqual(status["status"], "filled")
    #     paper._delete_account()

    @delete_save_files(".")
    def test_sell_order_limit(self):
        """
        Test if Paper Broker can sell orders correctly.
        Assumes the buy feature works.
        """

        _, dummy, paper = create_trader_and_api("dummy", "paper", "5MIN", ["A"])
        account = paper.fetch_account()

        A_price = dummy.fetch_latest_price("A")
        order = paper.order_stock_limit("buy", "A", 2, A_price * 1.05)
        status = paper.fetch_stock_order_status(order["order_id"])
        filled_price = A_price
        filled_qty = status["quantity"]
        cost = filled_price * filled_qty

        dummy.main()

        A_price = dummy.fetch_latest_price("A")
        account_1 = paper.fetch_account()
        print(account_1)

        order = paper.order_stock_limit("sell", "A", 2, A_price * 0.95)

        status = paper.fetch_stock_order_status(order["order_id"])
        self.assertEqual(status["order_id"], 1)
        self.assertEqual(status["symbol"], "A")
        self.assertEqual(status["quantity"], 2)
        self.assertEqual(status["filled_qty"], 0)
        # self.assertEqual(status["filled_price"], 0)
        self.assertEqual(status["side"], "sell")
        self.assertEqual(status["time_in_force"], "gtc")
        self.assertEqual(status["status"], "filled")

        filled_price_s = A_price
        filled_qty_s = status["quantity"]
        cost_s = filled_price_s * filled_qty_s
        profit = cost_s - cost

        exp_equity = 1000000.0 + profit

        dummy.main()

        account_2 = paper.fetch_account()

        self.assertAlmostEqual(account_2["equity"], exp_equity, 2)
        self.assertEqual(account_2["cash"], account_1["cash"] + cost_s)
        self.assertEqual(account_2["buying_power"], account_1["buying_power"] + cost_s)

    @delete_save_files(".")
    def test_sell(self):

        _, _, paper = create_trader_and_api("dummy", "paper", "1MIN", ["A"])
        paper.stocks = [{"symbol": "A", "avg_price": 10.0, "quantity": 5}]

        order = paper.sell("A", 2)
        self.assertEqual(order["order_id"], 0)
        self.assertEqual(order["symbol"], "A")

        status = paper.fetch_stock_order_status(order["order_id"])
        self.assertEqual(status["order_id"], 0)
        self.assertEqual(status["symbol"], "A")
        self.assertEqual(status["quantity"], 2)
        self.assertEqual(status["filled_qty"], 0)
        # self.assertEqual(status["filled_price"], 0)
        self.assertEqual(status["side"], "sell")
        self.assertEqual(status["time_in_force"], "gtc")
        self.assertEqual(status["status"], "filled")
        paper._delete_account()

    @delete_save_files(".")
    def test_order_option_limit(self):
        paper = PaperBroker()

        _, _, paper = create_trader_and_api("dummy", "paper", "1MIN", ["A"])

        exp_date = dt.datetime(2021, 11, 14) + dt.timedelta(hours=5)
        order = paper.order_option_limit(
            "buy", "A", 5, 50000, "OPTION", exp_date, 50001
        )

        self.assertEqual(order["order_id"], 0)
        self.assertEqual(order["symbol"], "A211114P50001000")

        status = paper.fetch_option_order_status(order["order_id"])
        self.assertEqual(status["symbol"], "A211114P50001000")
        self.assertEqual(status["quantity"], 5)
        paper._delete_account()

    @delete_save_files(".")
    def test_commission(self):
        commission_fee = {"buy": 5.76, "sell": "2%"}

        _, _, paper = create_trader_and_api("dummy", "paper", "1MIN", ["A"])
        paper.commission_fee = commission_fee

        total_cost = paper.apply_commission(50, paper.commission_fee, "buy")
        self.assertEqual(total_cost, 55.76)
        total_cost = paper.apply_commission(50, paper.commission_fee, "sell")
        self.assertEqual(total_cost, 49)
        paper._delete_account()


if __name__ == "__main__":
    unittest.main()
