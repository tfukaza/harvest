# Builtins
import asyncio
import re
import datetime as dt
import threading
from logging import warning, debug
import time
from signal import signal, SIGINT
from sys import exit

# External libraries
import pandas as pd
import pytz

# Submodule imports
import harvest.utils as utils
from harvest.storage import BaseStorage
from harvest.broker.dummy import DummyBroker
from harvest.algo import BaseAlgo
from harvest.storage import BaseStorage

class Trader:
    """
    :watch: Watchlist containing all stock and cryptos to monitor.
        The user may or may not own them. Note it does NOT contain options. 
    :broker: Both the broker and streamer store a Broker object.
        Broker places orders and retrieves latest account info like equity.
    :streamer: Streamer retrieves the latest stock price and calls handler().
    """

    interval_list = ['1MIN', '5MIN', '15MIN', '30MIN', '1HR', '1DAY']

    def __init__(self, streamer=None, broker=None, storage=None):      
        """Initializes the Trader. 
        """
        if streamer == None:
            warning("Streamer not specified, using DummyBroker")
            self.streamer = DummyBroker()
        else:
            self.streamer = streamer
  
        if broker == None:
            self.broker = self.streamer
        else:
            self.broker = broker

        # Initialize date 
        self.timestamp_prev = pytz.utc.localize(dt.datetime.utcnow().replace(microsecond=0, second=0))
        self.timestamp = self.timestamp_prev

        self.watch = []             # List of stocks to watch
        self.account = {}           # Local cash of account info 

        self.stock_positions = []   # Local cache of current stock positions
        self.option_positions = []  # Local cache of current options positions
        self.crypto_positions = []  # Local cache of current crypto positions

        self.order_queue = []       # Queue of unfilled orders

        if storage is None:
            self.storage = BaseStorage() # Storage to hold stock/crypto data
        else:
            self.storage = storage

        self.block_lock = threading.Lock() # Lock for streams that recieve data asynchronously

        self.algo = []
        self.is_save = False

    def setup(self, interval, aggregations, sync=True):
        self.sync = sync
        self.interval = interval
        self.aggregations = aggregations

        if not self.streamer.has_interval(interval):
            raise Exception(f"""Interval '{interval}' is not supported by the selected streamer.\n 
                                The streamer only supports {self.streamer.interval_list}""")

        # Ensure that all aggregate intervals are greater than 'interval'
        int_i = self.interval_list.index(interval)
        for agg in aggregations:
            if self.interval_list.index(agg) <= int_i:
                raise Exception(f"""Interval '{interval}' is greater than aggregation interval '{agg}'\n
                                    All intervals in aggregations must be greater than specified interval '{interval}'""")

        # Instantiate the account
        self._setup_account()

        # If sync is on, call the broker to load pending orders and 
        # all positions currently held.
        if sync:
            self._setup_stats()
            for s in self.stock_positions:
                self.watch.append(s['symbol'])
            for s in self.option_positions:
                self.watch.append(s['symbol'])
            for s in self.crypto_positions:
                self.watch.append(s['symbol'])
            for s in self.order_queue:
                self.watch.append(s['symbol'])     

        if len(self.watch) == 0:
            raise Exception(f"No stock or crypto was specified.")

        # Remove duplicates
        self.watch = list(set(self.watch))
        debug(f"Watchlist: {self.watch}")

        self.fetch_interval = self.streamer.fetch_interval
        debug(f"Interval: {interval}\nFetch interval: {self.fetch_interval}")

        if interval != self.fetch_interval:
            self.aggregations.insert(0, interval)
        debug(f"Aggregations: {self.aggregations}")

        if len(self.algo) == 0:
            print(f"No algorithm specified. Using BaseAlgo")
            self.algo = [BaseAlgo()]
        
        # Initialize storage
        for s in self.watch:
            for i in self.aggregations:
                self.storage.store(s, i, self.streamer.fetch_price_history(s, i))

        self.load_watch = True

    def _setup_account(self):
        """Initializes local cache of account info. 
        For testing, it should manually be specified
        """
        ret = self.broker.fetch_account()
        self.account = ret
    
    def _setup_stats(self):
        """Initializes local cache of stocks, options, and crypto positions.
        """
        # Get any pending orders 
        ret = self.broker.fetch_order_queue()
        self.order_queue = ret

        # Can be removed
        # self.storage_setup(self.interval)

        # Get positions
        pos = self.broker.fetch_stock_positions()
        self.stock_positions = pos
        pos = self.broker.fetch_option_positions()
        self.option_positions = pos
        pos = self.broker.fetch_crypto_positions()
        self.crypto_positions = pos

        # Update option stats
        self.broker.update_option_positions(self.option_positions)

    def start(self, interval='5MIN', aggregations=[], sync = True, kill_switch: bool=False): 
        """Entry point to start the system. 
        
        :load_watch: If True, all positions will be loaded from the brokerage account. 
            They will then be added to the watchlist automatically. Set it to False if you
            do not want to track all positions you currently own. 
        :interval: Specifies the interval of running the algo. 
        :aggregations: A list of intervals. The Trader will aggregate data to the intervals specified in this list.
            For example, if this is set to ['5MIN', '30MIN'], and interval is '1MIN', the algorithm will have access to 
            5MIN, 30MIN aggregated candles in addition to 1MIN candles. 
        :kill_switch: If true, kills the infinite loop in streamer.start so we can test this flow.

        TODO: If there is no internet connection, the program will shut down before starting. 
        """
        print(f"Starting Harvest...")

        self.broker.setup(self.watch, interval, self, self.main)
        self.streamer.setup(self.watch, interval, self, self.main)
        self.setup(interval, aggregations, sync)

        for a in self.algo:
            a.setup()
            a.trader = self
            a.watch = self.watch
            a.fetch_interval = self.fetch_interval

        self.blocker = {}
        for w in self.watch:
            self.blocker[w] = False
        self.block_queue = {}
        self.needed = self.watch.copy()

        self.is_save = True
        
        self.loop = asyncio.get_event_loop()

        self.streamer.start(kill_switch)

    async def timeout(self):
        try:
            debug("Begin timer")
            await asyncio.sleep(1)
            debug("Force flush")
            self.main(None, True)
        except asyncio.CancelledError:
            debug("Timeout cancelled")

    async def main(self, df_dict, timestamp, flush: bool=False):
        """ Function called by the broker every minute
        as new stock price data is streamed in. 

        :df_dict: A list of dataframes
        :timestamp: The time when the dataframes were generated, in other words the current time.
            This is needed since the timestamp of data != current time. For example, when the Robinhood API
            is called at midnight, it returns a data with the timestamp of market close time. 
        
            Services like Alpaca Market and Polygon.io offer websocket streaming
        to get real-time stock info. The downside of this is that in turn for
        millesecond latencies, price data do not come in synchronously. 
        Sometimes data may be missing all together. Harvest takes the follwing approach
        to solve this:
        -   Data that just came in will be compared against self.watch to see if 
            any data is missing
        -   If no, data will be passed on
        -   If yes, data will be put in a queue, and main will wait until rest of the data coms in
        -   After a certain timeout period, the main will forward the data 
        """
        debug(f"Received: \n{df_dict}")
        
        self.block_lock.acquire()

        self.timestamp_prev = self.timestamp
        self.timestamp = timestamp

        # If flush=True, forcefully push all data in block_queue onto main_helper
        if flush:
            # For missing data, repeat the existing one
            for n in self.needed:
                self.block_queue[n] = self.storage.load(n, self.base_interval).iloc[[-1]]
            self.needed = self.watch.copy()
            for k, v in self.blocker.items():
                self.blocker[k] = False
            self.main_helper(self.block_queue)
            self.block_queue = {}
            self.block_lock.release()
            return

        # If this is a first df to arrive for a given timestamp, 
        # start the timeout counter
        if all(not v for v in self.blocker.values()):
            self.task = self.loop.create_task(self.timeout())

        symbols = [k for k, v in df_dict.items()]
        debug(f"Got data for: {symbols}")
        self.needed = list(set(self.needed) - set(symbols))
        debug(f"Still need data for: {self.needed}")
 
        if not bool(self.block_queue):
            self.block_queue = df_dict 
        else:
            self.block_queue.update(df_dict)
        for t in symbols:    
            self.blocker[t] = True
        
        # If all data has been received, pass on the data
        if len(self.needed) == 0:
            debug("All data received")
            debug(self.block_queue)
            self.task.cancel()
            self.needed = self.watch.copy()
            for k, v in self.blocker.items():
                self.blocker[k] = False
            self.main_helper(self.block_queue)
            self.block_queue = {}
            self.block_lock.release()
            return 
        
        self.block_lock.release()

    def main_helper(self, df_dict):

        new_day = self.timestamp.date() > self.timestamp_prev.date()
        # Can be removed
        # self.storage_update(df_dict)
        
        # Periodically refresh access tokens
        if new_day or (self.timestamp.hour == 3 and self.timestamp.minute == 0):
            self.streamer.refresh_cred()
        
        # Save the data locally
        for s in self.watch:
            self.storage.store(s, self.fetch_interval, df_dict[s])
        
        # Aggregate the data to other intervals
        for s in self.watch:
            for i in self.aggregations:
                self.storage.aggregate(s, self.fetch_interval, i)

        # If an order was processed, fetch the latest position info.
        # Otherwise, calculate current positions locally
        update = self._update_order_queue()
        self._update_stats(df_dict, new=update, option_update=True)
        
        if not self.is_freq(self.timestamp):
            return

        meta = {
            'new_day': new_day
        }

        for a in self.algo:
            a.main(meta)
        self.broker.exit()
        self.streamer.exit()

    def is_freq(self, time):
        """Helper function to determine if algorithm should be invoked for the
        current timestamp. For example, if interval is 30MIN,
        algorithm should be called when minutes are 0 and 30.
        """
        
        if self.fetch_interval == self.interval:
            return True 

        if self.interval == '1MIN':
            return True 
        
        minutes = time.minute
        hours = time.hour
        if self.interval == '1HR':
            if minutes == 0:
                return True 
            else:
                return False
        
        if self.interval == '1DAY':
            #TODO use market close time 
            if minutes == 0 and hours == 16:
                return True 
            else:
                return False

        val = int(re.sub("[^0-9]", "", self.interval))
        if minutes % val == 0:
            return True 
        else: 
            return False

    def _update_order_queue(self):
        """Check to see if outstanding orders have been accpted or rejected
        and update the order queue accordingly.
        """
        debug(f"Updating order queue: {self.order_queue}")
        for i, order in enumerate(self.order_queue):
            if 'type' not in order:
                raise Exception(f"key error in {order}\nof {self.order_queue}")
            if order['type'] == 'STOCK':
                stat = self.broker.fetch_stock_order_status(order["id"])
            elif order['type'] == 'OPTION':
                stat = self.broker.fetch_option_order_status(order["id"])
            elif order['type'] == 'CRYPTO':
                stat = self.broker.fetch_crypto_order_status(order["id"])
            debug(f"Updating status of order {order['id']}")
            self.order_queue[i] = stat

        debug(f"Updated order queue: {self.order_queue}")
        new_order = []
        order_filled = False
        for order in self.order_queue:
            if order['status'] == 'filled':
                order_filled = True  
            else:
                new_order.append(order)
        self.order_queue = new_order

        # if an order was processed, update the positions and account info
        return order_filled
           
    def _update_stats(self, df_dict, new=False, option_update=False):
        """Update local cache of stocks, options, and crypto positions
        """
        # Update entries in local cache
        # API should also be called if load_watch is false, as there is a high chance 
        # that data in local cache are not representative of the entire portfolio,
        # meaning total equity cannot be calculated locally
        if new or not self.load_watch:
            pos = self.broker.fetch_stock_positions()
            self.stock_positions = [p for p in pos if p['symbol'] in self.watch]
            pos = self.broker.fetch_option_positions()
            self.option_positions = [p for p in pos if p['symbol'] in self.watch]
            pos = self.broker.fetch_crypto_positions()
            self.crypto_positions = [p for p in pos if p['symbol'] in self.watch]
            ret = self.broker.fetch_account()
            self.account = ret

        if option_update:
            self.broker.update_option_positions(self.option_positions)
        
        debug(f"Stock positions: {self.stock_positions}")
        debug(f"Option positions: {self.option_positions}")
        debug(f"Crypto positions: {self.crypto_positions}")

        if new or not self.load_watch:
            return 
        else:
            net_value = 0
            for p in self.stock_positions + self.crypto_positions:
                key = p['symbol']
                price = df_dict[key][key]['close'][0]
                p['current_price'] = price 
                value = price * p['quantity']
                p['market_value'] = value
                net_value = net_value + value
            
            equity = net_value + self.account['cash']
            self.account['equity'] = equity

    def fetch_chain_info(self, *args, **kwargs):
        return self.streamer.fetch_chain_info(*args, **kwargs)
    
    def fetch_chain_data(self, *args, **kwargs):
        return self.streamer.fetch_chain_data(*args, **kwargs)
    
    def fetch_option_market_data(self, *args, **kwargs):
        return self.streamer.fetch_option_market_data(*args, **kwargs)

    def buy(self, symbol: str, quantity: int, in_force: str, extended: bool):
        ret = self.broker.buy(symbol, quantity, in_force, extended)
        if ret == None:
            raise Exception("BUY failed")
        self.order_queue.append(ret)
        debug(f"BUY order queue: {self.order_queue}")
        return ret
    
    def await_buy(self, symbol: str, quantity: int, in_force: str, extended: bool):
        ret = self.broker.await_buy(symbol, quantity, in_force, extended)
        return ret

    def sell(self, symbol: str, quantity: int, in_force: str, extended: bool):
        ret = self.broker.sell(symbol, quantity, in_force, extended)
        if ret == None:
            raise Exception("SELL failed")
        self.order_queue.append(ret)
        debug(f"SELL order queue: {self.order_queue}")
        return ret
    
    def await_sell(self, symbol: str, quantity: int, in_force: str, extended: bool):
        ret = self.broker.await_sell(symbol, quantity, in_force, extended)
        return ret

    def buy_option(self, symbol: str, quantity: int, in_force: str):
        ret = self.broker.buy_option(symbol, quantity, in_force)
        if ret == None:
            raise Exception("BUY failed")
        self.order_queue.append(ret)
        debug(f"BUY order queue: {self.order_queue}")
        return ret

    def sell_option(self, symbol: str, quantity: int, in_force: str):
        ret = self.broker.sell_option(symbol, quantity, in_force)
        if ret == None:
            raise Exception("SELL failed")
        self.order_queue.append(ret)
        debug(f"SELL order queue: {self.order_queue}")
        return ret
    
    def set_algo(self, algo):
        if isinstance(algo, list):
            self.algo = algo
        else:
            self.algo = [algo]
    
    def set_symbol(self, symbol):
        if isinstance(symbol, list):
            self.watch = symbol
        else:
            self.watch = [symbol]

    def add_symbol(self, symbol):
        self.watch.append(symbol)
    
    def remove_symbol(self, symbol):
        self.watch.remove(symbol)
    
    def exit(self, signum, frame):
        # TODO: Gracefully exit
        print("\nStopping Harvest...")
        exit(0)