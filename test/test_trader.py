# Builtins
import unittest
# Submodule imports
from harvest import trader
from harvest.algo import BaseAlgo
from harvest.api.dummy import DummyStreamer

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
        it should be set to DummyStreamer"""
        t = trader.Trader()
        t.set_symbol('A')
        t.set_algo(BaseAlgo())
        
        self.assertIsInstance(t.streamer, DummyStreamer)

if __name__ == '__main__':
    unittest.main()