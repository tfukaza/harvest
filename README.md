![Header](doc/Header.png)

🚨**WARNING**🚨   
This library is still in early alpha, and the code is generally unstable. APIs and general functionality are subject to frequent changes. 

## What is Harvest?
Harvest is a framework to develop algorithms for trading stocks, options, and cryptocurrencies. In a single framework, you can easily test and deploy algorithms through various brokers. 

## Why Harvest?
There are many other algo trading frameworks availible, such as QuantConnect and BackTrader. What distinguishes Harvst is the two core principles the codebase is built around: 

😊**Intutive** - The interface is designed to be easy to learn. Many of the complicated data structures and parameters are abstracted away and handeled by Harvest. 

🛠️**Hackable** - The entire codebase is open-sourced, and is also modularized in a way that makes it easy for developers to add new, experimental features. 


## Example
To write an algorithm that monitors the RSI value of Twitter(TWTR) and makes trades based on its value, this is all you need to write:

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

Easy, right?

# Getting Started
Following are resoruces to get you started with Harvest
 - [Beginner's Guide](doc/Intro.md): Learn how to install and create a basic algorithm with Harvest.
 - [Developer Guide](doc/dev.md): Guide for developers interested in contributing or modifying the code.  

 # Collaborators:
 Special thanks to the following developers for contributing to this project 🤟
 - @shershah010