# Builtins
import pathlib
import unittest
import datetime as dt

from pandas.testing import assert_frame_equal

from harvest.api.dummy import DummyStreamer 

class TestDummyStreamer(unittest.TestCase):
    def test_fetch_prices(self):
        dummy = DummyStreamer()
        df = dummy.fetch_price_history('PO', '1HR')['PO']
        self.assertEqual(list(df.columns.values), ['open', 'high', 'low', 'close', 'volume'])

    def test_setup(self):
        dummy = DummyStreamer()
        watch = ['A', 'B', 'C', '@D']
        dummy.setup(watch, '1MIN')
        self.assertEqual(dummy.watch, watch)

    def test_get_stock_price(self):
        dummy = DummyStreamer()
        watch = ['A', 'B', 'C', '@D']
        dummy.setup(watch, '1MIN')
        d = dummy.fetch_latest_stock_price()
        self.assertEqual(len(d), 3)

    def test_get_crypto_price(self):
        dummy = DummyStreamer()
        watch = ['A', 'B', 'C', '@D']
        dummy.setup(watch, '1MIN')
        d = dummy.fetch_latest_crypto_price()
        self.assertTrue('@D' in d)
        self.assertEqual(d['@D'].shape, (1, 5))

    def test_simple_static(self):
        dummy1 = DummyStreamer()
        dummy2 = DummyStreamer()

        df1 = dummy1.fetch_price_history('A', '1MIN')
        df2 = dummy2.fetch_price_history('A', '1MIN')

        assert_frame_equal(df1, df2)

    def test_complex_static(self):
        dummy1 = DummyStreamer()
        dummy2 = DummyStreamer()

        df1B = dummy1.fetch_price_history('B', '5MIN')
        df2A = dummy2.fetch_price_history('A', '5MIN')
        df1A = dummy1.fetch_price_history('A', '5MIN')
        df2B = dummy2.fetch_price_history('B', '5MIN')

        assert_frame_equal(df1A, df2A)
        assert_frame_equal(df1B, df2B)

if __name__ == '__main__':
    unittest.main()