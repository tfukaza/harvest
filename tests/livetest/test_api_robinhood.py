import unittest
from harvest.api.robinhood import Robinhood
from harvest.api.paper import PaperBroker
from harvest.utils import *
import time
import os

secret_path = os.environ["SECRET_PATH"]

class TestLiveRobinhood(unittest.TestCase):

    def test_setup(self):
        """
        Assuming that secret.yml is already created with proper parameters,
        test if the broker can read its contents and establish a connection with the server.
        """
        rh = Robinhood(secret_path)
        interval = {
            "@BTC": {"interval": Interval.MIN_5, "aggregations": []},
            "SPY": {"interval": Interval.MIN_5, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        rh.setup(stats, Account())
        self.assertTrue(True)

    def test_fetch_prices(self):
        """
        Test API to get stock history
        """
        rh = Robinhood(secret_path)
        interval = {
            "SPY": {"interval": Interval.MIN_5, "aggregations": []},
            "@BTC": {"interval": Interval.MIN_5, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        rh.setup(stats, Account())
    
        df = rh.fetch_price_history("SPY", interval=Interval.MIN_5)["SPY"]
        self.assertEqual(
            sorted(list(df.columns.values)),
            sorted(["open", "high", "low", "close", "volume"]),
        )
        df = rh.fetch_price_history("BTC", interval=Interval.MIN_5)["BTC"]
        self.assertEqual(
            sorted(list(df.columns.values)),
            sorted(["open", "high", "low", "close", "volume"]),
        )
    
    def test_main(self):

        def test_main(df):
            self.assertEqual(len(df), 2)
            self.assertEqual(df["SPY"].columns[0][0], "SPY")
            self.assertEqual(df["@BTC"].columns[0][0], "@BTC")

        rh = Robinhood(secret_path)
        interval = {
            "SPY": {"interval": Interval.MIN_5, "aggregations": []},
            "@BTC": {"interval": Interval.MIN_5, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        rh.setup(stats, Account(), test_main)
        rh.main()
    
    def test_chain_info(self):
      
        rh = Robinhood(secret_path)
        interval = {
            "SPY": {"interval": Interval.MIN_5, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        rh.setup(stats, Account())

        info = rh.fetch_chain_info("SPY")
        self.assertGreater(len(info["exp_dates"]), 0)
    
    def test_chain_data(self):

        rh = Robinhood(secret_path)
        interval = {
            "LMND": {"interval": Interval.MIN_5, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        rh.setup(stats, Account())

        dates = rh.fetch_chain_info("LMND")["exp_dates"]
        data = rh.fetch_chain_data("LMND", dates[0])
        self.assertGreater(len(data), 0)
        self.assertListEqual(list(data.columns), ["exp_date", "strike", "type"])
        sym = data.index[0]
        df = rh.fetch_option_market_data(sym)
        self.assertTrue(True)

    def test_buy_option(self):
        rh = Robinhood(secret_path)
        interval = {
            "SPY": {"interval": Interval.MIN_5, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        rh.setup(stats, Account())

        # Get a list of all options
        dates = rh.fetch_chain_info("SPY")["exp_dates"]
        data = rh.fetch_chain_data("SPY", dates[0])
        option = data[0]

        exp_date = option["exp_date"]
        strike = option["strike"]

        ret = rh.order_option_limit(
            "buy", "SPY", 1, 0.01, "call", exp_date, strike
        )

        time.sleep(5)

        rh.cancel_option_order(ret["order_id"])

        self.assertTrue(True)

    def test_buy_stock(self):
        """
        Test that it can buy stocks
        """
        rh = Robinhood(secret_path)
        interval = {
            "SPY": {"interval": Interval.MIN_5, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        rh.setup(stats, Account())
    
        # Limit order SPY stock at an extremely low limit price
        # to ensure the order is not actually filled. 
        ret = rh.order_stock_limit('buy', "SPY", 1, 10.0)
        print(ret)

        time.sleep(5)

        rh.cancel_stock_order(ret["order_id"])
    


if __name__ == "__main__":
    unittest.main()
