# Builtins
import unittest
import time
# Submodule imports
from harvest.trader import Trader
from harvest.algo import BaseAlgo
from harvest.api.dummy import DummyStreamer
from harvest.api.paper import PaperBroker
#from harvest.api.robinhood import Robinhood

import datetime as dt

from harvest.utils import gen_data

class TestTrader(unittest.TestCase):    

    def test_trader_adding_symbol(self):
        t = Trader(DummyStreamer())
        t.set_symbol('A')
        self.assertEqual(t.watch[0], 'A')

    def test_start_do_nothing(self):
        t = Trader(DummyStreamer())
        t.set_symbol('A')
        t.set_algo(BaseAlgo())
        t.start('1MIN', kill_switch=True)

        self.assertTrue(True)
    
    def test_no_streamer(self):
        """
        If streamer is not specified, by default
        it should be set to DummyStreamer, and broker set to 
        """
        t = Trader(DummyStreamer())
    
        self.assertIsInstance(t.streamer, DummyStreamer)
        self.assertIsInstance(t.broker, PaperBroker)
    
    # def test_broker_set(self):
    #     """If a single API class is set, it should be set as
    #     a streamer and a broker"""
    #     t = Trader( Robinhood() )

    #     self.assertIsInstance(t.streamer, Robinhood)
    #     self.assertIsInstance(t.broker, Robinhood)
    
    def test_dummy_streamer(self):
        """If streamer is DummyStreamer, broker should be PaperBroker"""
        t = Trader( DummyStreamer() )

        self.assertIsInstance(t.streamer, DummyStreamer)
        self.assertIsInstance(t.broker, PaperBroker)
    
    def test_invalid_aggregation(self):
        """If invalid aggregation is set, it should raise an error"""
        t = Trader(DummyStreamer())
        with self.assertRaises(Exception):
            t.start('30MIN', ['5MIN', '1DAY'])
    
    def test_is_freq(self):
        """If invalid aggregation is set, it should raise an error"""
        t = Trader(DummyStreamer())
        t.fetch_interval = '1MIN'

        # If interval is '1MIN', it should always return True
        t.interval = '1MIN'
        self.assertTrue(t.is_freq(dt.datetime(2000,1,1,0,0,0))) 
        self.assertTrue(t.is_freq(dt.datetime(2000,1,1,1,1,1))) 

        # If interval is '5MIN', it should return True every 5 minutes
        t.interval = '5MIN'
        self.assertTrue(t.is_freq(dt.datetime(2000,1,1,0,5,0)))
        self.assertTrue(t.is_freq(dt.datetime(2000,1,1,1,35,0)))
        self.assertFalse(t.is_freq(dt.datetime(2000,1,1,1,36,0)))
        self.assertFalse(t.is_freq(dt.datetime(2000,1,1,1,59,0)))

        # If interval is '30MIN', it should return True every 30 minutes
        t.interval = '30MIN'
        self.assertTrue(t.is_freq(dt.datetime(2000,1,1,0,30,0)))
        self.assertTrue(t.is_freq(dt.datetime(2000,1,1,1,30,0)))
        self.assertFalse(t.is_freq(dt.datetime(2000,1,1,1,31,0)))
        self.assertFalse(t.is_freq(dt.datetime(2000,1,1,1,59,0)))

        # If interval is '1HR', it should return True every hour
        t.interval = '1HR'
        self.assertTrue(t.is_freq(dt.datetime(2000,1,1,0,0,0)))
        self.assertTrue(t.is_freq(dt.datetime(2000,1,1,1,0,0)))
        self.assertFalse(t.is_freq(dt.datetime(2000,1,1,1,1,0)))
        self.assertFalse(t.is_freq(dt.datetime(2000,1,1,1,59,0)))
    
    def test_timeout(self):
        t = Trader(DummyStreamer())
        t.set_symbol(['A', 'B'])
        t.start('1MIN', kill_switch=True)

        # Save the last datapoint of B
        a_cur = t.storage.load('A', '1MIN')
        b_cur = t.storage.load('B', '1MIN')
        # Only send data for A
        data = gen_data('A', 1)
        data.index=[a_cur.index[-1]+dt.timedelta(minutes=1)]
        data = {'A': data}
       
        t.main(data)
        # Wait for the timeout
        time.sleep(2)

        # Check if A has been added to storage
        self.assertEqual(a_cur['A']['close'][-1],       t.storage.load('A', '1MIN')['A']['close'][-2])
        self.assertEqual(data['A']['A']['close'][-1],   t.storage.load('A', '1MIN')['A']['close'][-1])
        # Check if B has been duplicated
        self.assertEqual(b_cur['B']['close'][-1],       t.storage.load('B', '1MIN')['B']['close'][-2])
        self.assertEqual(b_cur['B']['close'][-1],       t.storage.load('B', '1MIN')['B']['close'][-1])
    
    def test_timeout_cancel(self):
        t = Trader(DummyStreamer())
        t.set_symbol(['A', 'B'])
        t.start('1MIN', kill_switch=True)

        # Save the last datapoint of B
        a_cur = t.storage.load('A', '1MIN')
        b_cur = t.storage.load('B', '1MIN')
        # Only send data for A
        data_a = gen_data('A', 1)
        data_a.index=[a_cur.index[-1]+dt.timedelta(minutes=1)]
        data_a = {'A': data_a}
        data_b = gen_data('B', 1)
        data_b.index=[b_cur.index[-1]+dt.timedelta(minutes=1)]
        data_b = {'B': data_b}
        t.main(data_a)
        # Wait 
        time.sleep(0.1)
        t.main(data_b)

        # Check if A has been added to storage
        self.assertEqual(a_cur['A']['close'][-1],       t.storage.load('A', '1MIN')['A']['close'][-2])
        self.assertEqual(data_a['A']['A']['close'][-1],   t.storage.load('A', '1MIN')['A']['close'][-1])
        # Check if B has been added to storage
        self.assertEqual(b_cur['B']['close'][-1],       t.storage.load('B', '1MIN')['B']['close'][-2])
        self.assertEqual(data_b['B']['B']['close'][-1],   t.storage.load('B', '1MIN')['B']['close'][-1])

if __name__ == '__main__':
    unittest.main()