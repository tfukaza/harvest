# Contributing
Thank you for helping out coding Harvest :). Your help is greatly appreciated. 

## Workflow
The coding process is relatively straight-forward:
1. Choose a task to work on from [open issues](https://github.com/tfukaza/harvest/issues). Alternatively, you can create your own task by [filing a bug report](https://github.com/tfukaza/harvest/issues/new?assignees=&labels=bug&template=bug_report.md&title=%5B%F0%9F%AA%B0BUG%5D) or [submitting a feature suggestion](https://github.com/tfukaza/harvest/issues/new?assignees=&labels=enhancement%2C+question&template=feature-request.md&title=%5B%F0%9F%92%A1Feature+Request%5D).
2. When working on an issue, notify others you are doing so, so other people are aware of who is working on what.
3. Clone the repo, and write your code in your own branch.
4. Make a PR to merge your code to main branch. Currently this project requires the approval of at least one contributor to merge the code. 

# Developer Guide
Read through the following guides to understand how to properly set up your development environment. 

## Harvest
Harvest requires a Python version of 3.8 or greater, and has a lot of dependencies, so it is highly recommended you use tools like Anaconda or VirtualEnv.

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

**Make sure you don't accidentally `git push` secret keys of the brokerage you are using🤐**

## GUI
The web interface of Harvest is made with the Svelte framework. 

### Running a Dev Server
Move to the `/gui` directory (not `/harvest/gui`) and run:
```bash
npm run dev
```
This will start the dev server. Any edits you make in `/gui/src` will automatically be built and saved to `/harvest/gui`. 

## Website 
The Harvest website is built using Next.js (switching to 11ty soon).

### Running a Dev Server
Navigate to `/website`, and run 
```bash
npm run dev
``` 
to start a hot-reloading dev server. If you think the website looks good, run 
```bash
npm run build && npm run export
``` 
to make sure the website can build without any problems. 


