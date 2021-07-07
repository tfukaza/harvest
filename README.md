![Header](docs/banner.png)

## What is Harvest?
Harvest is a Python framework for algorithmic trading, that packs a lot of punch:
- Trade stocks, cryptos, even options! (if your brokerage supports them)
- Backtest on historical data
- Paper trading

Visit Harvest's [website](https://tfukaza.github.io/harvest/) for more details.

# For Developers
Interested in coding for Harvest? Awesome! 🤟 But before you begin, skim through the following sections:

## Local Testing
While generic tests are built into the CI/CD workflow, ideally you should conduct testing on your local working environment before pushing. This is especially true if you are working on a new feature, debugging, or making large modifications. 

### Testing Harvest 
Testing Harvest often requires you to provide login credentials to access the brokers, so it is recommended that you test the code in a different directory than your working directory. 

For example, if you cloned this repo into `C:\Alice\document\harvest`, you can create a new directory `C:\Alice\document\testing`. All of your test codes and access credentials should then be stored in `testing` to ensure they don't accidentally get pushed to the public repo. You can run 
```
pip install ../harvest
``` 
from `testing` to install the latest codebase from your local machine.  

If you want to run the generic tests locally, run:
```
python -m unittest discover -s test
```

### Testing Websites
The Harvest project has two websites: one for the Harvest homepage, and the other is the web interface to monitor Harvest.

The Harvest homepage is a pre-rendered NextJS/React website. Navigate to `harvest/website`, and run 
```
npm run dev
``` 
to start a hot-reloading dev server. If you think the website looks good, run 
```
npm run build && npm run export
``` 
to make sure the website can build without any problems. 

`Details of Harvest web interface coming soon`

## Documentation
Refer to the `docs` folder for full documentation of the codebase. The documentation provided on the website is for end users and intentionally leaves out some parts. 

`TODO: Add more sections as needed`

# Misc.
## Collaborators
 Special thanks to the following developers for contributing to this project:
 - @shershah010
 - @Kimeiga


## Disclaimer
Harvest is an open-source passion project created by algo trading enthusiasts. 
- It is not officially associated with Robinhood LLC.  
- Use Harvest at your own responsibility. 
