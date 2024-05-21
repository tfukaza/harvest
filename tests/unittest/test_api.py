import datetime as dt
import time
import unittest

import pandas as pd
from _util import delete_save_files

from harvest.algo import BaseAlgo
from harvest.broker._base import Broker
from harvest.enum import BrokerType, Interval
from harvest.trader import PaperTrader
from harvest.util.helper import gen_data, utc_current_time


class TestBroker(unittest.TestCase):
    def test_stream_broker_timeout(self):
        t = PaperTrader(BrokerType.BASE_STREAMER, debug=True)
        t.set_symbol(["A", "B"])
        t.start_streamer = False
        t.skip_init = True

        t._init_param_streamer_broker("1MIN", [])
        stream = t.data_broker_ref
        stream.fetch_price_history = lambda x, y, z: pd.DataFrame()
        stream.fetch_account = lambda: {"cash": 100, "equity": 100}
        stream.trader_main = t.main
        stream.trader = t
        t.start(sync=False)

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
        stream.stats.timestamp = stream.stats.timestamp + dt.timedelta(minutes=1)

        # Only send data for A
        data = gen_data("A", 1)
        data.index = [stream.stats.timestamp + dt.timedelta(minutes=1)]
        data = {"A": data}
        stream.step(data)

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

        try:
            t._delete_account()
        except Exception:
            pass

    @delete_save_files(".")
    def test_timeout_cancel(self):
        t = PaperTrader(BrokerType.BASE_STREAMER, debug=True)
        t.set_algo(BaseAlgo())
        t.set_symbol(["A", "B"])
        t.start_streamer = False
        t.skip_init = True

        t._init_param_streamer_broker("1MIN", [])
        stream = t.data_broker_ref
        stream.trader = t
        stream.trader_main = t.main
        stream.fetch_price_history = lambda x, y, z: pd.DataFrame()
        stream.fetch_account = lambda: {"cash": 100, "equity": 100}
        t.start(sync=False)

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
        stream.step(data_a)

        # Wait
        time.sleep(0.1)
        stream.step(data_b)

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

        try:
            t._delete_account()
        except Exception:
            pass

    def test_exceptions(self):
        api = Broker()

        self.assertEqual(api.create_secret(), None)

        try:
            api.fetch_price_history("A", Interval.MIN_1, utc_current_time(), utc_current_time())
            self.assertTrue(False)
        except NotImplementedError as e:
            self.assertEqual(
                str(e),
                "Broker class does not support the method fetch_price_history.",
            )

        try:
            api.fetch_chain_info("A")
            self.assertTrue(False)
        except NotImplementedError as e:
            self.assertEqual(str(e), "Broker class does not support the method fetch_chain_info.")

        try:
            api.fetch_chain_data("A", utc_current_time())
            self.assertTrue(False)
        except NotImplementedError as e:
            self.assertEqual(str(e), "Broker class does not support the method fetch_chain_data.")

        try:
            api.fetch_option_market_data("A")
            self.assertTrue(False)
        except NotImplementedError as e:
            self.assertEqual(
                str(e),
                "Broker class does not support the method fetch_option_market_data.",
            )

        try:
            api.fetch_account()
            self.assertTrue(False)
        except NotImplementedError as e:
            self.assertEqual(str(e), "Broker class does not support the method fetch_account.")

        try:
            api.fetch_stock_order_status(0)
            self.assertTrue(False)
        except NotImplementedError as e:
            self.assertEqual(
                str(e),
                "Broker class does not support the method fetch_stock_order_status.",
            )

        try:
            api.fetch_option_order_status(0)
            self.assertTrue(False)
        except NotImplementedError as e:
            self.assertEqual(
                str(e),
                "Broker class does not support the method fetch_option_order_status.",
            )

        try:
            api.fetch_crypto_order_status(0)
            self.assertTrue(False)
        except NotImplementedError as e:
            self.assertEqual(
                str(e),
                "Broker class does not support the method fetch_crypto_order_status.",
            )

        try:
            api.order_stock_limit("buy", "A", 5, 7)
            self.assertTrue(False)
        except NotImplementedError as e:
            self.assertEqual(str(e), "Broker class does not support the method order_stock_limit.")
        try:
            api.order_crypto_limit("buy", "@A", 5, 7)
            self.assertTrue(False)
        except NotImplementedError as e:
            self.assertEqual(str(e), "Broker class does not support the method order_crypto_limit.")

        try:
            api.order_option_limit("buy", "A", 5, 7, "call", utc_current_time(), 8)
            self.assertTrue(False)
        except NotImplementedError as e:
            self.assertEqual(str(e), "Broker class does not support the method order_option_limit.")

        try:
            api.buy("A", -1, 0)
            self.assertTrue(False)
        except NotImplementedError as e:
            self.assertEqual(str(e), "Broker class does not support the method order_stock_limit.")

        try:
            api.sell("A", -1, 0)
            self.assertTrue(False)
        except NotImplementedError as e:
            self.assertEqual(str(e), "Broker class does not support the method order_stock_limit.")

    def test_base_cases(self):
        api = Broker()

        api.refresh_cred()
        api.exit()
        self.assertEqual(api.fetch_stock_positions(), [])
        self.assertEqual(api.fetch_option_positions(), [])
        self.assertEqual(api.fetch_crypto_positions(), [])
        self.assertEqual(api.fetch_order_queue(), [])


if __name__ == "__main__":
    unittest.main()
