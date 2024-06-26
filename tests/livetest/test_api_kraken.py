# # Builtins
# import datetime as dt
# import os
# import time
# import unittest
# import unittest.mock

# from harvest.broker.kraken import Kraken
# from harvest.enum import Interval
# from harvest.utils import debugger, utc_current_time
# secret_path = os.environ["SECRET_PATH"]
# debugger.setLevel("DEBUG")


# class TestKraken(unittest.TestCase):
#     def test_current_time(self):
#         broker = Kraken(path=secret_path)

#         threshold = dt.timedelta(seconds=5)
#         current_time = broker.get_current_time()
#         self.assertTrue(utc_current_time() - current_time < threshold)

#         time.sleep(60)

#     def test_fetch_crypto_price(self):
#         broker = Kraken(path=secret_path)

#         # Use datetime with no timezone for start and end
#         end = dt.datetime.now()
#         start = end - dt.timedelta(hours=12)
#         results = broker.fetch_price_history("@BTC", Interval.MIN_1, start, end)
#         self.assertTrue(results.shape[0] > 0)
#         self.assertTrue(results.shape[1] == 5)

#         # Use datetime with timezone for start and end
#         start = start.astimezone(dt.timezone(dt.timedelta(hours=2)))
#         end = end.astimezone(dt.timezone(dt.timedelta(hours=2)))
#         results = broker.fetch_price_history("@DOGE", Interval.MIN_1, start, end)
#         self.assertTrue(results.shape[0] > 0)
#         self.assertTrue(results.shape[1] == 5)

#         # Use ISO 8601 string for start and end
#         start = start.isoformat()
#         end = end.isoformat()
#         results = broker.fetch_price_history("@BTC", Interval.MIN_1, start, end)
#         self.assertTrue(results.shape[0] > 0)
#         self.assertTrue(results.shape[1] == 5)

#     def test_market_time(self):
#         broker = Kraken(path=secret_path)

#         results = broker.fetch_market_hours(utc_current_time())
#         self.assertTrue("is_open" in results)
#         self.assertTrue("open_at" in results)
#         self.assertTrue("close_at" in results)

#         time.sleep(60)

#     def test_positions(self):
#         broker = Kraken(path=secret_path)

#         results = broker.fetch_stock_positions()
#         self.assertEqual(len(results), 0)
#         results = broker.fetch_option_positions()
#         self.assertEqual(len(results), 0)
#         results = broker.fetch_crypto_positions()
#         self.assertTrue(len(results) >= 0)

#         time.sleep(60)

#     def test_account(self):
#         broker = Kraken(path=secret_path)

#         results = broker.fetch_account()
#         self.assertTrue(results["equity"] >= 0)
#         self.assertTrue(results["cash"] >= 0)
#         self.assertTrue(results["buying_power"] >= 0)
#         self.assertGreater(results["multiplier"], 0)

#         time.sleep(60)

#     def test_buy_cancel(self):
#         broker = Kraken(path=secret_path)

#         # Failes with insufficent funds.
#         try:
#             results = broker.order_crypto_limit("buy", "@BTC", 1, 1.00)
#         except:
#             self.assertTrue(True)

#     @unittest.mock.patch("builtins.input", return_value="y")
#     @unittest.mock.patch("getpass.getpass", return_value="y")
#     def test_create_secret(self, mock_input, mock_pass):
#         broker = Kraken(path=secret_path)
#         results = broker.create_secret()
#         for key in broker.req_keys:
#             self.assertTrue(key in results)
#             self.assertEqual(results[key], "y")


# if __name__ == "__main__":
#     unittest.main()
