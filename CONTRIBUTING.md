# Contributing
Thank you for helping out coding Harvest :). Your help is greatly appreciated. 

## Workflow
The coding process is relatively straight-forward:
1. Choose a task to work on from [open issues](https://github.com/tfukaza/harvest/issues). Alternatively, you can create your own task by [filing a bug report](https://github.com/tfukaza/harvest/issues/new?assignees=&labels=bug&template=bug_report.md&title=%5B%F0%9F%AA%B0BUG%5D) or [submitting a feature suggestion](https://github.com/tfukaza/harvest/issues/new?assignees=&labels=enhancement%2C+question&template=feature-request.md&title=%5B%F0%9F%92%A1Feature+Request%5D).
2. When working on an issue, notify others you are doing so, so other people are aware of who is working on what.
3. Clone the repo, and write your code in your own branch.
4. Run unit tests (as described in a following section). 
5. Lint your code using [Black](https://github.com/psf/black)
6. Push your code and make a PR to merge your code to main branch. Currently this project requires the approval of at least one contributor to merge the code. 

# Developer Guide
Read through the following guides to understand how to properly set up your development environment. 

## Harvest
Harvest requires a Python version of 3.9 or greater, and has a lot of dependencies, so it is highly recommended you use tools like Anaconda or VirtualEnv.

### Installing a Local Build
Run the following in the root of the project directory to install local changes you made. 
```bash
pip install .
```
### Unit Testing
After any modifications to the code, conduct unit tests by running:
```bash
python -m unittest discover -s tests
```
from the project's root directory. This will run the tests defined in the `tests` directory.

### Real-Time Testing
Unit testing does not cover all possible situations Harvest might encounter. Whenever possible, run the program as if you are a user on your own machine to test the code in real-life environments. This is especially true for codes for specific brokerages, which automated unit tests cannot cover.   

**Make sure you don't accidentally `git push` secret keys of the brokerage you are using.**

## Web Interface
The web interface of Harvest is made with the Svelte framework. 

### Running a Dev Server
Move to the `/gui` directory (not `/harvest/gui`) and run:
```bash
npm run dev
```
This will start the dev server. Any edits you make in `/gui/src` will automatically be built and saved to `/harvest/gui`. 

# Coding Practices
We want to make sure our code is stable and reliable - a good way to do that is to write clean, well-documented code. 

### Linting
This project uses the [Black](https://github.com/psf/black) linter to format the code. Before pushing any code, run the linter on every file you edited. This can usually be done by running:
```bash
python -m black .
```
in the root directory of the project.

### Logging
Good logs and debug messages can not only help users, but other developers understand what exactly Harvest is doing. Here are Harvest's guidelines to consistant logging:
* `DEBUG`: User will have to enable showing debug logs. Use it to log when important events or decisions are made by Harvest and not the user. For example:
    * Record when a streamer recieves data from a websocket endpoint.
    * Record when a file is read into storage.
* `INFO`: Let users know of important things that occur and to give users confidence that the program is running as expected. Logs events that the user created. For example:
    * Logs the parameters to a user's buy or sell.
* `WARNING`: Something bad happened and Harvest can automatically fix the issue without any user input. For example:
    * Warns if the user tries to get stock data from over a period of time that their account allows, we can fix that start time.
* `ERROR`: Something unexpected happened but can easily be fixed by the user. For example:
    * Log error if the user tried to add a stock ticker that does not exists.
    * Log error if the user tried to add a stock ticker to a broker that only supports crypto.
    * Log error if the user tried to get stock positions from a broker that only supports crypto, can return an empty list.
    * Log error if an API call failed.
* `raise Exception`: Something really bad happened and the entire system must be shutdown because there is no way to recover. The main difference between raising an exception and logging an error is because if the logged error is not addressed by the user the entire program will still be able to run while raising an exception requires the user to edit their code. For example:
    * Errors if a call to a function that should return something without a solid null case. For example returning an empty list is a fine null case but an empty dictionary or None isn't (since no one checks for the None case).
    * Errors if the user tried to get a particular stock position from a broker that only supports crypto. The user expects a dictionary but Harvest has no way of providing this. 

### Documenting
Every method, no matter how trivial, should be documented. This project uses the [reST format](https://stackabuse.com/python-docstrings/)  
