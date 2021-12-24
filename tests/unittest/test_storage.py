# Builtins
import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from harvest.storage import BaseStorage
from harvest.utils import *


class TestBaseStorage(unittest.TestCase):
    def test_create_storage(self):
        storage = BaseStorage()
        self.assertEqual(storage.storage_price, {})

    def test_simple_store(self):
        storage = BaseStorage()
        data = gen_data("A", 50)
        storage.store("A", Interval.MIN_1, data.copy(True))

        self.assertTrue(not pd.isna(data.iloc[0]["A"]["low"]))
        self.assertEqual(list(storage.storage_price.keys()), ["A"])
        self.assertEqual(list(storage.storage_price["A"].keys()), [Interval.MIN_1])

    def test_simple_load(self):
        storage = BaseStorage()
        data = gen_data("A", 50)
        storage.store("A", Interval.MIN_1, data.copy(True))
        loaded_data = storage.load("A", Interval.MIN_1)

        assert_frame_equal(loaded_data, data)

    def test_store_no_overlap(self):
        storage = BaseStorage()
        data = gen_data("A", 100)
        storage.store("A", Interval.MIN_1, data.copy(True).iloc[:50])
        storage.store("A", Interval.MIN_1, data.copy(True).iloc[50:])
        loaded_data = storage.load("A", Interval.MIN_1)

        self.assertTrue(not pd.isnull(data.iloc[0]["A"]["low"]))
        self.assertTrue(not pd.isnull(loaded_data.iloc[0]["A"]["low"]))
        assert_frame_equal(loaded_data, data)

    def test_store_overlap1(self):
        storage = BaseStorage()
        data = gen_data("A", 100)
        storage.store("A", Interval.MIN_1, data.copy(True).iloc[:75])
        storage.store("A", Interval.MIN_1, data.copy(True).iloc[25:])
        loaded_data = storage.load("A", Interval.MIN_1)

        self.assertTrue(not pd.isnull(data.iloc[0]["A"]["low"]))
        self.assertTrue(not pd.isnull(loaded_data.iloc[0]["A"]["low"]))
        assert_frame_equal(loaded_data, data)

    def test_store_overlap2(self):
        storage = BaseStorage()
        data = gen_data("A", 100)
        storage.store("A", Interval.MIN_1, data.copy(True).iloc[25:])
        storage.store("A", Interval.MIN_1, data.copy(True).iloc[:75])
        loaded_data = storage.load("A", Interval.MIN_1)

        self.assertTrue(not pd.isnull(data.iloc[0]["A"]["low"]))
        self.assertTrue(not pd.isnull(loaded_data.iloc[0]["A"]["low"]))
        assert_frame_equal(loaded_data, data)

    def test_store_within(self):
        storage = BaseStorage()
        data = gen_data("A", 100)
        storage.store("A", Interval.MIN_1, data.copy(True).iloc[25:75])
        storage.store("A", Interval.MIN_1, data.copy(True))
        loaded_data = storage.load("A", Interval.MIN_1)

        self.assertTrue(not pd.isnull(data.iloc[0]["A"]["low"]))
        self.assertTrue(not pd.isnull(loaded_data.iloc[0]["A"]["low"]))
        assert_frame_equal(loaded_data, data)

    def test_store_over(self):
        storage = BaseStorage()
        data = gen_data("A", 100)
        storage.store("A", Interval.MIN_1, data.copy(True))
        storage.store("A", Interval.MIN_1, data.copy(True).iloc[25:75])
        loaded_data = storage.load("A", Interval.MIN_1)

        self.assertTrue(not pd.isnull(data.iloc[0]["A"]["low"]))
        self.assertTrue(not pd.isnull(loaded_data.iloc[0]["A"]["low"]))
        assert_frame_equal(loaded_data, data)

    def test_load_no_interval(self):
        storage = BaseStorage()
        data = gen_data("A", 50)
        storage.store("A", Interval.MIN_1, data.copy(True))
        loaded_data = storage.load("A")

        assert_frame_equal(loaded_data, data)

    def test_store_gap(self):
        storage = BaseStorage()
        data = gen_data("A", 100)
        storage.store("A", Interval.MIN_1, data.copy(True).iloc[:25])
        storage.store("A", Interval.MIN_1, data.copy(True).iloc[75:])
        loaded_data = storage.load("A", Interval.MIN_1)

        self.assertTrue(not pd.isnull(data.iloc[0]["A"]["low"]))
        self.assertTrue(not pd.isnull(loaded_data.iloc[0]["A"]["low"]))
        assert_frame_equal(loaded_data, data.iloc[:25].append(data.iloc[75:]))

    # def test_agg_load(self):
    #     storage = BaseStorage()
    #     data = gen_data("A", 100)
    #     storage.store("A", Interval.MIN_1, data.copy(True))
    #     loaded_data = storage.load("A", Interval.MIN_1)

    #     self.assertTrue(not pd.isnull(data.iloc[0]["A"]["low"]))
    #     self.assertTrue(not pd.isnull(loaded_data.iloc[0]["A"]["low"]))
    #     self.assertTrue(loaded_data.shape, (20, 5))


if __name__ == "__main__":
    unittest.main()
