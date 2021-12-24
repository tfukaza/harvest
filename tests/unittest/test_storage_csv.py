# Builtins
import shutil
import pathlib
import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from harvest.storage import CSVStorage
from harvest.utils import *


class TestCSVStorage(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.storage_dir = "test_csv_data"

    def test_create_storage(self):
        storage = CSVStorage(self.storage_dir)

        self.assertEqual(storage.storage_price, {})

    def test_simple_store(self):
        storage = CSVStorage(self.storage_dir)
        data = gen_data("A", 50)
        storage.store("A", Interval.MIN_1, data.copy(True))

        self.assertTrue(not pd.isna(data.iloc[0]["A"]["low"]))
        self.assertTrue("A" in list(storage.storage_price.keys()))
        self.assertEqual(list(storage.storage_price["A"].keys()), [Interval.MIN_1])

    def test_saved_load(self):
        storage1 = CSVStorage(self.storage_dir)
        data = gen_data("B", 50)
        storage1.store("B", Interval.MIN_1, data.copy(True))

        storage2 = CSVStorage(self.storage_dir)
        loaded_data = storage2.load("B", Interval.MIN_1)

        assert_frame_equal(loaded_data, data)

    @classmethod
    def tearDownClass(self):
        path = pathlib.Path(self.storage_dir)
        shutil.rmtree(path)


if __name__ == "__main__":
    unittest.main()
