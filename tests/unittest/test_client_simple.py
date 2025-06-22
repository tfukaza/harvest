import unittest
from _util import create_trader_and_api, delete_save_files
from harvest.enum import DataBrokerType, TradeBrokerType


class TestClient(unittest.TestCase):

    def test_basic_import(self):
        """Test that basic imports work"""
        self.assertTrue(True)

    @delete_save_files(".")
    def test_start_do_nothing(self):
        """Test that we can create a trader and api without errors"""
        try:
            _, _, _ = create_trader_and_api(DataBrokerType.DUMMY, TradeBrokerType.PAPER, "1MIN", ["A"])
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Failed to create trader and api: {e}")


if __name__ == '__main__':
    unittest.main()
