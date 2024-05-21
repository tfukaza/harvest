import datetime as dt
import unittest

from harvest.util.helper import Interval, check_interval


class TestUtils(unittest.TestCase):
    def test_is_freq(self):
        """If invalid aggregation is set, it should raise an error"""

        # If interval is '1MIN', it should always return True
        self.assertTrue(check_interval(dt.datetime(2000, 1, 1, 0, 0, 0), Interval.MIN_1))
        self.assertTrue(check_interval(dt.datetime(2000, 1, 1, 1, 1, 1), Interval.MIN_1))

        # If interval is '5MIN', it should return True every 5 minutes
        self.assertTrue(check_interval(dt.datetime(2000, 1, 1, 0, 0, 0), Interval.MIN_5))
        self.assertTrue(check_interval(dt.datetime(2000, 1, 1, 0, 35, 0), Interval.MIN_5))
        self.assertFalse(check_interval(dt.datetime(2000, 1, 1, 1, 59, 0), Interval.MIN_5))

        # If interval is '30MIN', it should return True every 30 minutes
        self.assertTrue(check_interval(dt.datetime(2000, 1, 1, 0, 0, 0), Interval.MIN_30))
        self.assertTrue(check_interval(dt.datetime(2000, 1, 1, 0, 30, 0), Interval.MIN_30))
        self.assertFalse(check_interval(dt.datetime(2000, 1, 1, 1, 35, 0), Interval.MIN_30))

        # If interval is '1HR', it should return True every hour
        self.assertTrue(check_interval(dt.datetime(2000, 1, 1, 0, 0, 0), Interval.HR_1))
        self.assertTrue(check_interval(dt.datetime(2000, 1, 1, 1, 0, 0), Interval.HR_1))
        self.assertFalse(check_interval(dt.datetime(2000, 1, 1, 1, 40, 0), Interval.HR_1))


if __name__ == "__main__":
    unittest.main()
