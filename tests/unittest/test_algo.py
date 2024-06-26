import unittest

from _util import create_trader_and_api, delete_save_files

from harvest.algo import BaseAlgo
from harvest.enum import DataBrokerType, Interval, TradeBrokerType

prices = [10, 12, 11, 9, 8, 10, 11, 12, 13, 15, 14, 16, 13, 14]


class TestAlgo(unittest.TestCase):
    @delete_save_files(".")
    def test_config_watchlist_1(self):
        """
        Test that the specified watchlist is saved in the Algo class
        """

        class Algo1(BaseAlgo):
            def config(self):
                self.watchlist = ["A", "B", "C"]

        class Algo2(BaseAlgo):
            def config(self):
                self.watchlist = ["D", "E", "F"]

        algo1 = Algo1()
        algo2 = Algo2()

        trader, dummy, paper = create_trader_and_api(
            DataBrokerType.DUMMY, TradeBrokerType.PAPER, "5MIN", ["1", "2", "3"], [algo1, algo2]
        )

        # Getting watchlist should return the watchlist of the Algo class
        list1 = algo1.get_stock_watchlist()
        self.assertListEqual(list1, ["A", "B", "C"])
        list2 = algo2.get_stock_watchlist()
        self.assertListEqual(list2, ["D", "E", "F"])

        # Running methods like get_stock_price_list without a symbol parameter
        # should return the symbol specified in the Algo class
        prices1 = algo1.get_asset_price_list()
        self.assertListEqual(prices1, list(trader.storage.load("A", Interval.MIN_5)["A"]["close"]))

    # @patch("harvest.api._base.mark_up")
    # @delete_save_files(".")
    # def test_buy_sell_option_auto(self, mock_mark_up):

    #     mock_mark_up.return_value = 10

    #     t = PaperTrader(streamer="dummy", debug=True)
    #     t.start_streamer = False
    #     t.set_symbol("X")
    #     t.set_algo(BaseAlgo())
    #     t.start("1MIN")
    #     streamer = t.streamer
    #     streamer.main()

    #     t.algo[0].buy("X     110101C01000000")
    #     streamer.main()

    #     p = t.positions.option[0]
    #     self.assertEqual(p.symbol, "X110101C01000000")

    #     t.algo[0].sell_all_options()
    #     streamer.main()

    #     t.broker._delete_account()
    #     self.assertEqual(0, t.algo[0].get_asset_quantity("X     110101C01000000"))

    #     try:
    #         t._delete_account()
    #     except:
    #         pass


if __name__ == "__main__":
    unittest.main()
