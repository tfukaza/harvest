# Builtins
import unittest
# Submodule imports
from harvest import trader
from harvest.algo import BaseAlgo
from harvest.broker.dummy import DummyBroker

class TestTrader(unittest.TestCase):    
    def test_trader_adding_symbol(self):
        dummy_broker = DummyBroker()
        t = trader.Trader(dummy_broker)
        t.set_symbol('A')
        self.assertEqual(t.watch[0], 'A')

    def test_start_do_nothing(self):
        dummy_broker = DummyBroker()
        t = trader.Trader(dummy_broker)
        t.set_symbol('A')
        t.set_algo(BaseAlgo())
        t.start('1MIN', kill_switch=True)

        self.assertTrue(True)
    
    def test_no_streamer(self):
        """If streamer is not specified, by default
        it should be set to DummyStreamer"""
        t = trader.Trader()
        t.set_symbol('A')
        t.set_algo(BaseAlgo())
        
        self.assertIsInstance(t.streamer, DummyBroker)

if __name__ == '__main__':
    unittest.main()