# Builtins
import os
import time
import unittest
import datetime as dt

from harvest.utils import *
from harvest.definitions import *
from harvest.api.kraken import Kraken

secret_path = os.environ["SECRET_PATH"]
debugger.setLevel("DEBUG")

class TestKraken(unittest.TestCase):
    def test_current_time(self):
        broker = Kraken(path=secret_path)

        threshold = dt.timedelta(seconds=5)
        current_time = broker.get_current_time()
        self.assertTrue(now() - current_time < threshold)

        time.sleep(60)

    def test_fetch_price(self):
        broker = Kraken(path=secret_path)

        # Use datetime with no timezone for start and end
        end = dt.datetime.now() 
        start = end - dt.timedelta(hours=12)
        results = broker.fetch_price_history('@BTC', Interval.MIN_1, start, end)
        self.assertTrue(results.shape[0] > 0)
        self.assertTrue(results.shape[1] == 5)

        # Use datetime with timezone for start and end
        start = start.astimezone(dt.timezone(dt.timedelta(hours=2)))
        end = end.astimezone(dt.timezone(dt.timedelta(hours=2)))
        results = broker.fetch_price_history('@BTC', Interval.MIN_1, start, end)
        self.assertTrue(results.shape[0] > 0)
        self.assertTrue(results.shape[1] == 5)

        # Use ISO 8601 string for start and end
        start = start.isoformat()
        end = end.isoformat()
        results = broker.fetch_price_history('@BTC', Interval.MIN_1, start, end)
        self.assertTrue(results.shape[0] > 0)
        self.assertTrue(results.shape[1] == 5)

if __name__ == "__main__":
    unittest.main()
