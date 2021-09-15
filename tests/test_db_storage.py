# Builtins
import os
import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from harvest.storage.database_storage import DBStorage
from harvest.utils import gen_data


class TestDBStorage(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.db_file = "foo.db"

        # Create the database file
        with open(self.db_file, "w") as f:
            pass

    def test_simple_load(self):
        storage = DBStorage("sqlite:///foo.db")
        data = gen_data("A", 50)
        storage.store("A", "1MIN", data.copy(True))

        loaded_data = storage.load("A", "1MIN")

        # sort_index to prevent order issues
        assert_frame_equal(loaded_data.sort_index(axis=1), data.sort_index(axis=1))

    def test_reset(self):
        storage = DBStorage("sqlite:///foo.db")
        data = gen_data("A", 50)
        storage.store("A", "1MIN", data.copy(True))
        storage.reset("A", "1MIN")
        loaded_data = storage.load("A", "1MIN")

        self.assertTrue(loaded_data is None)

    @classmethod
    def tearDownClass(self):
        if os.path.exists(self.db_file):
            os.remove(self.db_file)


if __name__ == "__main__":
    unittest.main()
