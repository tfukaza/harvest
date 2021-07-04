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
import harvest.queue as queue
from harvest.broker.dummy import DummyBroker

class Trader:
    """

    Parameters:
    :watch: Watchlist containing all stock and cryptos to monitor.
        The user may or may not own them. Note it does NOT contain options. 
    :broker: Both the broker and streamer store a Broker object.
        Broker places orders and retrieves latest account info like equity.
    :streamer: Streamer retrieves the latest stock price and calls handler().
    """

    interval_list = ['1MIN', '5MIN', '15MIN', '30MIN', '1HR', '1DAY']

    def __init__(self, streamer=None, broker=None):      
        """Initializes the Trader. 
        :streamer:
        :broker:
        """
        if streamer == None:
            warning("Streamer not specified, using DummyBroker")
            self.streamer = DummyBroker()
        else:
            self.streamer = streamer
        self.streamer.setup(self.handler, self)
            
        if broker == None:
            self.broker = self.streamer
        else:
            self.broker = broker
            self.broker.setup(self.handler, self)

        # Initialize date 
        now = time.mktime(time.gmtime())
        now = dt.datetime.fromtimestamp(now)
        now = now.replace(second=0, microsecond=0)
        now = pytz.utc.localize(now)
        self.timestamp_prev = now
        self.timestamp = self.timestamp_prev

        self.watch = []             # List of stocks to watch
        self.queue = queue.Queue()  # local cache of historic price
        self.account = {}           # Local cash of account info 

        self.stock_positions = []   # Local cache of current stock positions
        self.option_positions = []  # Local cache of current options positions
        self.crypto_positions = []  # Local cache of current crypto positions

        self.order_queue = []       # Queue of unfilled orders 

        self.block_lock = threading.Lock() # Lock for streams that recieve data asynchronously

        self.algo = None

        signal(SIGINT, self.exit)

    def run( self, load_watch=True, interval='5MIN',aggregations=[]): 
        """Entry point to start the system. 
        
        :load_watch: If True, all positions will be loaded from the brokerage account. 
            They will then be added to the watchlist automatically. Set it to False if you
            do not want to track all positions you currently own. 
        :interval: Specifies the interval of running the algo. 
        :aggregations: A list of intervals. The Trader will aggregate data to the intervals specified in this list.
            For example, if this is set to ['5MIN', '30MIN'], and interval is '1MIN', the algorithm will have access to 
            5MIN, 30MIN aggregated candles in addition to 1MIN candles. 

        TODO: If there is no internet connection, the program will shut down before starting. 
        """
        print(f"Starting Harvest...")

        self.load_watch = load_watch
        self.interval = interval
        self.aggregations = aggregations

        if not interval in self.streamer.interval_list:
            raise Exception(f"""Interval '{interval}' is not supported by the selected streamer.\n 
                                The streamer only supports {self.streamer.interval_list}""")

        # Ensure that all aggregate intervals are greater than 'interval'
        int_i = self.interval_list.index(interval)
        for agg in aggregations:
            if self.interval_list.index(agg) <= int_i:
                raise Exception(f"""Interval '{interval}' is less than aggregation interval '{agg}'\n
                                    All intervals in aggregations must be greater than specified interval '{interval}'""")

        self._setup_account()
        self._setup_stats()

        if load_watch:
            for s in self.stock_positions:
                self.watch.append(s['symbol'])
            for s in self.option_positions:
                self.watch.append(s['symbol'])
            for s in self.crypto_positions:
                self.watch.append(s['symbol'])
            for s in self.order_queue:
                self.watch.append(s['symbol'])     

        if len(self.watch) == 0:
            raise Exception(f"No stock or crypto was specified. Use add_symbol() to specify an asset to watch.")

        # Remove duplicates
        self.watch = list(set(self.watch))
        debug(f"Watchlist: {self.watch}")
    
        self.broker.setup_run(self.watch, interval)
        self.streamer.setup_run(self.watch, interval)

        # Fetch interval is the interval in which the streamer
        # gets asset data. For example, Robinhood does not provide 10MIN interval data,
        # so Trader must runs at 5MIN and aggregate it to 10MIN.
        # This also means fetch_interval is always a shorter interval than 'interval'
        self.fetch_interval = self.streamer.fetch_interval
        debug(f"Interval: {interval}\nFetch interval: {self.fetch_interval}")

        if interval != self.fetch_interval:
            self.aggregations.append(interval)
        debug(f"Aggregations: {self.aggregations}")

        if self.algo == None:
            raise Exception("Algorithm was not specified. Use set_algo to specify an algorithm.")

        self.algo.setup(self)
        self.algo.watch = self.watch
        self.algo.fetch_interval = self.fetch_interval
        
        self._queue_init(self.fetch_interval) 
        self.algo.algo_init()

        self.blocker = {}
        for w in self.watch:
            self.blocker[w] = False
        self.block_queue = {}
        self.needed = self.watch.copy()
        
        self.loop = asyncio.get_event_loop()

        self.streamer.run()

    async def timeout(self):
        try:
            debug("Begin timer")
            await asyncio.sleep(1)
            debug("Force flush")
            self.handler(None, True)
        except asyncio.CancelledError:
            debug("Timeout cancelled")

    async def handler(self, df_dict, timestamp, flush=False):
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
        -   If yes, data will be put in a queue, and handler will wait until rest of the data coms in
        -   After a certain timeout period, the handler will forward the data 
        """
        debug(f"Handler received: \n{df_dict}")
        
        self.block_lock.acquire()

        self.timestamp_prev = self.timestamp
        self.timestamp = timestamp

        # If flush=True, forcefully push all data in block_queue onto handler_main
        if flush:
            # For missing data, repeat the existing one
            for n in self.needed:
                self.block_queue[n] = self.queue.get_last_symbol_interval(n, self.base_inverval)
            self.needed = self.watch.copy()
            for k, v in self.blocker.items():
                self.blocker[k] = False
            self.handler_main(self.block_queue)
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
        
        # if all data has been received, send off the data
        if len(self.needed) == 0:
            debug("All data received")
            debug(self.block_queue)
            self.task.cancel()
            self.needed = self.watch.copy()
            for k, v in self.blocker.items():
                self.blocker[k] = False
            self.handler_main(self.block_queue)
            self.block_queue = {}
            self.block_lock.release()
            return 
        
        self.block_lock.release()

    def handler_main(self, df_dict):

        new_day = False
        # Init queue on a new day 
        if self.timestamp.date() > self.timestamp_prev.date():
            debug("Initializing queue...")
            self._queue_init(self.fetch_interval) 
            new_day = True
        
        # Periodically refresh access tokens
        if new_day or (self.timestamp.hour == 3 and self.timestamp.minute == 0):
            self.streamer.refresh_cred()
        
        # Update the queue. If not new data is received, skip.
        is_new = self._queue_update(df_dict, self.timestamp)
        if not is_new:
            debug("No new data")
            return 

        # If an order was processed, fetch the latest position info
        # otherwise, calculate current positions locally
        update = self._update_order_queue()
        self._update_stats(df_dict, new=update, option_update=True)
        
        if not self.is_freq(self.timestamp):
            return

        meta={
            'new_day':new_day
        }

        self.algo.handler(meta)
        self.broker.exit()
        self.streamer.exit()

    def is_freq(self, time):
        """Helper function to determine if algorithm should be invoked for the
        current timestamp. For example, if interval is 30MIN and fetch_interval is 5MIN,
        algorithm should be called when minutes are 25 and 55.
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
        val_fetch = int(re.sub("[^0-9]", "", self.fetch_interval))
        if minutes % val == 0:
            return True 
        else: 
            return False

    def _queue_init(self, interval):
        """Loads historical price data to ensure price queues are up-to-date upon program startup.
        This should also be called at the start of each trading day 
        so database is updated and cache is refreshed.
        """

        today = pytz.utc.localize(dt.datetime.utcnow().replace(microsecond=0, second=0))  # Current timestamp in UTC
        for sym in self.watch:
            self.queue.init_symbol(sym, interval)
            last = pytz.utc.localize(dt.datetime(1970, 1, 1))
            df = self.streamer.fetch_price_history(last, today, interval, sym)
            self.queue.set_symbol_interval(sym, interval, df)
            self.queue.set_symbol_interval_update(sym, interval, df.index[-1])
           
            # Many brokers have seperate API for intraday data, so make an API call
            # instead of aggregating interday data
            if '1DAY' in self.aggregations:
                df = self.streamer.fetch_price_history(last, today, '1DAY', sym)
                self.queue.set_symbol_interval(sym, '1DAY', df)
                self.queue.set_symbol_interval_update(sym, '1DAY', df.index[-1])

            df = self.queue.get_symbol_interval(sym, interval)
            for i in self.aggregations:
                if i == '1DAY':
                    continue
                df_tmp = self.aggregate_df(df, i)
                self.queue.set_symbol_interval(sym, i, df_tmp)
                self.queue.set_symbol_interval_update(sym, i, df_tmp.index[-1])

    def aggregate_df(self, df, inter):
        sym = list(df.columns.levels[0])[0]
        df = df[sym]
        op_dict = {
            'open': 'first',
            'high':'max',
            'low':'min',
            'close':'last',
            'volume':'sum'
        }
        val = re.sub("[^0-9]", "", inter)
        if inter[-1] == 'N':
            val = val+'T'
        elif inter[-1] == 'R':
            val = 'H'
        else:
            val = 'D'
        df = df.resample(val).agg(op_dict)
        df.columns = pd.MultiIndex.from_product([[sym], df.columns])
        return df

    def _queue_update(self, df_dict, time):
        """Takes a df of the latest stock price info, and updates the price queue 
        accordingly. Should be called every time handler() is invoked. 
        """
        debug("Queue update")
        interval = self.fetch_interval
        is_new = False

        for sym in self.watch:
            old_timestamp = self.queue.get_symbol_interval_update(sym, interval)
            new_timestamp = df_dict[sym].index[-1]
            if new_timestamp <= old_timestamp:
                continue
            else:
                is_new = True
            self.queue.append_symbol_interval(sym, interval, df_dict[sym], True)
            self.queue.set_symbol_interval_update(sym, interval, new_timestamp) 

            df_base = self.queue.get_symbol_interval(sym, interval) 
            
            for inter in self.aggregations:
                # Locally aggregate data to reduce network latency
                old_agg = self.queue.get_symbol_interval(sym, inter).index[-1]

                df_tmp = df_base.loc[old_agg:]
                df_tmp = self.aggregate_df(df_tmp, inter)
                df_tmp = df_tmp[df_tmp[sym]['open'].notna()]
              
                self.queue.append_symbol_interval(sym, inter, df_tmp, True)
                self.queue.set_symbol_interval_update(sym, interval, df_tmp.index[-1]) 
        
        return is_new

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
        
    def _setup_stats(self):
        """Initializes local cache of stocks, options, and crypto positions.
        """
        # Get any pending orders 
        ret = self.broker.fetch_order_queue()
        self.order_queue = ret

        # Get positions
        pos = self.broker.fetch_stock_positions()
        self.stock_positions = pos
        pos = self.broker.fetch_option_positions()
        self.option_positions = pos
        pos = self.broker.fetch_crypto_positions()
        self.crypto_positions = pos

        # Get account stats
        ret = self.broker.fetch_account()
        self.account = ret
        # Update option stats
        self.broker.update_option_positions(self.option_positions)

    def fetch_chain_info(self, *args, **kwargs):
        return self.streamer.fetch_chain_info(*args, **kwargs)
    
    def fetch_chain_data(self, *args, **kwargs):
        return self.streamer.fetch_chain_data(*args, **kwargs)
    
    def fetch_option_market_data(self, *args, **kwargs):
        return self.streamer.fetch_option_market_data(*args, **kwargs)

    def _setup_account(self):
        """Initializes local cache of account info. 
        For testing, it should manually be specified
        """
        self.account = {
            "equity": 0.0,
            "cash": 0.0,
            "buying_power": 0.0,
            "multiplier": 1
        }

    def buy(self, symbol: str=None, quantity: int=0, in_force: str='gtc', extended: bool=False):
        ret = self.broker.buy(symbol, quantity, in_force, extended)
        if ret == None:
            raise Exception("BUY failed")
        self.order_queue.append(ret)
        debug(f"BUY order queue: {self.order_queue}")
        return ret
    
    def await_buy(self, symbol: str=None, quantity: int=0, in_force: str='gtc', extended: bool=False):
        ret = self.broker.await_buy(symbol, quantity, in_force, extended)
        return ret

    def sell(self, symbol: str=None, quantity: int=0, in_force: str='gtc', extended: bool=False):
        ret = self.broker.sell(symbol, quantity, in_force, extended)
        if ret == None:
            raise Exception("SELL failed")
        self.order_queue.append(ret)
        debug(f"SELL order queue: {self.order_queue}")
        return ret
    
    def await_sell(self, symbol: str=None, quantity: int=0, in_force: str='gtc', extended: bool=False):
        ret = self.broker.await_sell(symbol, quantity, in_force, extended)
        return ret

    def buy_option(self, symbol: str=None, quantity: int=0, in_force: str='gtc'):
        ret = self.broker.buy_option(symbol, quantity, in_force)
        if ret == None:
            raise Exception("BUY failed")
        self.order_queue.append(ret)
        debug(f"BUY order queue: {self.order_queue}")
        return ret

    def sell_option(self, symbol: str=None, quantity: int=0, in_force: str='gtc'):
        ret = self.broker.sell_option(symbol, quantity, in_force)
        if ret == None:
            raise Exception("SELL failed")
        self.order_queue.append(ret)
        debug(f"SELL order queue: {self.order_queue}")
        return ret
    
    def set_algo(self, algo):
        self.algo = algo
    
    def add_symbol(self, symbol):
        self.watch.append(symbol)
    
    def remove_symbol(self, symbol):
        self.watch.remove(symbol)
    
    def exit(self, signum, frame):
        # TODO: Gracefully exit
        print("\nStopping Harvest...")
        exit(0)