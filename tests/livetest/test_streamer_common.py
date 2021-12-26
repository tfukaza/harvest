import unittest
from harvest.api.robinhood import Robinhood
from harvest.api.webull import Webull
from harvest.api.alpaca import Alpaca
from harvest.api.kraken import Kraken
from harvest.api.paper import PaperBroker

from harvest.utils import *
import time
import os

secret_path = os.environ["SECRET_PATH"]
debugger.setLevel("DEBUG")

import functools

# A decorator to repeat the same test for all the brokers
def decorator_repeat_test(api_list):
    def decorator_test(func):
        @functools.wraps(func)
        def wrapper_repeat(*args):
            self = args[0]
            for api in api_list:
                print(f"Testing {api}")
                func(self, api)
        return wrapper_repeat
    return decorator_test


class TestLiveStreamer(unittest.TestCase):

    @decorator_repeat_test([Robinhood, Webull, Alpaca, Kraken])
    def test_setup(self, api):
        """
        Assuming that secret.yml is already created with proper parameters, test if the broker can read its contents and establish a connection with the server.
        """
        api = api(secret_path)
        interval = {
            "@DOGE": {"interval": Interval.MIN_5, "aggregations": []},
            "TWTR": {"interval": Interval.MIN_5, "aggregations": []},
        }
        stats = Stats(watchlist_cfg=interval)
        api.setup(stats, Account())
        self.assertTrue(True)

#     def test_fetch_prices(self, api):
#         """
#         Test if price history can be properly fetched for every interval supported
#         """
        
#         intervals = api.interval_list
#         interval = {
#             "TWTR": {"interval": intervals[0], "aggregations": intervals[1:]},
#             "@DOGE": {"interval": intervals[0], "aggregations": intervals[1:]},
#         }
#         stats = Stats(watchlist_cfg=interval)
#         api.setup(stats, Account())

#         for i in intervals:
#             df = api.fetch_price_history("TWTR", interval=i)["TWTR"]
#             self.assertEqual(
#                 sorted(list(df.columns.values)),
#                 sorted(["open", "high", "low", "close", "volume"]),
#             )
#             df = api.fetch_price_history("@DOGE", interval=i)["@DOGE"]
#             self.assertEqual(
#                 sorted(list(df.columns.values)),
#                 sorted(["open", "high", "low", "close", "volume"]),
#             )

#     def test_main(self, api):
#         """
#         Test if latest prices can be fetched.
#         """

#         def test_main(df):
#             self.assertEqual(len(df), 2)

        
#         interval = {
#             "TWTR": {"interval": Interval.MIN_5, "aggregations": []},
#             "@DOGE": {"interval": Interval.MIN_5, "aggregations": []},
#         }
#         stats = Stats(watchlist_cfg=interval)
#         api.setup(stats, Account(), test_main)

#         # Override timestamp to ensure is_freq() evaluates to True
#         stats.timestamp = epoch_zero()
#         api.main()

#     def test_chain_info(self, api):
#         """
#         Test if chain info can be fetched
#         """
        
#         interval = {
#             "TWTR": {"interval": Interval.MIN_5, "aggregations": []},
#         }
#         stats = Stats(watchlist_cfg=interval)
#         api.setup(stats, Account())

#         info = api.fetch_chain_info("TWTR")
#         self.assertGreater(len(info["exp_dates"]), 0)

#     def test_chain_data(self, api):
#         """
#         Test if chain data can be fetched
#         """
        
#         interval = {
#             "TWTR": {"interval": Interval.MIN_5, "aggregations": []},
#         }
#         stats = Stats(watchlist_cfg=interval)
#         api.setup(stats, Account())

#         dates = api.fetch_chain_info("TWTR")["exp_dates"]
#         data = api.fetch_chain_data("TWTR", dates[0])

#         self.assertGreater(len(data), 0)
#         self.assertListEqual(list(data.columns), ["exp_date", "strike", "type"])

#         sym = data.index[0]
#         df = api.fetch_option_market_data(sym)
#         self.assertTrue(True)

#     def test_buy_option(self, api):
        
#         interval = {
#             "TWTR": {"interval": Interval.MIN_5, "aggregations": []},
#         }
#         stats = Stats(watchlist_cfg=interval)
#         api.setup(stats, Account())

#         # Get a list of all options
#         dates = api.fetch_chain_info("TWTR")["exp_dates"]
#         data = api.fetch_chain_data("TWTR", dates[0])
#         option = data.iloc[0]

#         exp_date = option["exp_date"]
#         strike = option["strike"]

#         ret = api.order_option_limit("buy", "TWTR", 1, 0.01, "call", exp_date, strike)

#         time.sleep(5)

#         api.cancel_option_order(ret["order_id"])

#         self.assertTrue(True)

#     def test_buy_stock(self, api):
#         """
#         Test that it can buy stocks
#         """
        
#         interval = {
#             "TWTR": {"interval": Interval.MIN_5, "aggregations": []},
#         }
#         stats = Stats(watchlist_cfg=interval)
#         api.setup(stats, Account())

#         # Limit order TWTR stock at an extremely low limit price
#         # to ensure the order is not actually filled.
#         ret = api.order_stock_limit("buy", "TWTR", 1, 10.0)

#         time.sleep(5)

#         api.cancel_stock_order(ret["order_id"])


if __name__ == "__main__":
    unittest.main()
