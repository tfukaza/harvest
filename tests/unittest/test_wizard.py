# Builtins
import io
import unittest
import unittest.mock

from harvest.wizard import Wizard


class TestWizard(unittest.TestCase):
    def test_init(self):
        w = Wizard()

        self.assertEqual(w.text_counter, 0)
        self.assertEqual(w.prompt_counter, 0)

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_print(self, mock_stdout):
        w = Wizard()
        w.print("Hello")
        self.assertEqual(mock_stdout.getvalue(), "💬 Hello")

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_println(self, mock_stdout):
        w = Wizard()
        w.println("Hello")
        self.assertEqual(mock_stdout.getvalue(), "💬 Hello\n")

    @unittest.mock.patch("builtins.input", return_value="yes")
    def test_get_bool(self, mock_stdout):
        w = Wizard()
        b = w.get_bool()
        self.assertTrue(b)

    @unittest.mock.patch("builtins.input", return_value="hello")
    def test_get_string(self, mock_stdout):
        w = Wizard()
        s = w.get_string()
        self.assertEqual(s, "hello")

    @unittest.mock.patch("builtins.input", return_value="5")
    def test_get_int(self, mock_stdout):
        w = Wizard()
        i = w.get_int()
        self.assertEqual(i, 5)

    @unittest.mock.patch("builtins.input", return_value="")
    def test_wait(self, mock_stdout):
        w = Wizard()
        w.wait_for_input()
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
