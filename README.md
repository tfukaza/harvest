![Header](doc/Header.png)

## What is Harvest?
Harvest is a Python framework for algorithmic trading. This simple framework packs a lot of punch:
- Trade stocks, cryptos, even options! (if your brokerage supports them)
- Backtest on historical data
- Live trading
- Paper trading

## Why Harvest?
There are many other algorithmic trading frameworks available, like QuantConnect and BackTrader. What distinguishes Harvest are the core principles the framework is built around: 

😊**Intuitive** - The interface is designed to be easy to learn. Many of the complicated data structures and parameters are abstracted away and handled by Harvest. 

🛠️**Hackable** - The entire codebase is open-sourced, and is also modularized in a way that makes it easy for developers to add new, experimental features. 

## Example
To trade Twitter(TWTR) on Robinhood with an algorithm that monitors the RSI value, write the following code:
```python
from harvest.algo import BaseAlgo
from harvest.trader import Trader
from harvest.broker.robinhood import RobinhoodBroker

class Example(BaseAlgo):
    def algo_init(self):
        pass

    def handler(self, meta):
        rsi = self.rsi()[-1]
        if rsi < 30:
            self.buy('TWTR', 1)    
            return
        elif rsi > 70:
            self.sell('TWTR', 1)
            return

if __name__ == "__main__":
    t = Trader( RobinhoodBroker() )
    t.add_symbol('TWTR')
    t.set_algo(Example())
    t.run()
```
That's it! Piece of cake 🍰

# Getting Started
Following are resources to get you started with Harvest
 - [Beginner's Guide](doc/Intro.md): Learn how to install and create a basic algorithm with Harvest.
 - [Developer Guide](doc/dev.md): Guide for developers interested in contributing or modifying the code.  

 # Collaborators:
 Special thanks to the following developers for contributing to this project 🤟
 - @shershah010
 - @Kimeiga