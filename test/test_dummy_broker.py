# Builtins
import pathlib
import unittest
import datetime as dt

from harvest.broker.dummy import DummyBroker 

class TestDummyBroker(unittest.TestCase):
    def test_fetch_prices(self):
        dummy = DummyBroker()
        df = dummy.fetch_price_history('PO', '1HR', dt.datetime.now() - dt.timedelta(hours=50), dt.datetime.now())['PO']
        self.assertEqual(list(df.columns.values), ['open', 'high', 'low', 'close', 'volume'])

    def test_setup(self):
        dummy = DummyBroker()
        watch = ['A', 'B', 'C', '@D']
        dummy.setup(watch, '1MIN')
        self.assertEqual(dummy.watch, watch)

    def test_get_stock_price(self):
        dummy = DummyBroker()
        watch = ['A', 'B', 'C', '@D']
        dummy.setup(watch, '1MIN')
        d = dummy.fetch_latest_stock_price()
        self.assertEqual(len(d), 3)

    def test_get_crypto_price(self):
        dummy = DummyBroker()
        watch = ['A', 'B', 'C', '@D']
        dummy.setup(watch, '1MIN')
        d = dummy.fetch_latest_crypto_price()
        self.assertTrue('@D' in d)
        self.assertEqual(d['@D'].shape, (1, 5))

    def test_account(self):
        dummy = DummyBroker()
        d = dummy.fetch_account()
        self.assertEqual(d['equity'], 100000.0)
        self.assertEqual(d['cash'], 100000.0)
        self.assertEqual(d['buying_power'], 100000.0)
        self.assertEqual(d['multiplier'], 1)
        

    def test_dummy_account(self):
        directory = pathlib.Path(__file__).parent.resolve()
        dummy = DummyBroker(str(directory) + '/../dummy_account.yaml')
        stocks = dummy.fetch_stock_positions()
        self.assertEqual(len(stocks), 2)
        self.assertEqual(stocks[0]['symbol'], 'A')
        self.assertEqual(stocks[0]['avg_price'], 1.0)
        self.assertEqual(stocks[0]['quantity'], 5)

        cryptos = dummy.fetch_crypto_positions()
        self.assertEqual(len(cryptos), 1)
        self.assertEqual(cryptos[0]['symbol'], '@C')
        self.assertEqual(cryptos[0]['avg_price'], 289.21)
        self.assertEqual(cryptos[0]['quantity'], 2)

    def test_buy_order_limit(self):
        dummy = DummyBroker() 
        dummy.setup(['A'], '1MIN')
        order = dummy.order_limit('buy', 'A', 5, 25)
        self.assertEqual(order['type'], 'STOCK')
        self.assertEqual(order['id'], 0)
        self.assertEqual(order['symbol'], 'A')

        status = dummy.fetch_stock_order_status(order['id'])
        self.assertEqual(status['id'], 0)
        self.assertEqual(status['symbol'], 'A')
        self.assertEqual(status['quantity'], 5)
        self.assertEqual(status['filled_qty'], 5)
        self.assertEqual(status['side'], 'buy')
        self.assertEqual(status['time_in_force'], 'gtc')
        self.assertEqual(status['status'], 'filled')

    def test_buy(self):
        dummy = DummyBroker() 
        dummy.setup(['A'], '1MIN')
        order = dummy.buy('A', 5)
        self.assertEqual(order['type'], 'STOCK')
        self.assertEqual(order['id'], 0)
        self.assertEqual(order['symbol'], 'A')

        status = dummy.fetch_stock_order_status(order['id'])
        self.assertEqual(status['id'], 0)
        self.assertEqual(status['symbol'], 'A')
        self.assertEqual(status['quantity'], 5)
        self.assertEqual(status['filled_qty'], 5)
        self.assertEqual(status['side'], 'buy')
        self.assertEqual(status['time_in_force'], 'gtc')
        self.assertEqual(status['status'], 'filled')

    def test_sell_order_limit(self):
        directory = pathlib.Path(__file__).parent.resolve()
        dummy = DummyBroker(str(directory) + '/../dummy_account.yaml') 
        dummy.setup(['A'], '1MIN')
        order = dummy.order_limit('sell', 'A', 2, 3)
        self.assertEqual(order['type'], 'STOCK')
        self.assertEqual(order['id'], 0)
        self.assertEqual(order['symbol'], 'A')

        status = dummy.fetch_stock_order_status(order['id'])
        self.assertEqual(status['id'], 0)
        self.assertEqual(status['symbol'], 'A')
        self.assertEqual(status['quantity'], 2)
        self.assertEqual(status['filled_qty'], 2)
        self.assertEqual(status['side'], 'sell')
        self.assertEqual(status['time_in_force'], 'gtc')
        self.assertEqual(status['status'], 'filled')

    def test_sell(self):
        directory = pathlib.Path(__file__).parent.resolve()
        dummy = DummyBroker(str(directory) + '/../dummy_account.yaml')
        dummy.setup(['A'], '1MIN')
        order = dummy.sell('A', 2)
        self.assertEqual(order['type'], 'STOCK')
        self.assertEqual(order['id'], 0)
        self.assertEqual(order['symbol'], 'A')

        status = dummy.fetch_stock_order_status(order['id'])
        self.assertEqual(status['id'], 0)
        self.assertEqual(status['symbol'], 'A')
        self.assertEqual(status['quantity'], 2)
        self.assertEqual(status['filled_qty'], 2)
        self.assertEqual(status['side'], 'sell')
        self.assertEqual(status['time_in_force'], 'gtc')
        self.assertEqual(status['status'], 'filled')

    def test_order_option_limit(self):
        dummy = DummyBroker() 
        dummy.setup(['A'], '1MIN')
        exp_date = dt.datetime.now() + dt.timedelta(hours=5)
        order = dummy.order_option_limit('buy', 'A', 5, 25.75, 'OPTION', exp_date, 31.25)
        self.assertEqual(order['type'], 'OPTION')
        self.assertEqual(order['id'], 0)
        self.assertEqual(order['symbol'], 'A')

        status = dummy.fetch_option_order_status(order['id'])
        self.assertEqual(status['symbol'], 'A')
        self.assertEqual(status['quantity'], 5)


if __name__ == '__main__':
    unittest.main()