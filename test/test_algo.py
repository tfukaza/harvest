# Builtins
from harvest import algo
from harvest.trader import Trader
from harvest.api.dummy import DummyStreamer
import unittest

from harvest.algo import BaseAlgo 

from harvest.utils import gen_data

prices = [10, 12, 11, 9, 8, 10, 11, 12, 13, 15, 14, 16, 13, 14]

class TestAlgo(unittest.TestCase):
    def test_rsi(self):
        algo = BaseAlgo()
        algo.add_symbol('DUMMY')
        rsi = algo.rsi(prices=prices)[-1]
        
        self.assertAlmostEqual(rsi, 59.476113, places=5)

    def test_sma(self):
        algo = BaseAlgo()
        algo.add_symbol('DUMMY')
        sma = algo.sma(prices=prices)[-1]

        self.assertAlmostEqual(sma, sum(prices) / len(prices), places=5)

    def test_ema(self):
        algo = BaseAlgo()
        algo.add_symbol('DUMMY')
        ema = algo.ema(prices=prices)[-1]

        alpha = 2 / (len(prices) + 1)
        weights = [(1 - alpha) ** t for t in range(len(prices))]
        expected_ema = sum([w * price for w, price in zip(weights, prices[::-1])]) / sum(weights)

        self.assertAlmostEqual(ema, expected_ema, places=5)

    def test_bbands(self):
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
        t = Trader(DummyStreamer())
        t.set_symbol('DUMMY')
        t.set_algo(BaseAlgo())
        t.start("1MIN", kill_switch=True)

        upper, middle, lower = t.algo[0].bbands()

        self.assertEqual(True, True)
    
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
        self.assertEqual(0, t.algo[0].get_quantity())
    
    # def test_buy_sell_option_auto(self):
    #     t = Trader()
    #     t.set_symbol('A')
    #     t.set_algo(BaseAlgo())
    #     t.start("1MIN", kill_switch=True)

    #     t.algo[0].buy_option('AAA   01019901000000')
    #     a_new = gen_data('A', 1)
    #     t.main({'A': a_new})

    #     p = t.option_positions[0]
    #     self.assertEqual(p['symbol'], 'AAA   01019901000000')
    #     #self.assertEqual(p['quantity'], 2)

    #     # This should sell 1 of A
    #     t.algo[0].sell_option('AAA   01019901000000')
    #     a_new = gen_data('A', 1)
    #     t.main({'A': a_new})

    #     # p = t.stock_positions[0]
    #     self.assertEqual(0, t.algo[0].get_quantity('AAA   01019901000000'))
    #     #self.assertEqual(p['quantity'], 1)


if __name__ == '__main__':
    unittest.main()