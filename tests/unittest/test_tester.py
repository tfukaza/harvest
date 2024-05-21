# import pathlib
# import shutil
# import unittest

# from harvest.algo import BaseAlgo
# from harvest.broker.dummy import DummyDataBroker
# from harvest.enum import Interval


# class TestTester(unittest.TestCase):
#     def tear_up_down(self):
#         def wrapper(*args, **kwargs):
#             try:
#                 self(*args, **kwargs)
#             finally:
#                 path = pathlib.Path("data")
#                 shutil.rmtree(path)

#         return wrapper

#     @tear_up_down
#     def test_start_do_nothing(self):
#         """Do a quick run-through of the BackTester
#         to ensure it can run without crashing.
#         """
#         s = DummyDataBroker()
#         # Prevent streamer from running which will cause an infinite loop
#         s.start = lambda: None
#         t = BackTester(s, True)
#         t.set_symbol("A")
#         t.set_algo(BaseAlgo())
#         # TODO: Update code so "1DAY" also works
#         t.start("1MIN", ["5MIN"], period="2DAY")
#         self.assertTrue(True)

#     @tear_up_down
#     def test_check_aggregation(self):
#         s = DummyDataBroker()
#         # Prevent streamer from running which will cause an infinite loop
#         s.start = lambda: None
#         t = BackTester(s, True)
#         t.set_symbol("A")
#         t.set_algo(BaseAlgo())
#         t.start("1MIN", ["1DAY"], period="2DAY")

#         minutes = list(t.storage.load("A", Interval.MIN_1)["A"]["close"])[:10]
#         days_agg = list(t.storage.load("A", int(Interval.DAY_1) - 16)["A"]["close"])[:10]

#         self.assertListEqual(minutes, days_agg)

#     @tear_up_down
#     def test_check_run(self):
#         class TestAlgo(BaseAlgo):
#             def main(self):
#                 print(self.get_datetime())

#         s = DummyDataBroker()
#         # Prevent streamer from running which will cause an infinite loop
#         s.start = lambda: None
#         t = BackTester()
#         t.set_symbol("A")
#         t.set_algo(TestAlgo())
#         t.start("1MIN", ["1DAY"], period="2DAY")

#         self.assertTrue(True)


# if __name__ == "__main__":
#     unittest.main()
