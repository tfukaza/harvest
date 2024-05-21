import datetime as dt
import time
import unittest

from harvest.broker.yahoo import YahooBroker
from harvest.definitions import Account, Stats
from harvest.enum import Interval
from harvest.util.helper import debugger, utc_current_time

debugger.setLevel("DEBUG")


class TestYahooStreamer(unittest.TestCase):
    def test_current_time(self):
        broker = YahooBroker()

        threshold = dt.timedelta(seconds=5)
        current_time = broker.get_current_time()
        self.assertTrue(utc_current_time() - current_time < threshold)

        time.sleep(60)

    def test_fetch_stock_price(self):
        broker = YahooBroker()

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

    def test_fetch_prices(self):
        yh = YahooBroker()
        df = yh.fetch_price_history("SPY", Interval.HR_1)
        df = df["SPY"]
        self.assertEqual(list(df.columns.values), ["open", "high", "low", "close", "volume"])

    def test_setup(self):
        yh = YahooBroker()
        interval = {
            "SPY": {"interval": Interval.MIN_15, "aggregations": []},
            "AAPL": {"interval": Interval.MIN_1, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        yh.setup(stats, Account())

        self.assertEqual(yh.poll_interval, Interval.MIN_1)
        self.assertListEqual(list(yh.stats.watchlist_cfg.keys()), ["SPY", "AAPL"])

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

        yh = YahooBroker()
        stats = Stats(watchlist_cfg=interval)
        yh.setup(stats, Account(), test_main)

        yh.step()

    def test_main_single(self):
        interval = {"SPY": {"interval": Interval.MIN_1, "aggregations": []}}

        def test_main(df):
            self.assertEqual(len(df), 1)
            self.assertEqual(df["SPY"].columns[0][0], "SPY")

        yh = YahooBroker()
        stats = Stats(watchlist_cfg=interval)
        yh.setup(stats, Account(), test_main)

        yh.step()

    def test_chain_info(self):
        yh = YahooBroker()

        interval = {"SPY": {"interval": Interval.MIN_1, "aggregations": []}}
        stats = Stats(watchlist_cfg=interval)
        yh.setup(stats, Account())

        info = yh.fetch_chain_info("SPY")

        self.assertGreater(len(info["exp_dates"]), 0)

    def test_chain_data(self):
        yh = YahooBroker()

        interval = {"SPY": {"interval": Interval.MIN_1, "aggregations": []}}
        stats = Stats(watchlist_cfg=interval)
        yh.setup(stats, Account())

        dates = yh.fetch_chain_info("SPY")["exp_dates"]
        data = yh.fetch_chain_data("SPY", dates[0])
        self.assertGreater(len(data), 0)
        self.assertListEqual(list(data.columns), ["exp_date", "strike", "type"])

        sym = data.index[0]
        _ = yh.fetch_option_market_data(sym)

        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
