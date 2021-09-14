# Builtins
import unittest
import pathlib
import shutil 

# Submodule imports
from harvest.trader import BackTester
from harvest.algo import BaseAlgo
from harvest.api.dummy import DummyStreamer
from harvest.utils import *

class TestTester(unittest.TestCase):    

    @classmethod
    def setUpClass(self):
        self.data_dir = 'data'

    # def test_start_do_nothing(self):
    #     """ Do a quick run-through of the BackTester 
    #     to ensure it can run without crashing.
    #     """
    #     s = DummyStreamer()
    #     t = BackTester(s)
    #     t.set_symbol('A')
    #     t.set_algo(BaseAlgo())
    #     t.start('1MIN', ['5MIN'])
    #     self.assertTrue(True)
    
    # This test is disabled for now since DummyStreamer returns
    # a large amount of data and tests take too long to run
    # def test_check_aggregation(self):
    #     """ 
    #     """
    #     t = BackTester(DummyStreamer())
    #     t.set_symbol('A')
    #     t.set_algo(BaseAlgo())
    #     t.start('1MIN', ['1DAY'])
        
    #     minutes = list(t.storage.load('A', Interval.MIN_1)['A']['close'])[-200:]
    #     days_agg = list(t.storage.load('A', Interval.DAY_1-16)['A']['close'])[-200:]

    #     self.assertListEqual(minutes, days_agg)
    
    @classmethod
    def tearDownClass(self):
        path = pathlib.Path(self.data_dir)
        shutil.rmtree(path)

if __name__ == '__main__':
    unittest.main()