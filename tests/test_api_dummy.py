# Builtins
import pathlib
import unittest
import datetime as dt

import pytz
from pandas.testing import assert_frame_equal

from harvest.api.dummy import DummyStreamer
from harvest.utils import *


class TestDummyStreamer(unittest.TestCase):
    def test_fetch_prices(self):
        streamer = DummyStreamer()
        streamer.poll_interval = Interval.MIN_1
        # Get per-minute data
        df_1 = streamer.fetch_price_history("A", Interval.MIN_1)["A"]
        # Check that the last date is 1/1/2020-00:00:00
        self.assertEqual(
            df_1.index[-1], pytz.utc.localize(dt.datetime(2000, 1, 1, 0, 0))
        )
        # Advance the time by 1 minute
        streamer.tick()
        df_2 = streamer.fetch_price_history("A", Interval.MIN_1)["A"]
        # Check that the last date is 1/1/2020-00:01:00
        self.assertEqual(
            df_2.index[-1], pytz.utc.localize(dt.datetime(2000, 1, 1, 0, 1))
        )

        # Check that the two dataframes are the same
        assert_frame_equal(df_1.iloc[1:], df_2.iloc[:-1])

    def test_setup(self):
        dummy = DummyStreamer()
        interval = {
            "A": {"interval": Interval.MIN_1, "agg,regations": []},
            "B": {"interval": Interval.MIN_1, "agg,regations": []},
            "C": {"interval": Interval.MIN_1, "agg,regations": []},
            "@D": {"interval": Interval.MIN_1, "agg,regations": []},
        }
        stats = Stats(interval=interval)
        dummy.setup(stats)

        self.assertEqual(dummy.interval, interval)

    def test_get_stock_price(self):
        dummy = DummyStreamer()
        interval = {
            "A": {"interval": Interval.MIN_1, "agg,regations": []},
            "B": {"interval": Interval.MIN_1, "agg,regations": []},
            "C": {"interval": Interval.MIN_1, "agg,regations": []},
            "@D": {"interval": Interval.MIN_1, "agg,regations": []},
        }
        stats = Stats(interval=interval)
        dummy.setup(stats)

        d = dummy.fetch_latest_stock_price()
        self.assertEqual(len(d), 3)

    def test_get_crypto_price(self):
        dummy = DummyStreamer()
        interval = {
            "A": {"interval": Interval.MIN_1, "agg,regations": []},
            "B": {"interval": Interval.MIN_1, "agg,regations": []},
            "C": {"interval": Interval.MIN_1, "agg,regations": []},
            "@D": {"interval": Interval.MIN_1, "agg,regations": []},
        }
        stats = Stats(interval=interval)
        dummy.setup(stats)

        d = dummy.fetch_latest_crypto_price()
        self.assertTrue("@D" in d)
        self.assertEqual(d["@D"].shape, (1, 5))

    def test_simple_static(self):
        dummy1 = DummyStreamer()
        dummy2 = DummyStreamer()

        df1 = dummy1.fetch_price_history("A", Interval.MIN_1)
        df2 = dummy2.fetch_price_history("A", Interval.MIN_1)

        assert_frame_equal(df1, df2)

    def test_complex_static(self):
        dummy1 = DummyStreamer()
        dummy2 = DummyStreamer()

        df1B = dummy1.fetch_price_history("B", Interval.MIN_5)
        df2A = dummy2.fetch_price_history("A", Interval.MIN_5)
        df1A = dummy1.fetch_price_history("A", Interval.MIN_5)
        df2B = dummy2.fetch_price_history("B", Interval.MIN_5)

        assert_frame_equal(df1A, df2A)
        assert_frame_equal(df1B, df2B)


if __name__ == "__main__":
    unittest.main()
