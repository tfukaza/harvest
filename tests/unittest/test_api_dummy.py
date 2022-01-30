# Builtins
import pathlib
import unittest
import datetime as dt

import pytz
from pandas.testing import assert_frame_equal

from harvest.api.dummy import DummyStreamer
from harvest.definitions import *
from harvest.utils import *


class TestDummyStreamer(unittest.TestCase):
    def test_fetch_prices(self):
        streamer = DummyStreamer(current_time="2000-01-01 00:00")
        current_time = dt.datetime(
            2000, 1, 1, 0, 0, tzinfo=get_local_timezone()
        ).astimezone(dt.timezone.utc)
        # Get per-minute data
        df_1 = streamer.fetch_price_history("A", Interval.MIN_1)["A"]
        # Check that the last date is 1/1/2020-00:00:00
        self.assertEqual(df_1.index[-1], pd.Timestamp(current_time))
        # Advance the time by 1 minute
        streamer.tick()
        df_2 = streamer.fetch_price_history("A", Interval.MIN_1)["A"]
        # Check that the last date is 1/1/2020-00:01:00
        self.assertEqual(
            df_2.index[-1], pd.Timestamp(current_time + dt.timedelta(minutes=1))
        )

        # Check that the two dataframes are the same
        assert_frame_equal(df_1.iloc[1:], df_2.iloc[:-1])

    def test_setup(self):
        dummy = DummyStreamer()
        interval = {
            "A": {"interval": Interval.MIN_1, "aggregations": []},
            "B": {"interval": Interval.MIN_1, "aggregations": []},
            "C": {"interval": Interval.MIN_1, "aggregations": []},
            "@D": {"interval": Interval.MIN_1, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        dummy.setup(stats, Account())

        self.assertEqual(dummy.stats.watchlist_cfg, interval)

    def test_get_stock_price(self):
        dummy = DummyStreamer()
        interval = {
            "A": {"interval": Interval.MIN_1, "aggregations": []},
            "B": {"interval": Interval.MIN_1, "aggregations": []},
            "C": {"interval": Interval.MIN_1, "aggregations": []},
            "@D": {"interval": Interval.MIN_1, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)

        trader_main = lambda df_dict: self.assertTrue("A" in df_dict)
        dummy.setup(stats, Account(), trader_main)

        dummy.main()

    def test_get_crypto_price(self):
        dummy = DummyStreamer()
        interval = {
            "A": {"interval": Interval.MIN_1, "aggregations": []},
            "B": {"interval": Interval.MIN_1, "aggregations": []},
            "C": {"interval": Interval.MIN_1, "aggregations": []},
            "@D": {"interval": Interval.MIN_1, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)

        trader_main = lambda df_dict: self.assertTrue("@D" in df_dict)
        dummy.setup(stats, Account(), trader_main)

        dummy.main()

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
