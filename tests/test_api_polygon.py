# Builtins
import unittest
import datetime as dt
import os

from harvest.utils import *
from harvest.api.polygon import PolygonStreamer


class TestPolygonStreamer(unittest.TestCase):
    @not_gh_action
    def test_fetch_prices(self):
        poly = PolygonStreamer("poly_secret.yaml", True)
        df = poly.fetch_price_history(
            "AAPL", Interval.HR_1, now() - dt.timedelta(days=7), now()
        )["AAPL"]
        self.assertEqual(
            list(df.columns.values), ["open", "high", "low", "close", "volume"]
        )


if __name__ == "__main__":
    unittest.main()
