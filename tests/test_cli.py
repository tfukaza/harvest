# Builtins
import os
import time
import unittest

from harvest import cli


class TestCLI(unittest.TestCase):
    def test_storage(self):
        for storage in cli.storages.values():
            self.assertTrue(callable(storage))

    def test_streamers(self):
        for streamer in cli.streamers.values():
            self.assertTrue(callable(streamer))

    def test_brokers(self):
        for broker in cli.brokers.values():
            self.assertTrue(callable(broker))

    def test_bad_storage(self):
        try:
            cli._get_storage("I don't exist")
            self.assertTrue(False)
        except ValueError:
            self.assertTrue(True)

    def test_bad_streamer(self):
        try:
            cli._get_streamer("I don't exist")
            self.assertTrue(False)
        except ValueError:
            self.assertTrue(True)

    def test_bad_broekrs(self):
        try:
            cli._get_broker("I don't exist")
            self.assertTrue(False)
        except ValueError:
            self.assertTrue(True)

    def test_start_basic(self):
        crossover = os.path.dirname(os.path.realpath(__file__)) + "/../examples"
        args = cli.parser.parse_args(
            ["start", "-o", "memory", "-s", "dummy", "-b", "paper", "-d", crossover]
        )
        cli.start(args, test=True)
        self.assertTrue(True)

    def test_start_complex(self):
        crossover = os.path.dirname(os.path.realpath(__file__)) + "/../examples"
        args = cli.parser.parse_args(
            ["start", "-o", "pickle", "-s", "yahoo", "-b", "paper", "-d", crossover]
        )
        cli.start(args, test=True)
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
