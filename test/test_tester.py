# Builtins
import unittest
# Submodule imports
from harvest.trader import BackTester
from harvest.algo import BaseAlgo
from harvest.api.dummy import DummyStreamer

class TestTester(unittest.TestCase):    

    def test_tester_adding_symbol(self):
        t = BackTester(DummyStreamer())
        t.set_symbol('A')
        self.assertEqual(t.watch[0], 'A')

    def test_start_do_nothing(self):
        """ Do a quick run-through of the BackTester 
        to ensure it can run without crashing.
        """
        t = BackTester(DummyStreamer())
        t.set_symbol('A')
        t.set_algo(BaseAlgo())
        t.start('1MIN', ['5MIN'], kill_switch=True)
        self.assertTrue(True)
    
    def test_check_aggregation(self):
        """ 
        """
        t = BackTester(DummyStreamer())
        t.set_symbol('A')
        t.set_algo(BaseAlgo())
        t.start('1MIN', ['1DAY'], kill_switch=True)
        
        minutes = list(t.storage.load('A', '1MIN')['A']['close'])
        days_agg = list(t.storage.load('A', '-1DAY')['A']['close'])

        self.assertListEqual(minutes, days_agg)

if __name__ == '__main__':
    unittest.main()