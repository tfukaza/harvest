# Builtins
import unittest
import time

# Submodule imports
from harvest.trader import *
from harvest.algo import BaseAlgo
from harvest.api.dummy import DummyStreamer
from harvest.api.paper import PaperBroker
from harvest.api.yahoo import YahooStreamer

# from harvest.api.robinhood import Robinhood

import datetime as dt

from harvest.definitions import *
from harvest.utils import gen_data

from _util import *


class TestLiveTrader(unittest.TestCase):

    def test_no_streamer_no_broker(self):
        """
        If no streamer or broker is specified, LiveTrader should default to Yahoo Streamer and Paper Broker
        """
        trader = LiveTrader()
        self.assertIsInstance(trader.streamer, YahooStreamer)
        self.assertIsInstance(trader.broker, PaperBroker)
    
    def test_no_streamer_rh_broker(self):
        """
        If no streamer is specified but a broker is set, and the broker can be used as a streamer
        (which is almost always the case), LiveTrader should use the broker as the streamer
        """
        trader = LiveTrader(broker="robinhood")
        self.assertIsInstance(trader.streamer, Robinhood)
        self.assertIsInstance(trader.broker, Robinhood)
        self.assertEqual(trader.broker, trader.streamer)
    
    def test_no_streamer_paper_broker(self):
        """
        If no streamer is specified but a paper broker is set, 
        LiveTrader should use the yahoo broker as the streamer
        """
        trader = LiveTrader(broker="paper")
        self.assertIsInstance(trader.streamer, YahooStreamer)
        self.assertIsInstance(trader.broker, PaperBroker)
    
    def test_yahoo_streamer_no_broker(self):
        """
        If a streamer is specified but no broker, LiveTrader should default to use Paper Broker
        """
        trader = LiveTrader(streamer="robinhood")
        self.assertIsInstance(trader.streamer, Robinhood)
        self.assertIsInstance(trader.broker, PaperBroker)
        
        trader_yh = LiveTrader(streamer="yahoo")
        self.assertIsInstance(trader_yh.streamer, YahooStreamer)
        self.assertIsInstance(trader_yh.broker, PaperBroker)

    def test_broker_sync(self):
        """
        Test that the broker is synced with the streamer
        """
        trader, dummy, paper = create_trader_and_api("dummy", "paper", "1MIN", [])
        # Add positions to the paper broker

    


    def test_trader_adding_symbol(self):
        t = PaperTrader(DummyStreamer())
        t.set_symbol("A")
        self.assertEqual(t.watchlist[0], "A")

        try:
            t._delete_account()
        except:
            pass

    @delete_save_files(".")
    def test_start_do_nothing(self):
        # Create a
        _, _, _ = create_trader_and_api("dummy", "paper", "1MIN", ["A"])

    # def test_no_streamer(self):
    #     """
    #     If streamer is not specified, by default
    #     it should be set to DummyStreamer, and broker set to
    #     """

    #     t = PaperTrader(DummyStreamer())

    #     self.assertIsInstance(t.streamer, DummyStreamer)
    #     self.assertIsInstance(t.broker, PaperBroker)

    #     try:
    #         t._delete_account()
    #     except:
    #         pass

    # def test_broker_set(self):
    #     """If a single API class is set, it should be set as
    #     a streamer and a broker"""
    #     t = PaperTrader( Robinhood() )

    #     self.assertIsInstance(t.streamer, Robinhood)
    #     self.assertIsInstance(t.broker, Robinhood)

    # def test_dummy_streamer(self):
    #     """If streamer is DummyStreamer, broker should be PaperBroker"""
    #     t = PaperTrader(DummyStreamer())

    #     self.assertIsInstance(t.streamer, DummyStreamer)
    #     self.assertIsInstance(t.broker, PaperBroker)

    #     try:
    #         t._delete_account()
    #     except:
    #         pass

    def test_invalid_aggregation(self):
        """If invalid aggregation is set, it should raise an error"""
        s = DummyStreamer()
        # Prevent streamer from running which will cause an infinite loop
        s.start = lambda: None
        t = PaperTrader(s)
        with self.assertRaises(Exception):
            t.start("30MIN", ["5MIN", "1DAY"])

        try:
            t._delete_account()
        except:
            pass


if __name__ == "__main__":
    unittest.main()
