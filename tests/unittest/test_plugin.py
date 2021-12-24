# Builtins
import unittest

from harvest.plugin._base import Plugin


class TestPlugin(unittest.TestCase):
    def test_init(self):
        plugin = Plugin("my_plugin", ["pandas", "finta", "yaml"])
        self.assertEqual(plugin.name, "my_plugin")


if __name__ == "__main__":
    unittest.main()
