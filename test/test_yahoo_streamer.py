# Builtins
import pathlib
import unittest
import datetime as dt

from harvest.api.yahoo import YahooStreamer

class TestYahooStreamer(unittest.TestCase):
    def test_fetch_prices(self):
        yh = YahooStreamer()
        df = yh.fetch_price_history('SPY', '1HR', dt.datetime.now() - dt.timedelta(hours=50), dt.datetime.now())['SPY']
        self.assertEqual(list(df.columns.values), ['open', 'high', 'low', 'close', 'volume'])

    def test_setup(self):
        yh = YahooStreamer()
        watch = ['SPY', 'AAPL']
        yh.setup(watch, '1MIN')
        self.assertEqual(yh.watch, watch)

if __name__ == '__main__':
    unittest.main()