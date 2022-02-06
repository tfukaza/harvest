# Builtins
import os
import time
import unittest
import datetime as dt

from harvest.utils import *
from harvest.definitions import *
from harvest.api.alpaca import Alpaca

secret_path = os.environ["SECRET_PATH"]
debugger.setLevel("DEBUG")

class TestAlpaca(unittest.TestCase):
    def test_current_time(self):
        broker = Alpaca(path=secret_path, is_basic_account=True, paper_trader=True)

        threshold = dt.timedelta(seconds=5)
        current_time = broker.get_current_time()
        self.assertTrue(now() - current_time < threshold)

        time.sleep(60)

    def test_fetch_stock_price(self):
        broker = Alpaca(path=secret_path, is_basic_account=True, paper_trader=True)

        # Use datetime with no timezone for start and end
        end = dt.datetime.now() - dt.timedelta(days=7)
        start = end - dt.timedelta(days=7)
        results = broker.fetch_price_history('AAPL', Interval.MIN_1, start, end)
        self.assertTrue(results.shape[0] > 0)
        self.assertTrue(results.shape[1] == 5)

        # Use datetime with timezone for start and end
        start = start.astimezone(dt.timezone(dt.timedelta(hours=2)))
        end = end.astimezone(dt.timezone(dt.timedelta(hours=2)))
        results = broker.fetch_price_history('AAPL', Interval.MIN_1, start, end)
        self.assertTrue(results.shape[0] > 0)
        self.assertTrue(results.shape[1] == 5)

        # Use ISO 8601 string for start and end
        start = "2022-01-21T09:00-05:00"
        end = "2022-01-25T17:00-05:00"
        results = broker.fetch_price_history('AAPL', Interval.MIN_1, start, end)
        self.assertTrue(results.shape[0] > 0)
        self.assertTrue(results.shape[1] == 5)

        time.sleep(60)

    def test_market_time(self):
        broker = Alpaca(path=secret_path, is_basic_account=True, paper_trader=True)

        results = broker.fetch_market_hours(now())
        self.assertTrue("is_open" in results)
        self.assertTrue("open_at" in results)
        self.assertTrue("close_at" in results)

        time.sleep(60)

    def test_positions(self):
        broker = Alpaca(path=secret_path, is_basic_account=True, paper_trader=True)

        results = broker.fetch_stock_positions()
        self.assertTrue(len(results) >= 0)
        results = broker.fetch_option_positions()
        self.assertTrue(len(results) >= 0)
        results = broker.fetch_crypto_positions()
        self.assertTrue(len(results) >= 0)

        time.sleep(60)

    def test_account(self):
        broker = Alpaca(path=secret_path, is_basic_account=True, paper_trader=True)

        results = broker.fetch_account()
        self.assertGreater(results["equity"], 100)
        self.assertGreater(results["cash"], 100)
        self.assertGreater(results["buying_power"], 100)
        self.assertGreater(results["multiplier"], 0)

        time.sleep(60)

    def test_buy_cancel(self):
        broker = Alpaca(path=secret_path, is_basic_account=True, paper_trader=True)

        results = broker.order_stock_limit("buy", "AAPL", 1, 200.00)
        self.assertEqual(results["type"], "STOCK")
        self.assertEqual(results["symbol"], "AAPL")

        time.sleep(10)

        results = broker.cancel_stock_order(results["id"])

if __name__ == "__main__":
    unittest.main()
