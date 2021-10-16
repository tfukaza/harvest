# Builtins
import re
from getpass import getpass
import os

# Source: https://stackoverflow.com/questions/287871/how-to-print-colored-text-to-the-terminal
HEADER = "\033[95m"
OKBLUE = "\033[94m"
OKCYAN = "\033[96m"
OKGREEN = "\033[92m"
WARNING = "\033[93m"
FAIL = "\033[91m"
ENDC = "\033[0m"
BOLD = "\033[1m"
UNDERLINE = "\033[4m"


class Wizard:
    """
    The base class for all wizards that holds functions to get user inputs.
    Designed so that the *only* function the child classes should need to
    implement is the `create_secret` function.
    """

    def __init__(self):
        self.update_size()

        self.text_counter = 0
        self.prompt_counter = 0

    def update_size(self):
        # https://stackoverflow.com/questions/566746/how-to-get-linux-console-window-width-in-python
        with os.popen("stty size", "r") as dim:
            # with closes the subprocess opened by popen
            dimensions = dim.read().split()
        # If dimensions not given, i.e. not run in a terminal such as on github actions
        self.rows, self.columns = dimensions if len(dimensions) == 2 else (0, 0)
        self.columns = int(self.columns)
        self.rows = int(self.rows)

    def reset_counter(self) -> None:
        self.text_counter = 0
        self.prompt_counter = 0

    def print(self, text: str) -> None:
        if self.text_counter == 0:
            self.reset_counter()
            header = "💬 "
        else:
            header = "  "
        print(f"{header}{text}", end="")
        self.text_counter += 1

    def println(self, text: str) -> None:
        if self.text_counter == 0:
            self.reset_counter()
            header = "💬 "
        else:
            header = "  "
        print(f"{header}{text}")
        self.text_counter += 1

    def get_bool(
        self,
        prompt: str = "y/n",
        true_pat: str = r"y|yes",
        false_pat: str = r"n|no",
        default: str = None,
        persistent=True,
    ) -> bool:
        """
        Prompts the user for a binary decision. Ignores case in regex matching. Return False if the input does not match any pattern and persistent is False.

        :prompt: What to ask the user
        :true_pat: A (regex) pattern that is used to validate the user input is True
        :false_pat: A (regex) pattern that is used to validate the user input is False
        :default: A string that should return True when matched with its associated value's pattern. If None then ignored.
        :persistent: A bool that if True, and if default is None, will continue to prompt the user.
        """
        self.reset_counter()

        df = ""
        if default is not None:
            df = f"[{default}]"

        prompt = f"❓ {HEADER}{prompt} (y/n){df}{ENDC} "

        value = input(prompt)

        if re.fullmatch(true_pat, value, flags=re.IGNORECASE):
            return True

        elif re.fullmatch(false_pat, value, flags=re.IGNORECASE):
            return False

        if default is not None:
            return re.fullmatch(true_pat, default, flags=re.IGNORECASE)

        else:
            if persistent:
                return self.get_bool(prompt, true_pat, false_pat, default, persistent)
            else:
                return False

    def get_string(
        self, prompt: str = "input", pattern: str = ".+", persistent: bool = False
    ) -> str:
        """
        Prompts the user for any string, with an optional pattern, ignoring case. If persistent is True then will continuly prompt the user for input.

        :prompt: What to ask the user
        :pattern: A (regex) pattern that is used to validate the user input. Default to any string with at least 1 input
        :persistent:A bool that if True, will continue to prompt the user.
        """
        if self.prompt_counter == 0:
            self.reset_counter()
            print("❓ ", end="")

        value = input(f"{HEADER}{prompt}{ENDC}\n\t➔")

        if pattern is None or not persistent:
            return value
        elif re.fullmatch(pattern, value, flags=re.IGNORECASE):
            return value
        else:
            return self.get_string(prompt, pattern, persistent)

    def get_int(
        self, prompt="input number", default: int = None, persistent: bool = False
    ) -> int:
        """
        Prompts the user for an integer.

        :prompt: What to ask the user
        :default: If persistent is off, then this retuns if the user fails to specify a number.
        :persistent: If True then keep prompting the user for a valid input.
        """
        value = self.get_string(prompt, r"\d+", persistent)

        try:
            return int(value)
        except ValueError as e:
            print(f"Invalid input {value}, using {default} instead!\nError: {e}")
            return default

    def get_password(self, prompt="Password: ") -> str:
        """
        Prompts the user for a password.
        """
        return getpass(prompt)

    def wait_for_input(self) -> None:
        """
        Prompts the user for any input and to give the user the ability to do something while the program waits.
        """
        print("Press Enter...".rjust(self.columns))
        input("")
