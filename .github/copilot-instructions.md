# Copilot Instructions
This project is a Python framework for using AI agents to analyze market data and make real time trading decisions.
The primary focus is ease of use and flexibility, rather than raw performance.

## Tech Stack
- Python 3.11+
- Polars for data manipulation
- pytest for testing

## Coding Standards
- Use modern Python type hints rather than the typing module. E.g. use `list[str]` instead of `List[str]`.
- Type EVERYTHING, including function parameters and return types.
- Use Enums where appropriate, especially for fixed sets of values. Consider using variants like StrEnm and IntEnum for string and integer enums respectively.
- Prefer to use try/except for error handling instead of if/else checks, as it is considered more Pythonic.
- Use dataclasses for data structures, avoid generic dictionaries or tuples.
- Use f-strings for string formatting.
- Use `asyncio` for asynchronous code over threading.
- Have docstrings for everything, including functions, classes, enums, dataclasses, and modules.

## Coding Style
- Avoid adding inline comments to code unless you are explaining unintuitive behavior or complex logic.
- Usually, a docstring is sufficient to explain the purpose of a function or class.

## Documentation Tips
- Use Google style for docstrings.
- Always start with a single line summary of the function or class,
  followed by a more detailed description if necessary.
- Mention any side effects or exceptions that may be raised.
- Use type hints to clarify the expected types of parameters and return values.
- Note return values and types in the docstring.
- Note any Exceptions that may be raised in the docstring.
