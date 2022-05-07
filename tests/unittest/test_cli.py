# Builtins
import os
import time
import unittest

from harvest import cli


class TestCLI(unittest.TestCase):


    def test_start_basic(self):
        crossover = os.path.dirname(os.path.realpath(__file__)) + "/../../examples"
        args = cli.parser.parse_args(
            ["start", "-o", "memory", "-s", "dummy", "-b", "paper", "-d", crossover]
        )
        cli.start(args, test=True)
        self.assertTrue(True)

    def test_start_complex(self):
        crossover = os.path.dirname(os.path.realpath(__file__)) + "/../../examples"
        args = cli.parser.parse_args(
            ["start", "-o", "pickle", "-s", "yahoo", "-b", "paper", "-d", crossover]
        )
        cli.start(args, test=True)
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
