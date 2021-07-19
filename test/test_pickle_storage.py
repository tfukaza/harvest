# Builtins
import shutil 
import pathlib
import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from harvest.storage import PickleStorage 
from harvest.utils import gen_data

class TestCSVStorage(unittest.TestCase):

    @classmethod
    def setUpClass(self):
        self.storage_dir = 'test_pickle_data'

    def test_create_storage(self):
        storage = PickleStorage(self.storage_dir)

        self.assertEqual(storage.storage, {})

    def test_simple_store(self):
        storage = PickleStorage(self.storage_dir)
        data = gen_data('A', 50)
        storage.store('A', '1MIN', data.copy(True))

        self.assertTrue(not pd.isna(data.iloc[0]['A']['low']))
        self.assertTrue('A' in list(storage.storage.keys()))
        self.assertEqual(list(storage.storage['A'].keys()), ['1MIN'])


    def test_saved_load(self):
        storage1 = PickleStorage(self.storage_dir)
        data = gen_data('A', 50)
        storage1.store('B', '1MIN', data.copy(True))

        storage2 = PickleStorage(self.storage_dir)
        loaded_data = storage2.load('B', '1MIN')

        assert_frame_equal(loaded_data, data)

    def test_open(self):
        storage = PickleStorage(self.storage_dir)
        data = gen_data('A', 50)
        storage.store('A', '1MIN', data.copy(True))

        loaded_data = storage.open('A', '1MIN')
        assert_frame_equal(loaded_data, data)

        empty_data = storage.open('I_DONT', 'EXISTS')
        assert_frame_equal(empty_data, pd.DataFrame())

    @classmethod
    def tearDownClass(self):
        path = pathlib.Path(self.storage_dir)
        shutil.rmtree(path)


if __name__ == '__main__':
    unittest.main()