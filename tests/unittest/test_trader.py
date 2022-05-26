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
import pandas as pd

from harvest.definitions import *
from harvest.utils import gen_data

from _util import *


class TestLiveTrader(unittest.TestCase):

    def test_no_streamer_no_broker(self):
        """
        If no streamer or broker is specified, LiveTrader should default to Yahoo Streamer and Paper Broker
        """
        trader = LiveTrader()
        self.assertEqual(trader.streamer_str, "yahoo")
        self.assertEqual(trader.broker_str, "paper")
    
    def test_no_streamer_rh_broker(self):
        """
        If no streamer is specified but a broker is set, and the broker can be used as a streamer
        (which is almost always the case), LiveTrader should use the broker as the streamer
        """
        trader = LiveTrader(broker="robinhood")
        self.assertEqual(trader.streamer_str, "robinhood")
        self.assertEqual(trader.broker_str, "robinhood")
    
    def test_no_streamer_paper_broker(self):
        """
        If no streamer is specified but a paper broker is set, 
        LiveTrader should use the yahoo broker as the streamer
        """
        trader = LiveTrader(broker="paper")
        self.assertEqual(trader.streamer_str, "yahoo")
        self.assertEqual(trader.broker_str, "paper")
    
    def test_yahoo_streamer_no_broker(self):
        """
        If a streamer is specified but no broker, LiveTrader should default to use Paper Broker
        """
        trader = LiveTrader(streamer="robinhood")
        self.assertEqual(trader.streamer_str, "robinhood")
        self.assertEqual(trader.broker_str, "paper")
        
        trader_yh = LiveTrader(streamer="yahoo")
        self.assertEqual(trader_yh.streamer_str, "yahoo")
        self.assertEqual(trader_yh.broker_str, "paper")

    def test_broker_sync(self):
        """
        Test that the broker is synced with the streamer
        """
        trader, dummy, paper = create_trader_and_api("dummy", "paper", "1MIN", ["A"])
        # Add positions to the paper broker


    def test_trader_adding_symbol(self):
        t = PaperTrader(DummyStreamer())
        t.set_symbol("A")
        self.assertEqual(t.watchlist[0], "A")


    @delete_save_files(".")
    def test_start_do_nothing(self):
        _, _, _ = create_trader_and_api("dummy", "paper", "1MIN", ["A"])

    def test_invalid_aggregation(self):
        """If invalid aggregation is set, it should raise an error"""
        s = DummyStreamer()
        # Prevent streamer from running which will cause an infinite loop
        s.start = lambda: None
        t = PaperTrader(s)
        with self.assertRaises(Exception):
            t.start("30MIN", ["5MIN", "1DAY"])
    
    def _create_fake_calendar_df(self, open_today, close_today):
        df = pd.DataFrame(
            {
                "is_open": [True] * 24,
                "open_at": [open_today - dt.timedelta(days=24-i) for i in range(24)],
                "close_at": [close_today - dt.timedelta(days=24-i) for i in range(24)],
            }
        )
        return df

    def test_day_trade_detection_0(self):
        """
        Test that day trade detection returns the correct number of day trades in the past day.
        """
        open_today = dt.datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
        close_today = dt.datetime.now().replace(hour=16, minute=0, second=0, microsecond=0)
        df = self._create_fake_calendar_df(open_today, close_today)

        trader, dummy, paper = create_trader_and_api("dummy", "paper", "1MIN", ["A"])
        # Manually add transaction history of buying and selling shares on the same day
        trader.storage.storage_calendar = df
        trader.storage.store_transaction(open_today, "N/A", "A", "buy", 100, 1.0)
        trader.storage.store_transaction(open_today, "N/A", "A", "sell", 100, 1.0)

        daytrades = trader.day_trade_count()

        self.assertEqual(daytrades, 1)
    
    def test_day_trade_detection_1(self):
        """
        Test that day trade detection returns the correct number of day trades in the past day.
        If an asset is bought, partially sold on the same day, and sold again the same day,
        it should be counted as 1 day trade.
        """
        open_today = dt.datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
        close_today = dt.datetime.now().replace(hour=16, minute=0, second=0, microsecond=0)
        df = self._create_fake_calendar_df(open_today, close_today)

        trader, dummy, paper = create_trader_and_api("dummy", "paper", "1MIN", ["A"])
        # Manually add transaction history of buying and selling shares on the same day
        trader.storage.storage_calendar = df
        trader.storage.store_transaction(open_today, "N/A", "A", "buy", 100, 1.0)
        trader.storage.store_transaction(open_today, "N/A", "A", "sell", 50, 1.0)
        trader.storage.store_transaction(open_today, "N/A", "A", "sell", 30, 1.0)

        daytrades = trader.day_trade_count()

        self.assertEqual(daytrades, 1)
    
    def test_day_trade_detection_2(self):
        """
        Test that day trade detection returns the correct number of day trades in the past day.
        If an asset is bought, partially sold on the same day, and bought again the same day,
        it should be counted as 1 day trade.
        """
        open_today = dt.datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
        close_today = dt.datetime.now().replace(hour=16, minute=0, second=0, microsecond=0)
        df = self._create_fake_calendar_df(open_today, close_today)

        trader, dummy, paper = create_trader_and_api("dummy", "paper", "1MIN", ["A"])
        trader.storage.storage_calendar = df
        trader.storage.store_transaction(open_today, "N/A", "A", "buy", 100, 1.0)
        trader.storage.store_transaction(open_today, "N/A", "A", "sell", 50, 1.0)
        trader.storage.store_transaction(open_today, "N/A", "A", "buy", 50, 1.0)

        daytrades = trader.day_trade_count()

        self.assertEqual(daytrades, 1)
    
    def test_day_trade_detection_3(self):
        """
        Test that day trade detection returns the correct number of day trades in the past day.
        If an asset is bought, partially sold on the same day, bought again the same day,
        and then sold again the same day, it should be counted as 2 day trades.
        """
        open_today = dt.datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
        close_today = dt.datetime.now().replace(hour=16, minute=0, second=0, microsecond=0)
        df = self._create_fake_calendar_df(open_today, close_today)

        trader, dummy, paper = create_trader_and_api("dummy", "paper", "1MIN", ["A"])
        trader.storage.storage_calendar = df
        trader.storage.store_transaction(open_today, "N/A", "A", "buy", 100, 1.0)
        trader.storage.store_transaction(open_today, "N/A", "A", "sell", 50, 1.0)
        trader.storage.store_transaction(open_today, "N/A", "A", "buy", 50, 1.0)
        trader.storage.store_transaction(open_today, "N/A", "A", "sell", 50, 1.0)

        daytrades = trader.day_trade_count()

        self.assertEqual(daytrades, 2)
       


if __name__ == "__main__":
    unittest.main()
