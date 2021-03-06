# Builtins
import unittest
import pathlib
import shutil

# Submodule imports
from harvest.trader import BackTester
from harvest.algo import BaseAlgo
from harvest.api.dummy import DummyStreamer
from harvest.definitions import *
from harvest.utils import *


class TestTester(unittest.TestCase):
    def tear_up_down(func):
        def wrapper(*args, **kwargs):
            try:
                func(*args, **kwargs)
            finally:
                path = pathlib.Path("data")
                shutil.rmtree(path)

        return wrapper

    @tear_up_down
    def test_start_do_nothing(self):
        """Do a quick run-through of the BackTester
        to ensure it can run without crashing.
        """
        s = DummyStreamer()
        # Prevent streamer from running which will cause an infinite loop
        s.start = lambda: None
        t = BackTester(s, True)
        t.set_symbol("A")
        t.set_algo(BaseAlgo())
        # TODO: Update code so "1DAY" also works
        t.start("1MIN", ["5MIN"], period="2DAY")
        self.assertTrue(True)

    @tear_up_down
    def test_check_aggregation(self):
        """ """
        s = DummyStreamer()
        # Prevent streamer from running which will cause an infinite loop
        s.start = lambda: None
        t = BackTester(s, True)
        t.set_symbol("A")
        t.set_algo(BaseAlgo())
        t.start("1MIN", ["1DAY"], period="2DAY")

        minutes = list(t.storage.load("A", Interval.MIN_1)["A"]["close"])[:10]
        days_agg = list(t.storage.load("A", int(Interval.DAY_1) - 16)["A"]["close"])[
            :10
        ]

        self.assertListEqual(minutes, days_agg)

    @tear_up_down
    def test_check_run(self):
        """ """

        class TestAlgo(BaseAlgo):
            def main(self):
                print(self.get_datetime())

        s = DummyStreamer()
        # Prevent streamer from running which will cause an infinite loop
        s.start = lambda: None
        t = BackTester()
        t.set_symbol("A")
        t.set_algo(TestAlgo())
        t.start("1MIN", ["1DAY"], period="2DAY")

        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
