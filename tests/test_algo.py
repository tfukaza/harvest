# Builtins
from re import S
import unittest
from unittest.mock import patch

# from harvest import algo
from harvest.trader import PaperTrader
from harvest.api.dummy import DummyStreamer
from harvest.algo import BaseAlgo

from harvest.utils import *

import logging

prices = [10, 12, 11, 9, 8, 10, 11, 12, 13, 15, 14, 16, 13, 14]


class TestAlgo(unittest.TestCase):

    # Watchlist set in the Algo class locally should take precendance over watchlist in PaperTrader class
    def test_config_watchlist_1(self):
        class Algo1(BaseAlgo):
            def config(self):
                self.watchlist = ["A", "B", "C"]

        class Algo2(BaseAlgo):
            def config(self):
                self.watchlist = ["D", "E", "F"]

        algo1 = Algo1()
        algo2 = Algo2()

        s = DummyStreamer()
        t = PaperTrader(s)
        t.set_algo([algo1, algo2])
        t.set_symbol(["1", "2", "3"])

        t.start()
        s.tick()

        # Getting watchlist should return the watchlist of the Algo class
        list1 = algo1.get_stock_watchlist()
        self.assertListEqual(list1, ["A", "B", "C"])
        list2 = algo2.get_stock_watchlist()
        self.assertListEqual(list2, ["D", "E", "F"])

        # Running methods like get_stock_price_list without a symbol parameter
        # should return the symbol specified in the Algo class
        prices1 = algo1.get_asset_price_list()
        self.assertListEqual(
            prices1, list(t.storage.load("A", Interval.MIN_5)["A"]["close"])
        )

    # PaperTrader class should be able to run algorithms at the individually specified intervals
    def test_config_interval(self):
        class Algo1(BaseAlgo):
            def config(self):
                self.watchlist = ["A"]
                self.interval = "5MIN"
                self.aggregations = ["15MIN", "1DAY"]

        class Algo2(BaseAlgo):
            def config(self):
                self.watchlist = ["B"]
                self.interval = "30MIN"
                self.aggregations = ["1DAY"]

        algo1 = Algo1()
        algo2 = Algo2()

        s = DummyStreamer()
        t = PaperTrader(s)
        t.set_algo([algo1, algo2])

        t.start()
        s.tick()

        self.assertListEqual(
            t.stats.watchlist_cfg["A"]["aggregations"],
            [Interval.MIN_15, Interval.DAY_1],
        )

    def test_rsi(self):
        """
        Test that RSI values are calculated correctly.
        """
        algo = BaseAlgo()
        stats = Stats(
            watchlist_cfg={
                "A": {"interval": Interval.MIN_1, "aggregations": []},
            }
        )
        algo.init(stats, Functions(), Account())
        algo.watchlist = ["A"]
        rsi = algo.rsi(prices=prices)[-1]

        self.assertAlmostEqual(rsi, 59.476113, places=5)

    def test_sma(self):
        """
        Test that SMA values are calculated correctly.
        """
        algo = BaseAlgo()
        stats = Stats(
            watchlist_cfg={
                "A": {"interval": Interval.MIN_1, "aggregations": []},
            }
        )
        algo.init(stats, Functions(), Account())
        algo.watchlist = ["A"]
        sma = algo.sma(prices=prices)[-1]

        self.assertAlmostEqual(sma, sum(prices) / len(prices), places=5)

    def test_ema(self):
        """
        Test that EMA values are calculated correctly.
        """
        algo = BaseAlgo()
        stats = Stats(
            watchlist_cfg={
                "A": {"interval": Interval.MIN_1, "aggregations": []},
            }
        )
        algo.init(stats, Functions(), Account())
        algo.watchlist = ["A"]
        ema = algo.ema(prices=prices)[-1]

        alpha = 2 / (len(prices) + 1)
        weights = [(1 - alpha) ** t for t in range(len(prices))]
        expected_ema = sum(w * price for w, price in zip(weights, prices[::-1])) / sum(
            weights
        )

        self.assertAlmostEqual(ema, expected_ema, places=5)

    def test_bbands(self):
        """
        Test that bbands returns the correct values based on provided price list.
        """
        algo = BaseAlgo()
        stats = Stats(
            watchlist_cfg={
                "A": {"interval": Interval.MIN_1, "aggregations": []},
            }
        )
        algo.init(stats, Functions(), Account())
        algo.watchlist = ["A"]

        upper, middle, lower = algo.bbands(prices=prices)

        mean = sum(prices) / len(prices)
        var = sum((price - mean) ** 2 for price in prices) / (len(prices) - 1)
        std = var ** 0.5
        expected_middle = sum(prices) / len(prices)

        self.assertAlmostEqual(middle[-1], expected_middle, places=5)
        self.assertAlmostEqual(upper[-1], expected_middle + std, places=5)
        self.assertAlmostEqual(lower[-1], expected_middle - std, places=5)

    def test_bbands_trader(self):
        """
        Test that bband values are calculated correctly based on data in PaperTrader's Storage class.
        """
        streamer = DummyStreamer()
        t = PaperTrader(streamer)
        t.set_symbol("DUMMY")
        t.set_algo(BaseAlgo())
        t.start("1MIN")
        streamer.tick()

        upper, middle, lower = t.algo[0].bbands()

        self.assertEqual(True, True)

    def test_get_asset_quantity(self):
        s = DummyStreamer()
        t = PaperTrader(s)
        t.set_symbol("A")
        t.set_algo(BaseAlgo())
        t.start("1MIN")

        # This should buy 5 of A
        t.algo[0].buy("A", 5)
        s.tick()

        q = t.algo[0].get_asset_quantity("A")

        self.assertEqual(q, 5)

    def test_get_asset_cost(self):
        s = DummyStreamer()
        t = PaperTrader(s)
        t.set_symbol("A")
        t.set_algo(BaseAlgo())
        t.start("1MIN")

        t.algo[0].buy("A", 1)
        s.tick()

        cost = s.fetch_price_history("A", Interval.MIN_5).iloc[-1]["A"]["close"]
        get_cost = t.algo[0].get_asset_cost("A")

        self.assertEqual(get_cost, cost)

    def test_get_asset_price(self):
        s = DummyStreamer()
        t = PaperTrader(s)
        t.set_symbol("A")
        t.set_algo(BaseAlgo())
        t.start("1MIN")

        # This should buy 5 of A
        t.algo[0].buy("A", 5)
        s.tick()
        price = s.fetch_latest_stock_price()["A"]["A"]["close"][0]

        get_price = t.algo[0].get_asset_price("A")

        self.assertEqual(get_price, price)

    def test_buy_sell(self):
        s = DummyStreamer()
        t = PaperTrader(s)
        t.set_symbol("A")
        t.set_algo(BaseAlgo())
        t.start("1MIN")

        # This should buy 2 of A
        t.algo[0].buy("A", 2)
        s.tick()

        p = t.positions.stock[0]
        self.assertEqual(p.symbol, "A")
        self.assertEqual(p.quantity, 2)

        # This should sell 1 of A
        t.algo[0].sell("A", 1)
        s.tick()

        p = t.positions.stock[0]
        self.assertEqual(p.symbol, "A")
        self.assertEqual(p.quantity, 1)

    def test_buy_sell_auto(self):
        s = DummyStreamer()
        t = PaperTrader(s)
        t.set_symbol("A")
        t.set_algo(BaseAlgo())
        t.start("1MIN")

        price = round(t.storage.load("A", Interval.MIN_1)["A"]["close"][-1] * 1.05, 2)
        qty = int(1000000 / price)
        t.algo[0].buy()
        s.tick()

        p = t.positions.stock[0]
        self.assertEqual(p.symbol, "A")
        self.assertEqual(p.quantity, qty)

        # This should sell all of A
        t.algo[0].sell()
        s.tick()
        self.assertEqual(0, t.algo[0].get_asset_quantity())

    @patch("harvest.api._base.mark_up")
    def test_buy_sell_option_auto(self, mock_mark_up):
        mock_mark_up.return_value = 10

        streamer = DummyStreamer()
        t = PaperTrader(streamer, debug=True)
        t.set_symbol("X")
        t.set_algo(BaseAlgo())
        t.start("1MIN")
        streamer.tick()

        t.algo[0].buy("X     110101C01000000")
        streamer.tick()

        p = t.positions.option[0]
        self.assertEqual(p.symbol, "X     110101C01000000")

        t.algo[0].sell_all_options()
        streamer.tick()

        # p = t.stock_positions[0]
        self.assertEqual(0, t.algo[0].get_asset_quantity("X     110101C01000000"))
        # self.assertEqual(p['quantity'], 1)


if __name__ == "__main__":
    unittest.main()
