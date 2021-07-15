# Builtins
import unittest
import time
# Submodule imports
from harvest import trader
from harvest.algo import BaseAlgo
from harvest.api.dummy import DummyStreamer
from harvest.api.paper import PaperBroker
#from harvest.api.robinhood import Robinhood


from harvest.utils import gen_data

class TestTrader(unittest.TestCase):    
    def test_trader_adding_symbol(self):
        t = trader.Trader()
        t.set_symbol('A')
        self.assertEqual(t.watch[0], 'A')

    def test_start_do_nothing(self):
        t = trader.Trader()
        t.set_symbol('A')
        t.set_algo(BaseAlgo())
        t.start('1MIN', kill_switch=True)

        self.assertTrue(True)
    
    def test_no_streamer(self):
        """If streamer is not specified, by default
        it should be set to DummyStreamer, and broker set to PaperBroker"""
        t = trader.Trader()
    
        self.assertIsInstance(t.streamer, DummyStreamer)
        self.assertIsInstance(t.broker, PaperBroker)
    
    # def test_broker_set(self):
    #     """If a single API class is set, it should be set as
    #     a streamer and a broker"""
    #     t = trader.Trader( Robinhood() )

    #     self.assertIsInstance(t.streamer, Robinhood)
    #     self.assertIsInstance(t.broker, Robinhood)
    
    def test_dummy_streamer(self):
        """If streamer is DummyStreamer, broker should be PaperBroker"""
        t = trader.Trader( DummyStreamer() )

        self.assertIsInstance(t.streamer, DummyStreamer)
        self.assertIsInstance(t.broker, PaperBroker)
    
    def test_invalid_aggregation(self):
        """If invalid aggregation is set, it should raise an error"""
        t = trader.Trader()
        with self.assertRaises(Exception):
            t.start('30MIN', ['5MIN', '1DAY'])
    
    def test_timeout(self):
        t = trader.Trader()
        t.set_symbol(['A', 'B'])
        t.start('1MIN', kill_switch=True)

        # Save the last datapoint of B
        b_data = t.storage.load('B', '1MIN')['B']['close'][-1]
        # Only send data for A
        data = {
            'A': gen_data('A', 1)
        }
        t.main(data)
        # Wait for the timeout
        time.sleep(2)
        # Check if B has been duplicated
        self.assertEqual(b_data, t.storage.load('B', '1MIN')['B']['close'][-1])
    
    def test_timeout_cancel(self):
        t = trader.Trader()
        t.set_symbol(['A', 'B'])
        t.start('1MIN', kill_switch=True)

        a_new = gen_data('A', 1)
        b_new = gen_data('B', 1)
        # Only send data for A
        data = {'A': a_new}
        t.main(data)
        time.sleep(0.3)
        data = {'B': b_new}
        t.main(data)
        # Check that the new data has been stored
        self.assertEqual(a_new['A']['close'][-1], t.storage.load('A', '1MIN')['A']['close'][-1])
        self.assertEqual(b_new['B']['close'][-1], t.storage.load('B', '1MIN')['B']['close'][-1])

if __name__ == '__main__':
    unittest.main()