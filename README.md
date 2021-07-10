![Header](docs/banner.png)
Harvest is a Python based framework providing a simple and intuitive framework for algorithmic trading. Visit Harvest's [**website**](https://tfukaza.github.io/harvest/) for details, tutorials, and documentation. 

<br />


[![codecov](https://codecov.io/gh/tfukaza/harvest/branch/main/graph/badge.svg?token=NQMXTBK2UO)](https://codecov.io/gh/tfukaza/harvest)
![run tests](https://github.com/tfukaza/harvest/actions/workflows/run-tests.yml/badge.svg)
![website](https://github.com/tfukaza/harvest/actions/workflows/build-website.yml/badge.svg)

---

**⚠️WARNING⚠️**
Harvest is currently at **v0.0**. Use with caution, and contributions are greatly appreciated. 
- 🪲 [File a bug report](https://github.com/tfukaza/harvest/issues/new?assignees=&labels=bug&template=bug_report.md&title=%5B%F0%9F%AA%B0BUG%5D)
- 💡 [Submit a feature suggestion](https://github.com/tfukaza/harvest/issues/new?assignees=&labels=enhancement%2C+question&template=feature-request.md&title=%5B%F0%9F%92%A1Feature+Request%5D)
- 📝 [Request documentation](https://github.com/tfukaza/harvest/issues/new?assignees=&labels=documentation&template=documentation.md&title=%5B%F0%9F%93%9DDocumentation%5D)

## Example
Below is minimal example of a crossover strategy for `TWTR` implemented with Harvest
```python
from harvest.algo import BaseAlgo
from harvest.trader import Trader
from harvest.broker.robinhood import RobinhoodBroker

class Watch(BaseAlgo):
    def main(self, _):
        sma_long = self.sma(period=50)
        sma_short = self.sma(period=20)
        if self.crossover(sma_long, sma_short):
            self.buy()
        elif self.crossover(sma_short, sma_long):
            self.sell()

if __name__ == "__main__":
    t = Trader( RobinhoodBroker() )
    t.set_symbol('TWTR')
    t.set_algo(Watch())
    t.start()
```
Piece of cake 🍰

## Installation
The only prerequisite is to have **Python version 3.8 or greater**.

Harvest is still early in development, so you'll have to install it directly from this repo. 
```bash
pip install -e git+https://github.com/tfukaza/harvest.git
```
Next, install the dependencies necessary for the brokerage of your choice. Currently, Harvest only supports Robinhood. 
```bash
pip install -e 'git+https://github.com/tfukaza/harvest.git#egg=harvest[Robinhood]'
```
Now you're all set!

## Disclaimer
- Harvest is not officially associated with Robinhood LLC.  
    - Robinhood was also not designed to be used for algo-trading. Excessive access to their API can result in your account getting locked. 
- Tutorials and documentation solely exist to provide technical references of the code. They are not recommendations of any specific securities or strategies. 
- Use Harvest at your own responsibility. 
