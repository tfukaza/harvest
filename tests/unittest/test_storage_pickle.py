# Builtins
import shutil
import pathlib
import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from harvest.storage import PickleStorage
from harvest.utils import *


class TestCSVStorage(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.storage_dir = "test_pickle_data"

    def test_create_storage(self):
        storage = PickleStorage(self.storage_dir)

        self.assertEqual(storage.storage_price, {})

    def test_simple_store(self):
        storage = PickleStorage(self.storage_dir)
        data = gen_data("A", 50)
        storage.store("A", Interval.MIN_1, data.copy(True))

        self.assertTrue(not pd.isna(data.iloc[0]["A"]["low"]))
        self.assertTrue("A" in list(storage.storage_price.keys()))
        self.assertEqual(list(storage.storage_price["A"].keys()), [Interval.MIN_1])

    def test_saved_load(self):
        storage1 = PickleStorage(self.storage_dir)
        data = gen_data("A", 50)
        storage1.store("B", Interval.MIN_1, data.copy(True))

        storage2 = PickleStorage(self.storage_dir)
        loaded_data = storage2.load("B", Interval.MIN_1)

        assert_frame_equal(loaded_data, data)

    def test_open(self):
        storage = PickleStorage(self.storage_dir)
        data = gen_data("A", 50)
        storage.store("A", Interval.MIN_1, data.copy(True))

        loaded_data = storage.open("A", Interval.MIN_1)
        assert_frame_equal(loaded_data, data)

    @classmethod
    def tearDownClass(self):
        path = pathlib.Path(self.storage_dir)
        shutil.rmtree(path)


if __name__ == "__main__":
    unittest.main()
