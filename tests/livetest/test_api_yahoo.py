# Builtins
import os
import time
import unittest
import datetime as dt

from harvest.utils import *
from harvest.definitions import *
from harvest.broker.yahoo import YahooStreamer

debugger.setLevel("DEBUG")


class TestYahooStreamer(unittest.TestCase):
    def test_current_time(self):
        broker = YahooStreamer()

        threshold = dt.timedelta(seconds=5)
        current_time = broker.get_current_time()
        self.assertTrue(now() - current_time < threshold)

        time.sleep(60)

    def test_fetch_stock_price(self):
        broker = YahooStreamer()

        # Use datetime with no timezone for start and end
        end = dt.datetime.now() - dt.timedelta(days=7)
        start = end - dt.timedelta(days=7)
        results = broker.fetch_price_history("AAPL", Interval.MIN_1, start, end)
        self.assertTrue(results.shape[0] > 0)
        self.assertTrue(results.shape[1] == 5)

        # Use datetime with timezone for start and end
        start = start.astimezone(dt.timezone(dt.timedelta(hours=2)))
        end = end.astimezone(dt.timezone(dt.timedelta(hours=2)))
        results = broker.fetch_price_history("AAPL", Interval.MIN_1, start, end)
        self.assertTrue(results.shape[0] > 0)
        self.assertTrue(results.shape[1] == 5)

        # Use ISO 8601 string for start and end
        start = "2022-01-21T09:00-05:00"
        end = "2022-01-25T17:00-05:00"
        results = broker.fetch_price_history("AAPL", Interval.MIN_1, start, end)
        self.assertTrue(results.shape[0] > 0)
        self.assertTrue(results.shape[1] == 5)

        time.sleep(60)


if __name__ == "__main__":
    unittest.main()
