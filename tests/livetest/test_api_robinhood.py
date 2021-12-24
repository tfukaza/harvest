import unittest
from harvest.api.robinhood import Robinhood
from harvest.utils import *
import time
import os

secret_path = os.environ["SECRET_PATH"]

class TestLiveRobinhood(unittest.TestCase):

    def test_get_prices(self):
        """
        Test API to get stock history
        """
        rh = Robinhood(secret_path)
        interval = {
            "SPY": {"interval": Interval.MIN_5, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        rh.setup(stats, Account())
    
        ret = rh.fetch_price_history("SPY", Interval.MIN_5)
        print(ret)

        time.sleep(5)

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
