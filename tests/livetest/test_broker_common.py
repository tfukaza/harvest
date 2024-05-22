import os
import time
import unittest

from harvest.broker.robinhood import RobinhoodBroker
from harvest.definitions import Account, Interval, Stats
from harvest.util.helper import debugger

secret_path = os.environ["SECRET_PATH"]
debugger.setLevel("DEBUG")

import functools


# A decorator to repeat the same test for all the brokers
def decorator_repeat_test(broker_list):
    def decorator_test(func):
        @functools.wraps(func)
        def wrapper_repeat(*args):
            self = args[0]
            for api in broker_list:
                print(f"Testing {api}")
                func(self, api)

        return wrapper_repeat

    return decorator_test


class TestLiveBroker(unittest.TestCase):
    @decorator_repeat_test([RobinhoodBroker])
    def test_buy_option(self, api):
        api = api(secret_path)
        interval = {
            "TWTR": {"interval": Interval.MIN_5, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        api.setup(stats, Account())

        # Get a list of all options
        dates = api.fetch_chain_info("TWTR")["exp_dates"]
        data = api.fetch_chain_data("TWTR", dates[1])
        option = data.iloc[0]

        exp_date = option["exp_date"]
        strike = option["strike"]

        ret = api.order_option_limit("buy", "TWTR", 1, 0.01, "call", exp_date, strike)

        time.sleep(5)

        api.cancel_option_order(ret["order_id"])

        self.assertTrue(True)

    @decorator_repeat_test([RobinhoodBroker])
    def test_buy_stock(self, api):
        """
        Test that it can buy stocks
        """
        api = api(secret_path)
        interval = {
            "TWTR": {"interval": Interval.MIN_5, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        api.setup(stats, Account())

        # Limit order TWTR stock at an extremely low limit price
        # to ensure the order is not actually filled.
        ret = api.order_stock_limit("buy", "TWTR", 1, 10.0)

        time.sleep(5)

        api.cancel_stock_order(ret["order_id"])

    @decorator_repeat_test([RobinhoodBroker])
    def test_buy_crypto(self, api):
        """
        Test that it can buy crypto
        """
        api = api(secret_path)
        interval = {
            "@DOGE": {"interval": Interval.MIN_5, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        api.setup(stats, Account())

        # Limit order DOGE at an extremely low limit price
        # to ensure the order is not actually filled.
        ret = api.order_crypto_limit("buy", "@DOGE", 1, 0.10)

        time.sleep(5)

        api.cancel_crypto_order(ret["order_id"])


if __name__ == "__main__":
    unittest.main()
