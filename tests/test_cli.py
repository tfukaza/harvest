# Builtins
import os
import time
from multiprocessing import Process
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

    def test_start_basic(self):
        crossover = os.path.dirname(os.path.realpath(__file__)) + "/../examples/crossover.py"
        args = cli.parser.parse_args(["start", "-o", "memory", "-s", "dummy", "-b", "paper", crossover])
        print(args)
        process = Process(target=cli.start, args=(args,))
        process.start()
        time.sleep(1)
        process.kill()
        self.assertTrue(True)

    def test_start_complex(self):
        crossover = os.path.dirname(os.path.realpath(__file__)) + "/../examples/crossover.py"
        args = cli.parser.parse_args(["start", "-o", "pickle", "-s", "yahoo", "-b", "paper", crossover])
        process = Process(target=cli.start, args=(args,))
        process.start()
        time.sleep(1)
        process.kill()
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
