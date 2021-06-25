
# Beginner's Guide

## Prerequisites

Make sure the following are installed beforehand:
- Python 3.8+  

It is recommeded to use a virtualenv or a version control system like Conda, though it is optional. 

## Installing

The library can be installed using 
```bash
pip install git+https://github.com/tfukaza/Harvest.git
```

Next, install libraries corresponding to which broker you want to use
```bash
pip install git+https://github.com/tfukaza/Harvest.git[BROKER]
```
Where `BROKER` is replaced by one of the following brokers supported by Harvest:
- `Robinhood`


Once you have everything installed, set up the login credentials:
- [For Robinhood](Robinhood.md)

## Writing a Simple Harvest Code

Harvest is designed to be simple and easy - there are only three modules you need to know.
- Trader: The main module responsible for managing the other modules.
- Broker: The module that communicates with the brokerage you are using.
- Algo: The module where you define your algorithm.

Before doing anything, we import the aforementioned modules.

```python
from harvest.algo import BaseAlgo
from harvest.trader import Trader
from harvest.broker.robinhood import RobinhoodBroker
```

First we create a Trader class

```python
if __name__ == "__main__":
    t = Trader( RobinhoodBroker() )
```
Few things happen here, and don't worry, this is as complex as Harvest will get (for now).
- The trader class is instantiated. Traders take two Brokers as input, a `streamer` and a `broker`. `streamer` is the broker used to retrieve stock/cryto data. `broker` is the brokerage used to place orders and manage your portfolio. 
- For this example, we initialize `RobinhoodBroker`. The broker automatically reads the credentials saved in `secret.yaml` and sets up a connection with the broker. 
- The Robinhood broker is specified as a streamer and will be used to get stock/crypto data. 
- If the broker is unspecified, Robinhood will also be used as a broker. 

Fortunately after this, things get pretty easy. We specify what stock to track, in this case Twitter (TWTR).
```python
    t.add_symbol('TWTR')
```

At this point, we define our algorithm. Algorithms are created by extending the `BaseAlgo` class.

```python
class Twitter(BaseAlgo):
    def algo_init(self):
        pass

    def handler(self, meta):
        pass
```

Every also must define two functions
- `algo_init`: Function called right before the algorithm starts
- `handler`: Function called at a specified interval. 

In this example, we create a simple algorithm that buys and sells a single stock.

```python
class Twitter(aseAlgo):
    def algo_init(self):
        self.hold = False

    def handler(self, meta):
        if self.hold:
            self.sell('TWTR', 1)    
            self.hold = False
        else:
            self.buy('TWTR', 1)
            self.hold = True
```
Finally, we tell the trader to use this algorithm, and run it.
Below is the final code after putting everything together.

```python
from harvest.algo import BaseAlgo
from harvest.trader import Trader
from harvest.broker.robinhood import RobinhoodBroker

class Twitter(BaseAlgo):
    def algo_init(self):
        self.hold = False

    def handler(self, meta):
        if self.hold:
            self.sell('TWTR', 1)    
            self.hold = False
        else:
            self.buy('TWTR', 1)
            self.hold = True

if __name__ == "__main__":
    t = Trader( RobinhoodBroker(), None )
    t.add_symbol('TWTR')
    t.set_algo(Twitter())
    t.run(interval='1DAY')
```

By specifying `interval='1DAY'` in `run`, the `_handler` will be called once every day.

Now you can log into Robinhood on your phone or computer, and watch Harvest automatically buy and sell Twitter stocks! 

For more examples, check out the sample codes in the `example` folder.

