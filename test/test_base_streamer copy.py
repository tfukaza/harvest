# Builtins
import pathlib
import unittest
import datetime as dt

from harvest.api.dummy import DummyStreamer 

class TestBaseStreamer(unittest.TestCase):
    # def test_fetch_prices(self):
    #     dummy = DummyStreamer()
    #     df = dummy.fetch_price_history('PO', '1HR', dt.datetime.now() - dt.timedelta(hours=50), dt.datetime.now())['PO']
    #     self.assertEqual(list(df.columns.values), ['open', 'high', 'low', 'close', 'volume'])

    # def test_setup(self):
    #     dummy = DummyStreamer()
    #     watch = ['A', 'B', 'C', '@D']
    #     dummy.setup(watch, '1MIN')
    #     self.assertEqual(dummy.watch, watch)

    # def test_get_stock_price(self):
    #     dummy = DummyStreamer()
    #     watch = ['A', 'B', 'C', '@D']
    #     dummy.setup(watch, '1MIN')
    #     d = dummy.fetch_latest_stock_price()
    #     self.assertEqual(len(d), 3)

    # def test_get_crypto_price(self):
    #     dummy = DummyStreamer()
    #     watch = ['A', 'B', 'C', '@D']
    #     dummy.setup(watch, '1MIN')
    #     d = dummy.fetch_latest_crypto_price()
    #     self.assertTrue('@D' in d)
    #     self.assertEqual(d['@D'].shape, (1, 5))
    pass

if __name__ == '__main__':
    unittest.main()