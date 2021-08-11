# Builtins
import unittest
import datetime as dt

from harvest.utils import *
from harvest.api.alpaca import Alpaca

class TestAlpaca(unittest.TestCase):
    def test_fetch_prices(self):
        alpaca = Alpaca('alpaca_secret.yaml', True)
        df = alpaca.fetch_price_history('AAPL', '1HR', now() - dt.timedelta(days=7), now())['AAPL']
        self.assertEqual(list(df.columns.values), ['open', 'high', 'low', 'close', 'volume'])


if __name__ == '__main__':
    unittest.main()