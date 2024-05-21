import os
import unittest

from harvest.util.helper import debugger

secret_path = os.environ["SECRET_PATH"]
debugger.setLevel("DEBUG")


class TestLiveRobinhood(unittest.TestCase):
    pass


if __name__ == "__main__":
    unittest.main()
