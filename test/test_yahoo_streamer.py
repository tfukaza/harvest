# Builtins
import pathlib
import unittest
import datetime as dt

from harvest.api.yahoo import YahooStreamer

class TestYahooStreamer(unittest.TestCase):
    def test_fetch_prices(self):
        yh = YahooStreamer()
        df = yh.fetch_price_history('SPY', '1HR')['SPY']
        self.assertEqual(list(df.columns.values), ['open', 'high', 'low', 'close', 'volume'])

    def test_setup(self):
        yh = YahooStreamer()
        watch = ['SPY', 'AAPL']
        yh.setup(watch, '1MIN')
        self.assertEqual(yh.watch, watch)
        self.assertEqual(yh.watch_stock, watch)
        self.assertListEqual(list(yh.watch_ticker.keys()), watch)
    
    def test_main(self):
        def test_main(df):
            self.assertEqual(len(df), 3)
            self.assertEqual(df['SPY'].columns[0][0], 'SPY')
            self.assertEqual(df['AAPL'].columns[0][0], 'AAPL')
            self.assertEqual(df['@BTC'].columns[0][0], '@BTC')
            
        yh = YahooStreamer()
        watch = ['SPY', 'AAPL', '@BTC']
        yh.setup(watch, '1MIN', None, test_main)
        yh.main()        
    
    def test_main_single(self):
        def test_main(df):
            self.assertEqual(len(df), 1)
            self.assertEqual(df['SPY'].columns[0][0], 'SPY')
            
        yh = YahooStreamer()
        watch = ['SPY']
        yh.setup(watch, '1MIN', None, test_main)
        yh.main()      
    
    def test_chain_info(self):
        yh = YahooStreamer()
        watch = ['SPY']
        yh.setup(watch, '1MIN', None, None)
        info = yh.fetch_chain_info('SPY')
        self.assertGreater(len(info['exp_dates']), 0)
    
    def test_chain_data(self):
        yh = YahooStreamer()
        watch = ['LMND']
        yh.setup(watch, '1MIN', None, None)
        dates = yh.fetch_chain_info('LMND')['exp_dates']
        data = yh.fetch_chain_data('LMND', dates[0])
        self.assertGreater(len(data), 0)
        self.assertListEqual(list(data.columns), ["exp_date", "strike", "type"])

        sym = data.index[0]
        df = yh.fetch_option_market_data(sym)

        self.assertTrue(True)


if __name__ == '__main__':
    unittest.main()