# Builtins
from harvest.api.dummy import DummyStreamer
import pathlib
import unittest
import datetime as dt
import os

import pandas as pd


from harvest.algo import BaseAlgo
from harvest.api._base import API, StreamAPI
from harvest.api.dummy import DummyStreamer
from harvest.trader import PaperTrader
from harvest.utils import *


class TestAPI(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        with open("secret.yaml", "a") as f:
            f.write("data: 0")
            f.close()

    def test_timeout(self):
        stream = StreamAPI()
        stream.fetch_account = lambda: None
        stream.fetch_price_history = lambda x, y, z: pd.DataFrame()
        stream.fetch_account = lambda: {"cash": 100, "equity": 100}
        t = PaperTrader(stream, debug=True)

        stream.trader_main = t.main
        t.set_symbol(["A", "B"])

        t.start("1MIN", sync=False)

        # Save dummy data
        data = gen_data("A", 10)
        t.storage.store("A", Interval.MIN_1, data)
        data = gen_data("B", 10)
        t.storage.store("B", Interval.MIN_1, data)

        # Save the last datapoint of B
        a_cur = t.storage.load("A", Interval.MIN_1)
        b_cur = t.storage.load("B", Interval.MIN_1)
        print("test0", b_cur)

        # Manually advance timestamp of streamer
        stream.timestamp = stream.timestamp + dt.timedelta(minutes=1)

        # Only send data for A
        data = gen_data("A", 1)
        data.index = [stream.timestamp + dt.timedelta(minutes=1)]
        data = {"A": data}
        stream.main(data)

        # Wait for the timeout
        time.sleep(2)

        # Check if A has been added to storage
        self.assertEqual(
            a_cur["A"]["close"][-1],
            t.storage.load("A", Interval.MIN_1)["A"]["close"][-2],
        )
        self.assertEqual(
            data["A"]["A"]["close"][-1],
            t.storage.load("A", Interval.MIN_1)["A"]["close"][-1],
        )
        # Check if B has been set to 0
        print("Test", t.storage.load("B", Interval.MIN_1)["B"])
        self.assertEqual(
            b_cur["B"]["close"][-1],
            t.storage.load("B", Interval.MIN_1)["B"]["close"][-2],
        )
        self.assertEqual(
            0,
            t.storage.load("B", Interval.MIN_1)["B"]["close"][-1],
        )

    def test_timeout_cancel(self):
        stream = StreamAPI()
        stream.fetch_account = lambda: None
        stream.fetch_price_history = lambda x, y, z: pd.DataFrame()
        stream.fetch_account = lambda: {"cash": 100, "equity": 100}
        t = PaperTrader(stream)
        t.set_algo(BaseAlgo())
        stream.trader = t
        stream.trader_main = t.main
        t.set_symbol(["A", "B"])

        t.start("1MIN", sync=False)

        # Save dummy data
        data = gen_data("A", 10)
        t.storage.store("A", Interval.MIN_1, data)
        data = gen_data("B", 10)
        t.storage.store("B", Interval.MIN_1, data)

        # Save the last datapoint of B
        a_cur = t.storage.load("A", Interval.MIN_1)
        b_cur = t.storage.load("B", Interval.MIN_1)

        # Send data for A and B
        data_a = gen_data("A", 1)
        data_a.index = [a_cur.index[-1] + dt.timedelta(minutes=1)]
        data_a = {"A": data_a}
        data_b = gen_data("B", 1)
        data_b.index = [b_cur.index[-1] + dt.timedelta(minutes=1)]
        data_b = {"B": data_b}
        stream.main(data_a)

        # Wait
        time.sleep(0.1)
        stream.main(data_b)

        # Check if A has been added to storage
        self.assertEqual(
            a_cur["A"]["close"][-1],
            t.storage.load("A", Interval.MIN_1)["A"]["close"][-2],
        )
        self.assertEqual(
            data_a["A"]["A"]["close"][-1],
            t.storage.load("A", Interval.MIN_1)["A"]["close"][-1],
        )
        # Check if B has been added to storage
        self.assertEqual(
            b_cur["B"]["close"][-1],
            t.storage.load("B", Interval.MIN_1)["B"]["close"][-2],
        )
        self.assertEqual(
            data_b["B"]["B"]["close"][-1],
            t.storage.load("B", Interval.MIN_1)["B"]["close"][-1],
        )

    def test_exceptions(self):
        api = API()

        self.assertEqual(api.create_secret("I dont exists"), False)

        try:
            api.fetch_price_history("A", Interval.MIN_1, now(), now())
            self.assertTrue(False)
        except NotImplementedError as e:
            self.assertEqual(
                str(e),
                "API does not support this streamer method: `fetch_price_history`.",
            )

        try:
            api.fetch_chain_info("A")
            self.assertTrue(False)
        except NotImplementedError as e:
            self.assertEqual(
                str(e), "API does not support this streamer method: `fetch_chain_info`."
            )

        try:
            api.fetch_chain_data("A")
            self.assertTrue(False)
        except NotImplementedError as e:
            self.assertEqual(
                str(e), "API does not support this streamer method: `fetch_chain_data`."
            )

        try:
            api.fetch_option_market_data("A")
            self.assertTrue(False)
        except NotImplementedError as e:
            self.assertEqual(
                str(e),
                "API does not support this streamer method: `fetch_option_market_data`.",
            )

        try:
            api.fetch_account()
            self.assertTrue(False)
        except NotImplementedError as e:
            self.assertEqual(
                str(e), "API does not support this broker method: `fetch_account`."
            )

        try:
            api.fetch_stock_order_status(0)
            self.assertTrue(False)
        except NotImplementedError as e:
            self.assertEqual(
                str(e),
                "API does not support this broker method: `fetch_stock_order_status`.",
            )

        try:
            api.fetch_option_order_status(0)
            self.assertTrue(False)
        except NotImplementedError as e:
            self.assertEqual(
                str(e),
                "API does not support this broker method: `fetch_option_order_status`.",
            )

        try:
            api.fetch_crypto_order_status(0)
            self.assertTrue(False)
        except NotImplementedError as e:
            self.assertEqual(
                str(e),
                "API does not support this broker method: `fetch_crypto_order_status`.",
            )

        try:
            api.order_stock_limit("buy", "A", 5, 7)
            self.assertTrue(False)
        except NotImplementedError as e:
            self.assertEqual(
                str(e), "API does not support this broker method: `order_stock_limit`."
            )

        try:
            api.order_crypto_limit("buy", "@A", 5, 7)
            self.assertTrue(False)
        except NotImplementedError as e:
            self.assertEqual(
                str(e), "API does not support this broker method: `order_crypto_limit`."
            )

        try:
            api.order_option_limit("buy", "A", 5, 7, "call", now(), 8)
            self.assertTrue(False)
        except NotImplementedError as e:
            self.assertEqual(
                str(e), "API does not support this broker method: `order_option_limit`."
            )

        try:
            api.buy("A", -1, 0)
            self.assertTrue(False)
        except NotImplementedError as e:
            self.assertEqual(
                str(e), "API does not support this broker method: `order_stock_limit`."
            )

        try:
            api.sell("A", -1, 0)
            self.assertTrue(False)
        except NotImplementedError as e:
            self.assertEqual(
                str(e), "API does not support this broker method: `order_stock_limit`."
            )

    def test_base_cases(self):
        api = API()

        api.refresh_cred()
        api.exit()
        self.assertEqual(api.fetch_stock_positions(), [])
        self.assertEqual(api.fetch_option_positions(), [])
        self.assertEqual(api.fetch_crypto_positions(), [])
        self.assertEqual(api.fetch_order_queue(), [])

    def test_run_once(self):
        api = API()
        fn = lambda x: x + 1
        wrapper = API._run_once(fn)
        self.assertEqual(wrapper(5), 6)
        self.assertTrue(wrapper(5) is None)

    def test_timestamp(self):
        api = API()
        self.assertTrue(now() >= api.current_timestamp())

    @classmethod
    def tearDownClass(self):
        os.remove("secret.yaml")


if __name__ == "__main__":
    unittest.main()
