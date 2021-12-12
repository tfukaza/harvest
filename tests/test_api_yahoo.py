# Builtins
import pathlib
import unittest
import datetime as dt

from harvest.api.yahoo import YahooStreamer
from harvest.trader.trader import PaperTrader
from harvest.utils import *


class TestYahooStreamer(unittest.TestCase):
    def test_fetch_prices(self):
        yh = YahooStreamer()
        df = yh.fetch_price_history("SPY", Interval.HR_1)
        df = df["SPY"]
        self.assertEqual(
            list(df.columns.values), ["open", "high", "low", "close", "volume"]
        )

    def test_setup(self):
        yh = YahooStreamer()
        interval = {
            "SPY": {"interval": Interval.MIN_15, "aggregations": []},
            "AAPL": {"interval": Interval.MIN_1, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        yh.setup(stats)

        self.assertEqual(yh.poll_interval, Interval.MIN_1)
        self.assertListEqual([s for s in yh.interval], ["SPY", "AAPL"])

    def test_main(self):
        interval = {
            "SPY": {"interval": Interval.MIN_1, "aggregations": []},
            "AAPL": {"interval": Interval.MIN_1, "aggregations": []},
            "@BTC": {"interval": Interval.MIN_1, "aggregations": []},
        }

        def test_main(df):
            self.assertEqual(len(df), 3)
            self.assertEqual(df["SPY"].columns[0][0], "SPY")
            self.assertEqual(df["AAPL"].columns[0][0], "AAPL")
            self.assertEqual(df["@BTC"].columns[0][0], "@BTC")

        yh = YahooStreamer()
        stats = Stats(watchlist_cfg=interval)
        yh.setup(stats, test_main)

        yh.main()

    def test_main_single(self):
        interval = {"SPY": {"interval": Interval.MIN_1, "aggregations": []}}

        def test_main(df):
            self.assertEqual(len(df), 1)
            self.assertEqual(df["SPY"].columns[0][0], "SPY")

        yh = YahooStreamer()
        stats = Stats(watchlist_cfg=interval)
        yh.setup(stats, test_main)

        yh.main()

    def test_chain_info(self):
        yh = YahooStreamer()

        interval = {"LMND": {"interval": Interval.MIN_1, "aggregations": []}}
        stats = Stats(watchlist_cfg=interval)
        yh.setup(stats)

        info = yh.fetch_chain_info("LMND")
        self.assertGreater(len(info["exp_dates"]), 0)

    def test_chain_data(self):

        yh = YahooStreamer()

        interval = {"LMND": {"interval": Interval.MIN_1, "aggregations": []}}
        stats = Stats(watchlist_cfg=interval)
        yh.setup(stats)

        dates = yh.fetch_chain_info("LMND")["exp_dates"]
        data = yh.fetch_chain_data("LMND", dates[0])
        self.assertGreater(len(data), 0)
        self.assertListEqual(list(data.columns), ["exp_date", "strike", "type"])

        sym = data.index[0]
        df = yh.fetch_option_market_data(sym)

        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
