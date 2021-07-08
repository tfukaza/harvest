![Header](docs/banner.png)

**⚠️WARNING⚠️**
Harvest is currently at **v0.0**, meaning the code is generally unstable. Use with caution. 
- Found a bug? We'll love it if you can take your time to [file a bug report](https://github.com/tfukaza/harvest/issues/new?assignees=&labels=bug&template=bug_report.md&title=%5B%F0%9F%AA%B0BUG%5D), so we can start fixing it. 
- Have ideas to improve or add a feature? [Submit a feature suggestion](https://github.com/tfukaza/harvest/issues/new?assignees=&labels=enhancement%2C+question&template=feature-request.md&title=%5B%F0%9F%92%A1Feature+Request%5D)!
- Can't find the info you need? [Request documentation](https://github.com/tfukaza/harvest/issues/new?assignees=&labels=documentation&template=documentation.md&title=%5B%F0%9F%93%9DDocumentation%5D)

## What is Harvest?
Harvest is a Python framework for algorithmic trading that packs a lot of punch:
- Trade stocks, cryptos, even options! (if your brokerage supports them)
- Backtest on historical data
- Paper trading

Visit Harvest's [website](https://tfukaza.github.io/harvest/) for more details.

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

Easy, right?

## Disclaimer
Harvest is an open-source passion project created by algo trading enthusiasts. 
- It is not officially associated with Robinhood LLC.  
- Tutorials and documentation solely exist to provide technical references of the code. They are not recommendations of any specific securities or strategies. 
- Use Harvest at your own responsibility. 
