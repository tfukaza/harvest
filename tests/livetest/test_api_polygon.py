import unittest
from harvest.api.polygon import PolygonStreamer
from harvest.utils import *
import time
import os

secret_path = os.environ["SECRET_PATH"]

class TestLivePolygon(unittest.TestCase):

    def test_get_prices(self):
        """
        Test API to get stock history
        """
        poly = PolygonStreamer(secret_path, True)
        interval = {
            "SPY": {"interval": Interval.MIN_5, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        poly.setup(stats, Account())
    
        ret = poly.fetch_price_history("SPY", Interval.MIN_5)
        
        self.assertTrue(len(ret.columns), 5)


    def test_get_prices_cfg(self):
        poly = PolygonStreamer("poly_secret.yaml", True)
        df = poly.fetch_price_history(
            "AAPL", Interval.HR_1, now() - dt.timedelta(days=7), now()
        )["AAPL"]
        self.assertEqual(
            list(df.columns.values), ["open", "high", "low", "close", "volume"]
        )


if __name__ == "__main__":
    unittest.main()
