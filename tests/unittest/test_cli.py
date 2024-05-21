# Builtins
import os
import unittest

from _util import delete_save_files

from harvest import cli


class TestCLI(unittest.TestCase):
    @delete_save_files(".")
    def test_start_basic(self):
        crossover = os.path.dirname(os.path.realpath(__file__)) + "/../../examples"
        args = cli.parser.parse_args(["start", "-o", "base", "-s", "dummy", "-b", "paper", "-d", crossover])
        cli.start(args, test=True)
        self.assertTrue(True)

    @delete_save_files(".")
    def test_start_complex(self):
        crossover = os.path.dirname(os.path.realpath(__file__)) + "/../../examples"
        args = cli.parser.parse_args(["start", "-o", "pickle", "-s", "yahoo", "-b", "paper", "-d", crossover])
        cli.start(args, test=True)
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
