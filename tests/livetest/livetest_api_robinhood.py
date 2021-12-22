import unittest
from harvest.api.paper import RobinhoodBroker
from harvest.utils import *
import time

class LiveTestRHBroker(unittest.TestCase):
    def test_buy_stock(self):
        """
        Test that it can buy stocks
        """
        rh = RobinhoodBroker("robinhood_secret.yaml")
        interval = {
            "SPY": {"interval": Interval.MIN_5, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        rh.setup(stats, Account())
    
        # Limit order SPY stock at an extremely low limit price
        # to ensure the order is not actually filled. 
        ret = rh.order_stock_limit('buy', "SPY", 1, 10.0)

        time.sleep(5)

        rh.cancel_stock_order(ret["order_id"])
    


if __name__ == "__main__":
    unittest.main()
