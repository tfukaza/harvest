# Builtins
import unittest
import datetime as dt

# Submodule imports
from harvest import queue

class TestQueue(unittest.TestCase):
	def test_queue(self):
		# Test initialization
		q = queue.Queue()
		self.assertEqual(q.queue, {})

		# Test adding a symbol
		now = dt.datetime.now()
		q.init_symbol('A', '1MIN', now)
		self.assertEqual(q.get_symbol_interval_update('A', '1MIN'), now)
		self.assertTrue(q.get_symbol_interval('A', '1MIN').empty)

		# Test sets
		now = dt.datetime.now()
		q.set_symbol_interval_update('A', '1MIN', now)
		self.assertEqual(q.get_symbol_interval_update('A', '1MIN'), now)

if __name__ == '__main__':
    unittest.main()