# Builtins
import unittest
import datetime as dt

# Submodule imports
from harvest import trader
from harvest.broker.dummy import DummyBroker

class TestTrader(unittest.TestCase):	
	def test_adding_symbol(self):
		dummy_broker = DummyBroker()
		t = trader.TestTrader(dummy_broker)
		t.add_symbol('A')
		self.assertEqual(t.watch[0], 'A')



if __name__ == '__main__':
    unittest.main()