# Builtins
import unittest

from harvest.algo import BaseAlgo 

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

if __name__ == '__main__':
    unittest.main()