# Builtins
import unittest
import datetime as dt

from harvest import trader, broker, algo 

class TestDummyBroker(unittest.TestCase):
    def test_fetch_prices(self):
        dummy = broker.DummyBroker()
        df = dummy.fetch_price_history(dt.datetime.now() - dt.timedelta(hours=20), dt.datetime.now(), '1HR', 'PO')
        self.assertEqual(list(df.columns.values), [('PO', 'open'), ('PO', 'high'), ('PO', 'low'), ('PO', 'close'), ('PO', 'volume')])

    def test_setup(self):
        dummy = broker.DummyBroker()
        watch = ['A', 'B', 'C', '@D']
        dummy.setup_run(watch, '1MIN')
        self.assertEqual(dummy.watch, watch)

    def test_get_stock_price(self):
        dummy = broker.DummyBroker()
        watch = ['A', 'B', 'C', '@D']
        dummy.setup_run(watch, '1MIN')
        d = dummy.fetch_latest_stock_price()
        print(d)
        self.assertEqual(d.shape, (1, 15))

    def test_get_crypto_price(self):
        dummy = broker.DummyBroker()
        watch = ['A', 'B', 'C', '@D']
        dummy.setup_run(watch, '1MIN')
        d = dummy.fetch_latest_crypto_price()
        self.assertEqual(d.shape, (1, 5))

if __name__ == '__main__':
    unittest.main()