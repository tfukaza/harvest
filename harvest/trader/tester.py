# Builtins
import datetime as dt
from logging import critical, error, info, warning, debug
from typing import Any, Dict, List, Tuple
import os.path

# External libraries
import pandas as pd
import numpy as np
from tqdm import tqdm
import pytz

# Submodule imports
import harvest.load as load
from harvest.storage import BaseStorage
import harvest.trader.trader as trader
from harvest.broker.dummy import DummyBroker

class BackTester(trader.Trader):
    """
    This class replaces several key functions to allow backtesting
    on historical data. 
    """

    def __init__(self, streamer=None, config={}):      
        """Initializes the TestTrader. 
        """
        if streamer == None:
            self.streamer = DummyBroker()
        else:
            self.streamer = streamer
        self.broker = DummyBroker()

        self.watch = []             # List of stocks to watch
        self.store = BaseStorage()  # local cache of historic price
        self.account = {}           # Local cash of account info 

        self.stock_positions = []   # Local cache of current stock positions
        self.option_positions = []  # Local cache of current options positions
        self.crypto_positions = []  # Local cache of current crypto positions

        self.order_queue = []       # Queue of unfilled orders 

        self.load = load.Load()
    
    def read_csv(self, path:str) -> pd.DataFrame:
        """Reads a CSV file and returns a Pandas DataFrame. 

        :path: Path to the CSV file. 
        """
        df = pd.read_csv(path)
        df = df.set_index(['timestamp'])
        if isinstance(df.index[0], str):
            df.index = pd.to_datetime(df.index)
        else:
            df.index = pd.to_datetime(df.index, unit='s')
        df = df[["open", "high", "low", "close", "volume"]].astype(float)
        df = df.sort_index()
        return df

    def read_price_history(self, path: str, date_format: str='%Y-%m-%d %H:%M:%S'):
        """Function to read backtesting data from a local CSV file. 

        :interval: The interval of the data
        :path: Path to the local data file
        :date_format: The format of the data's timestamps
        TODO: Possibly allow interday data to be specified. 
        """
        for sym in self.watch: 
            df = self.read_csv(f"{path}/{sym}-{self.interval}.csv")
            self.store.store(sym, self.interval, df)
            
            prev_i = self.interval
            for i in self.aggregations:
                # If the user supplied data for aggregate intervals, read it. 
                # Otherwise, aggregate the original data. 
                name = f"{path}/{sym}-{i}.csv"
                if os.path.isfile(name):
                    df = self.read_csv(name)
                    self.store.store(sym, i, df)
                else:
                    self.store.aggregate(sym, prev_i, i)
                prev_i = i

    def load_price_history(self):
        """Function to read backtesting data from a local file. 

        :interval: The interval of the data
        :path: Path to the local data file
        :date_format: The format of the data's timestamps
        TODO: Possibly allow interday data to be specified. 
        """
        last = pytz.utc.localize(dt.datetime(1970, 1, 1))
        today = pytz.utc.localize(dt.datetime.utcnow().replace(microsecond=0, second=0))  
        for sym in self.watch:
            for i in [self.interval] + self.aggregations:
                df = self.load.get_entry(sym, i)
                df = df.dropna()
                debug(f"got {df} for {sym}, {i}")
                if df.empty:
                    warning(f"Local data for {sym}, {i} not found. Running FETCH")
                    df = self.streamer.fetch_price_history(last, today, i, sym).dropna()
                self.store.store(sym, i, df)
            
    def setup(self, source, interval, aggregations=None, path=None):
        self.interval = interval
        self.aggregations = aggregations if not aggregations == None else []

        self.broker.setup(self.watch, interval, self, self.main)
        self.streamer.setup(self.watch, interval, self, self.main)

        self.fetch_interval = interval
        self._setup_account()
        self.df = {}

        # Load data into queue
        if source == "FETCH":
            self._queue_init(interval)
        elif source == "CSV":
            self.read_price_history(path)
        elif source == "LOCAL":
            self.load_price_history()
        
        conv = {
            "1MIN": 1,
            "5MIN": 5,
            "15MIN": 15,
            "30MIN": 30,
            "1HR": 60,
            "1DAY": 1440
        }

        # Generate the "simulated aggregation" data
        for sym in self.watch:
            df = self.store.load(sym, self.interval)
            rows = len(df.index)
            print(f"Formatting {sym} data...")
            for agg in self.aggregations:
                print(f"Formatting {agg} ...")
                points = int(conv[agg]/conv[interval])
                for i in tqdm(range(rows)):
                    df_tmp = df.iloc[0:i+1]                    
                    df_tmp = df_tmp.iloc[-points:] 
                    agg_df = self.store._aggregate(df_tmp, agg)
                    # Save the data into a new queue
                    self.store.store(sym, '-'+agg, agg_df.iloc[[-1]], remove_duplicate=False)
        print("Formatting complete")

        # Save the current state of the queue
        for s in self.watch:
            self.load.append_entry(s, self.interval, self.store.load(s, self.interval))
            for i in self.aggregations:
                self.load.append_entry(s, '-'+i, self.store.load(s, '-'+i), False, True)
                self.load.append_entry(s, i, self.store.load(s, i))

        # Move all data to a cached dataframe
        for i in [self.interval] + self.aggregations:
            i = i if i == self.interval else '-'+i
            self.df[i] = {}
            for s in self.watch:
                df = self.store.load(s, i)
                self.df[i][s] = df.copy() 
        
        # Trim data so start and end dates match between assets and intervals
        # data_start = pytz.utc.localize(dt.datetime(1970, 1, 1))
        # data_end = pytz.utc.localize(dt.datetime.utcnow().replace(microsecond=0, second=0))
        # for i in [self.interval] + self.aggregations:
        #     for s in self.watch:
        #         start = self.df[i][s].index[0]
        #         end = self.df[i][s].index[-1]
        #         if start > data_start:
        #             data_start = start
        #         if end < data_end:
        #             data_end = end

        # for i in [self.interval] + self.aggregations:
        #     for s in self.watch:
        #         self.df[i][s] = self.df[i][s].loc[data_start:data_end]

        # Reset them 
        for i in [self.interval] + self.aggregations:
            for s in self.watch:
                self.store.reset(s, i)
            
        self.load_watch = True

    def start(self, interval: str='5MIN', aggregations: List[Any]=[], source: str='LOCAL', path: str="./data"):
        """Runs backtesting. 

        :source: 'LOCAL' if backtesting data is in a local file, 'FETCH' if the streamer should 
            be used to download latest data. 
        """

        self.setup(source, interval, aggregations, path)

        self.algo.setup()
        self.algo.trader = self
        self.algo.watch = self.watch
        self.algo.fetch_interval = self.fetch_interval

        self.main(interval)

    def main(self, interval):
        info("Running test...")

        # import cProfile
        # pr = cProfile.Profile()
        # pr.enable()
        
        rows = len(self.df[interval][self.watch[0]].index)
        for i in range(rows):
            df_dict = {}
            for s in self.watch:
                df_dict[s] = self.df[interval][s].iloc[[i]]
            # Add data to queue
            self.timestamp = self.df[interval][self.watch[0]].index[i]
            update = self._update_order_queue()
            self._update_stats(df_dict, new=update, option_update=True)
            for s in self.watch:
                df = self.df[interval][s].iloc[[i]]
                self.store.store(s, interval, df)
                # Add data to aggregation queue
                for agg in self.aggregations:
                    # Update the last datapoint
                    df = self.df['-'+agg][s].iloc[[i]]
                    self.store.store(s, agg, df)
        
            self.algo.main({})
 
        # pr.disable()
        # import pstats 
        # st = pstats.Stats(pr)
        # st.sort_stats('cumtime')
        # st.print_stats(0.1)
        # st.dump_stats("stat.txt")

        print(self.account)

 
    def _queue_update(self, new_df: pd.DataFrame, time):
        pass

    def _setup_account(self):
        self.account = {
            "equity": 1000000.0,
            "cash": 1000000.0,
            "buying_power": 1000000.0,
            "multiplier": 1
        }
    
    def fetch_position(self, key):
        pass

    def fetch_account(self):
        pass

  
  
