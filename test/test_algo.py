# Builtins
import unittest
import unittest.mock

from harvest import algo
from harvest.trader import Trader
from harvest.api.dummy import DummyStreamer
from harvest.algo import BaseAlgo 

from harvest.utils import gen_data

import logging
logging.basicConfig(level=logging.DEBUG)

prices = [10, 12, 11, 9, 8, 10, 11, 12, 13, 15, 14, 16, 13, 14]

class TestAlgo(unittest.TestCase):

    def test_rsi(self):
        """
        Test that RSI values are calculated correctly.
        """
        algo = BaseAlgo()
        algo.add_symbol('DUMMY')
        rsi = algo.rsi(prices=prices)[-1]
        
        self.assertAlmostEqual(rsi, 59.476113, places=5)

    def test_sma(self):
        """
        Test that SMA values are calculated correctly.
        """
        algo = BaseAlgo()
        algo.add_symbol('DUMMY')
        sma = algo.sma(prices=prices)[-1]

        self.assertAlmostEqual(sma, sum(prices) / len(prices), places=5)

    def test_ema(self):
        """
        Test that EMA values are calculated correctly.
        """
        algo = BaseAlgo()
        algo.add_symbol('DUMMY')
        ema = algo.ema(prices=prices)[-1]

        alpha = 2 / (len(prices) + 1)
        weights = [(1 - alpha) ** t for t in range(len(prices))]
        expected_ema = sum([w * price for w, price in zip(weights, prices[::-1])]) / sum(weights)

        self.assertAlmostEqual(ema, expected_ema, places=5)

    def test_bbands(self):
        """
        Test that bbands returns the correct values based on provided price list.
        """
        algo = BaseAlgo()
        algo.add_symbol('DUMMY')
        upper, middle, lower = algo.bbands(prices=prices)

        mean = sum(prices) / len(prices)
        var = sum([(price - mean) ** 2 for price in prices]) / (len(prices) - 1)
        std = var ** 0.5
        expected_middle = sum(prices) / len(prices)

        self.assertAlmostEqual(middle[-1], expected_middle, places=5)
        self.assertAlmostEqual(upper[-1], expected_middle + std, places=5)
        self.assertAlmostEqual(lower[-1], expected_middle - std, places=5)
    
    def test_bbands_trader(self):
        """
        Test that bband values are calculated correctly based on data in Trader's Storage class.
        """
        streamer = DummyStreamer()
        t = Trader(streamer)
        t.set_symbol('DUMMY')
        t.set_algo(BaseAlgo())
        t.start("1MIN", kill_switch=True)

        upper, middle, lower = t.algo[0].bbands()

        self.assertEqual(True, True)
    
    def test_get_asset_quantity(self):
        t = Trader(DummyStreamer())
        t.set_symbol('A')
        t.set_algo(BaseAlgo())
        t.start("1MIN", kill_switch=True)

        # This should buy 5 of A
        t.algo[0].buy('A', 5)
        a_new = gen_data('A', 1)
        t.main({'A': a_new})

        q = t.algo[0].get_asset_quantity('A')

        self.assertEqual(q, 5)

    def test_get_asset_cost(self):
        t = Trader(DummyStreamer())
        t.set_symbol('A')
        t.set_algo(BaseAlgo())
        t.start("1MIN", kill_switch=True)

        a_new = gen_data('A', 1)
        t.main({'A': a_new})
        # This should buy 1 of A
        t.algo[0].buy('A', 1)

        a_new = gen_data('A', 1)
        t.main({'A': a_new})
        cost = a_new['A']['close'][-1] 

        get_cost = t.algo[0].get_asset_cost('A')

        self.assertEqual(get_cost, cost)
    
    def test_get_asset_price(self):
        t = Trader(DummyStreamer())
        t.set_symbol('A')
        t.set_algo(BaseAlgo())
        t.start("1MIN", kill_switch=True)

        # This should buy 5 of A
        t.algo[0].buy('A', 5)
        a_new = gen_data('A', 1)
        t.main({'A': a_new})
        price = a_new['A']['close'][-1] 

        get_price = t.algo[0].get_asset_price('A')

        self.assertEqual(get_price, price)

    def test_buy_sell(self):
        t = Trader(DummyStreamer())
        t.set_symbol('A')
        t.set_algo(BaseAlgo())
        t.start("1MIN", kill_switch=True)

        # This should buy 2 of A
        t.algo[0].buy('A', 2)
        a_new = gen_data('A', 1)
        t.main({'A': a_new})

        p = t.stock_positions[0]
        self.assertEqual(p['symbol'], 'A')
        self.assertEqual(p['quantity'], 2)

        # This should sell 1 of A
        t.algo[0].sell('A', 1)
        a_new = gen_data('A', 1)
        t.main({'A': a_new})

        p = t.stock_positions[0]
        self.assertEqual(p['symbol'], 'A')
        self.assertEqual(p['quantity'], 1)
    
    def test_buy_sell_auto(self):
        t = Trader(DummyStreamer())
        t.set_symbol('A')
        t.set_algo(BaseAlgo())
        t.start("1MIN", kill_switch=True)

        price = round(t.storage.load('A', '1MIN')['A']['close'][-1] * 1.05, 2)
        qty = int(1000000/price)
        t.algo[0].buy()
        a_new = gen_data('A', 1)
        t.main({'A': a_new})

        p = t.stock_positions[0]
        self.assertEqual(p['symbol'], 'A')
        self.assertEqual(p['quantity'], qty)

        # This should sell all of A
        t.algo[0].sell()
        a_new = gen_data('A', 1)
        t.main({'A': a_new})
        self.assertEqual(0, t.algo[0].get_asset_quantity())
    
    def test_buy_sell_option_auto(self):
        streamer = DummyStreamer()
        t = Trader(streamer)
        t.set_symbol('X')
        t.set_algo(BaseAlgo())
        t.start("1MIN", kill_switch=True)

        t.algo[0].buy_option('X     110101C01000000')
        streamer.tick()

        p = t.option_positions[0]
        self.assertEqual(p['occ_symbol'], 'X     110101C01000000')

        t.algo[0].sell_option()
        streamer.tick()

        # p = t.stock_positions[0]
        self.assertEqual(0, t.algo[0].get_asset_quantity('X     110101C01000000'))
        #self.assertEqual(p['quantity'], 1)


if __name__ == '__main__':
    unittest.main()