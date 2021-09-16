# Builtins
import pathlib
import unittest
import datetime as dt
import os

from harvest.api.webullapi import Webull


class TestWebull(unittest.TestCase):
    def test_fetch_prices(self):
        if not "GITHUB_ACTION" in os.environ:
            return
        wb = Webull()
        df = wb.fetch_price_history("SPY", interval="1MIN")["SPY"]
        self.assertEqual(
            sorted(list(df.columns.values)),
            sorted(["open", "high", "low", "close", "volume"]),
        )

    def test_setup(self):
        if not "GITHUB_ACTION" in os.environ:
            return
        wb = Webull()
        watch = ["SPY", "AAPL", "@BTC", "@ETH"]
        wb.setup(watch, "1MIN")
        self.assertEqual(wb.watch, watch)
        self.assertEqual(wb.watch_stock, ["SPY", "AAPL"])
        self.assertEqual(wb.watch_crypto, ["@BTC", "@ETH"])

    def test_main(self):
        if not "GITHUB_ACTION" in os.environ:
            return
        def test_main(df):
            self.assertEqual(len(df), 3)
            self.assertEqual(df["SPY"].columns[0][0], "SPY")
            self.assertEqual(df["AAPL"].columns[0][0], "AAPL")
            self.assertEqual(df["@BTC"].columns[0][0], "@BTC")

        wb = Webull()
        watch = ["SPY", "AAPL", "@BTC"]
        wb.setup(watch, "1MIN", None, test_main)
        wb.main()

    def test_main_single(self):
        if not "GITHUB_ACTION" in os.environ:
            return
        def test_main(df):
            self.assertEqual(len(df), 1)
            self.assertEqual(df["SPY"].columns[0][0], "SPY")

        wb = Webull()
        watch = ["SPY"]
        wb.setup(watch, "1MIN", None, test_main)
        wb.main()

    def test_chain_info(self):
        if not "GITHUB_ACTION" in os.environ:
            return
        wb = Webull()
        watch = ["SPY"]
        wb.setup(watch, "1MIN", None, None)
        info = wb.fetch_chain_info("SPY")
        self.assertGreater(len(info["exp_dates"]), 0)

    def test_chain_data(self):
        if not "GITHUB_ACTION" in os.environ:
            return
        wb = Webull()
        watch = ["LMND"]
        wb.setup(watch, "1MIN", None, None)
        dates = wb.fetch_chain_info("LMND")["exp_dates"]
        data = wb.fetch_chain_data("LMND", dates[0])
        self.assertGreater(len(data), 0)
        self.assertListEqual(list(data.columns), ["exp_date", "strike", "type", "id"])

        sym = data.index[0]
        df = wb.fetch_option_market_data(sym)

        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
