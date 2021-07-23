# Builtins
import re
from getpass import getpass
from logging import critical, error, info, warning, debug


class Wizard:
	"""
	The base class for all wizards that holds functions to get user inputs.
	Designed so that the *only* function the child classes should need to 
	implement is the `create_secret` function.
	"""

	def create_secret(self, path: str) -> bool:
		"""
		To be implemented by child classes to generate files with secrets in them. Returns True if the secret was successfully created and False otherwise.

		:path: The location to save the file with the secret.
		"""
		raise NotImplementedError('`create_secret` not implemented for this Wizard')

	def get_bool(self, prompt='y/n': str, true_pat=r'y|yes': str, false_pat=r'n|no': str, default=None: str, persistent=False) -> bool:
		"""
		Prompts the user for a binary decision. Ignores case in regex matching. Return False if the input does not match any pattern and persistent is False.

		:prompt: What to ask the user
		:true_pat: A (regex) pattern that is used to validate the user input is True
		:false_pat: A (regex) pattern that is used to validate the user input is False
		:default: A string that should return True when matched with its associated value's pattern. If None then ignored.
		:persistent: A bool that if True, and if default is None, will continue to prompt the user.
		"""

		if default is not None:
			prompt += f' [{default}]'

		value = input(prompt)

		if re.fullmatch(true_pat, value, flags=re.IGNORECASE):
			return True 

		elif re.fullmatch(true_pat, value, flags=re.IGNORECASE):
			return False

		if default is not None:
			return re.fullmatch(true_pat, default, flags=re.IGNORECASE)

		else:
			if persistent:
				return self.get_bool(prompt, true_pat, false_path, default, persistent) 
			else:
				return False

	def get_string(self, prompt='input': str, pattern='.+': str, persistent=False: bool) -> str:
		"""
		Prompts the user for any string, with an optional pattern, ignoring case. If persistent is True then will continuly prompt the user for input.

		:prompt: What to ask the user
		:pattern: A (regex) pattern that is used to validate the user input. Default to any string with at least 1 input
		:persistent:A bool that if True, will continue to prompt the user.
		"""

		value = input(prompt)

		if pattern is None or not persistent:
			return value 
		elif re.fullmatch(pattern, value, flags=re.IGNORECASE):
			return value
		else:
			return self.get_string(prompt, pattern, persistent)

	def get_int(self, prompt='input number', default=None: int, persistent=False: bool) -> int:
		"""
		Prompts the user for an integer.

		:prompt: What to ask the user
		:default: If persistent is off, then this retuns if the user fails to specify a number. 
		:persistent: If True then keep prompting the user for a valid input.
		"""

		value = get_string(prompt, r'\d+', persistent)

		try:
			return int(value)
		except ValueError as e:
			warning(f'Invalid input {value}, using {default} instead!\nError: {e}')
			return default


	def get_password(self, prompt='enter password') -> str:
		"""
		Prompts the user for a password.
		"""

		return getpass(prompt)

	def wait_for_input(self, prompt='press enter to continue') -> None:
		"""
		Prompts the user for any input and to give the user the ability to do something while the program waits.
		"""

		input(prompt)