# Builtins
import unittest
import datetime as dt

# Submodule imports
from harvest import queue

# External libraries
import pandas as pd

class TestQueue(unittest.TestCase):
	def test_queue(self):
		# Test initialization
		q = queue.Queue()
		self.assertEqual(q.queue, {})

		# Test adding a symbol
		q.init_symbol('A', '1MIN')
		self.assertEqual(q.get_symbol_interval_update('A', '1MIN'), dt.datetime(1970, 1, 1))
		self.assertTrue(q.get_symbol_interval('A', '1MIN').empty)

		# Test sets
		q.set_symbol_interval('A', '1MIN', pd.DataFrame({'A': [0, 1, 2], 'B': [3, 4, 5]}))
		self.assertEqual(q.get_symbol_interval('A', '1MIN').shape, (3, 2))

if __name__ == '__main__':
    unittest.main()