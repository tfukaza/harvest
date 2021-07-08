![Header](docs/banner.png)

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
- Use Harvest at your own responsibility. 
