# Builtins
import unittest
import time

# Submodule imports
from harvest.trader import PaperTrader
from harvest.algo import BaseAlgo
from harvest.api.dummy import DummyStreamer
from harvest.api.paper import PaperBroker

# from harvest.api.robinhood import Robinhood

import datetime as dt

from harvest.utils import gen_data


class TestPaperTrader(unittest.TestCase):
    def test_trader_adding_symbol(self):
        t = PaperTrader(DummyStreamer())
        t.set_symbol("A")
        self.assertEqual(t.watchlist_global[0], "A")

    def test_start_do_nothing(self):
        t = PaperTrader(DummyStreamer())
        t.set_symbol("A")
        t.set_algo(BaseAlgo())
        t.start("1MIN")

        self.assertTrue(True)

    def test_no_streamer(self):
        """
        If streamer is not specified, by default
        it should be set to DummyStreamer, and broker set to
        """
        t = PaperTrader(DummyStreamer())

        self.assertIsInstance(t.streamer, DummyStreamer)
        self.assertIsInstance(t.broker, PaperBroker)

    # def test_broker_set(self):
    #     """If a single API class is set, it should be set as
    #     a streamer and a broker"""
    #     t = PaperTrader( Robinhood() )

    #     self.assertIsInstance(t.streamer, Robinhood)
    #     self.assertIsInstance(t.broker, Robinhood)

    def test_dummy_streamer(self):
        """If streamer is DummyStreamer, broker should be PaperBroker"""
        t = PaperTrader(DummyStreamer())

        self.assertIsInstance(t.streamer, DummyStreamer)
        self.assertIsInstance(t.broker, PaperBroker)

    def test_invalid_aggregation(self):
        """If invalid aggregation is set, it should raise an error"""
        t = PaperTrader(DummyStreamer())
        with self.assertRaises(Exception):
            t.start("30MIN", ["5MIN", "1DAY"])


if __name__ == "__main__":
    unittest.main()
