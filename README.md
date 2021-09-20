![Header](docs/banner.png)
Harvest is a Python based framework providing a simple and intuitive framework for algorithmic trading. Visit Harvest's [**website**](https://tfukaza.github.io/harvest/) for details, tutorials, and documentation. 

<br />


[![codecov](https://codecov.io/gh/tfukaza/harvest/branch/main/graph/badge.svg?token=NQMXTBK2UO)](https://codecov.io/gh/tfukaza/harvest)
![run tests](https://github.com/tfukaza/harvest/actions/workflows/run-tests.yml/badge.svg)
![website](https://github.com/tfukaza/harvest/actions/workflows/build-website.yml/badge.svg)
[![Code style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
---

Comments? Questions? Join our [discussion](https://github.com/tfukaza/harvest/discussions)

**⚠️WARNING⚠️**
Harvest is currently at **v0.1.1**. The program is unstable and cointains many bugs. Use with caution, and contributions are greatly appreciated. 
- 🪲 [File a bug report](https://github.com/tfukaza/harvest/issues/new?assignees=&labels=bug&template=bug_report.md&title=%5B%F0%9F%AA%B0BUG%5D)
- 💡 [Submit a feature suggestion](https://github.com/tfukaza/harvest/issues/new?assignees=&labels=enhancement%2C+question&template=feature-request.md&title=%5B%F0%9F%92%A1Feature+Request%5D)
- 📝 [Request documentation](https://github.com/tfukaza/harvest/issues/new?assignees=&labels=documentation&template=documentation.md&title=%5B%F0%9F%93%9DDocumentation%5D)

# Example
Below is a minimal example of a crossover strategy for `TWTR` implemented with Harvest, tested on historical stock prices.
```python
from harvest.algo import *
from harvest.trader import *
from harvest.api import *

class Watch(algo.BaseAlgo):
    def main(self):
        sma_long = self.sma(period=50)
        sma_short = self.sma(period=20)
        if self.crossover(sma_long, sma_short):
            self.buy()
        elif self.crossover(sma_short, sma_long):
            self.sell()

if __name__ == "__main__":
    t = tester.BackTester()
    t.set_symbol('TWTR')
    t.set_algo(Watch())
    t.start()
```
If you want to see how this algorithm performs in real life, just change one line to enable paper trading:
```diff
- t = tester.BackTester()
+ t = trader.Trader()
```
Confident in your strategy? Deploy it using a broker of your choice (Currently only supports Robinhood). Again, you just need to change one line:
```diff
- t = trader.Trader()
+ t = trader.Trader(robinhood.Robinhood())
```
With Harvest, the process of testing, simulating, and deploying your strategies is a piece of cake 🍰

# Installation
There are few prerequisites:
- **Python 3.8+**
- pip

Once you have them, install via pip:
```bash
pip install harvest-python
```

Next, install the dependencies necessary for the brokerage of your choice:
```bash
pip install harvest-python[BROKER]
```
Replace `BROKER` with a brokerage/data source of your choice:
- Robinhood
- Alpaca (Coming soon)
- Polygon (Coming soon)

Now you're all set!

# Contributing
Contributions are greatly appreciated. Check out the [CONTRIBUTING](CONTRIBUTING.md) document for details, and [ABOUT](ABOUT.md) for the long-term goals of this project. 

Currently looking for...
- Python devs to code the framework
- Backend devs for the Flask backend
- Frontend devs to make the web GUI based on Svelte
- UX/UI designers for the web GUI

# Disclaimer
- Harvest is not officially associated with Robinhood LLC.  
    - Robinhood was also not designed to be used for algo-trading. Excessive access to their API can result in your account getting locked. 
- Tutorials and documentation solely exist to provide technical references of the code. They are not recommendations of any specific securities or strategies. 
- Use Harvest at your own responsibility. Developers of Harvest take no responsibility for any financial losses you incur by using Harvest.  
