# Builtins
import os
import time
import unittest
import datetime as dt

from harvest.utils import *
from harvest.definitions import *
from harvest.api.polygon import PolygonStreamer

secret_path = os.environ["SECRET_PATH"]
debugger.setLevel("DEBUG")

class TestPolygonStreamer(unittest.TestCase):
    def test_current_time(self):
        streamer = PolygonStreamer(path=secret_path, is_basic_account=True)

        threshold = dt.timedelta(seconds=5)
        current_time = streamer.get_current_time()
        self.assertTrue(now() - current_time < threshold)

        time.sleep(60)

    def test_fetch_stock_price(self):
        streamer = PolygonStreamer(path=secret_path, is_basic_account=True)

        # Use datetime with no timezone for start and end
        end = dt.datetime.now() - dt.timedelta(days=7)
        start = end - dt.timedelta(days=7)
        results = streamer.fetch_price_history('AAPL', Interval.MIN_1, start, end)
        self.assertTrue(results.shape[0] > 0)
        self.assertTrue(results.shape[1] == 5)

        # Use datetime with timezone for start and end
        start = start.astimezone(dt.timezone(dt.timedelta(hours=2)))
        end = end.astimezone(dt.timezone(dt.timedelta(hours=2)))
        results = streamer.fetch_price_history('MSFT', Interval.MIN_1, start, end)
        self.assertTrue(results.shape[0] > 0)
        self.assertTrue(results.shape[1] == 5)

        # Use ISO 8601 string for start and end
        start = "2022-01-21T09:00-05:00"
        end = "2022-01-25T17:00-05:00"
        results = streamer.fetch_price_history('AAPL', Interval.MIN_1, start, end)
        self.assertTrue(results.shape[0] > 0)
        self.assertTrue(results.shape[1] == 5)

        time.sleep(60)

    def test_fetch_crypto_price(self):
        streamer = PolygonStreamer(path=secret_path, is_basic_account=True)

        # Use datetime with no timezone for start and end
        end = dt.datetime.now() - dt.timedelta(days=7)
        start = end - dt.timedelta(days=7)
        results = streamer.fetch_price_history('@BTC', Interval.MIN_1, start, end)
        self.assertTrue(results.shape[0] > 0)
        self.assertTrue(results.shape[1] == 5)

        # Use datetime with timezone for start and end
        start = start.astimezone(dt.timezone(dt.timedelta(hours=2)))
        end = end.astimezone(dt.timezone(dt.timedelta(hours=2)))
        results = streamer.fetch_price_history('@DOGE', Interval.MIN_1, start, end)
        self.assertTrue(results.shape[0] > 0)
        self.assertTrue(results.shape[1] == 5)

        # Use ISO 8601 string for start and end
        start = "2022-01-21T09:00-05:00"
        end = "2022-01-25T17:00-05:00"
        results = streamer.fetch_price_history('@BTC', Interval.MIN_1, start, end)
        self.assertTrue(results.shape[0] > 0)
        self.assertTrue(results.shape[1] == 5)

        time.sleep(60)

    def test_fetch_option(self):
        streamer = PolygonStreamer(path=secret_path, is_basic_account=True)

        results = streamer.fetch_chain_info('AAPL')
        self.assertTrue('exp_dates' in results)
        self.assertTrue(len(results['exp_dates']) > 0)

        results = streamer.fetch_chain_data('AAPL', results['exp_dates'][-1])
        self.assertTrue(results.shape[0] > 0)
        self.assertTrue(results.shape[1] == 3)

        time.sleep(60)
        
    def test_market_time(self):
        streamer = PolygonStreamer(path=secret_path, is_basic_account=True)

        results = streamer.fetch_market_hours(now())
        self.assertTrue("is_open" in results)
        self.assertTrue("open_at" in results)
        self.assertTrue("close_at" in results)


if __name__ == "__main__":
    unittest.main()
