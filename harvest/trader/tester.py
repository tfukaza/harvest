# Builtins
import datetime as dt
from typing import Any, Dict, List, Tuple
import os.path
from pathlib import Path

# External libraries
import pandas as pd
import numpy as np
from tqdm import tqdm
import pytz

# Submodule imports
from harvest.storage import PickleStorage
import harvest.trader.trader as trader
from harvest.api.yahoo import YahooStreamer
from harvest.api.paper import PaperBroker
from harvest.utils import *


class BackTester(trader.PaperTrader):
    """
    This class replaces several key functions to allow backtesting
    on historical data.
    """

    def __init__(self, streamer=None, debug=False, config={}):
        """Initializes the TestTrader."""

        self.streamer = YahooStreamer() if streamer is None else streamer
        self.broker = PaperBroker()

        self.storage = PickleStorage(limit_size=False)  # local cache of historic price
        self._init_attributes()

        self._setup_debugger(debug)

    def start(
        self,
        interval: str = "5MIN",
        aggregations: List[Any] = [],
        source: str = "PICKLE",
        path: str = "./data",
        start=None,
        end=None,
        period=None,
    ):
        """Runs backtesting.

        The interface is very similar to the Trader class, with some additional parameters for specifying
        backtesting configurations.

        :param str? interval: The interval to run the algorithm on. defaults to '5MIN'.
        :param List[str]? aggregations: The aggregations to run. defaults to [].
        :param str? source: The source of backtesting data.
            'FETCH' will pull the latest data using the broker (if specified).
            'CSV' will read data from a locally saved CSV file.
            'PICKLE' will read data from a locally saved pickle file, generated using the Trader class.
            defaults to 'PICKLE'.
        :param str? path: The path to the directory which backtesting data is stored.
            This parameter must be set accordingly if 'source' is set to 'CSV' or 'PICKLE'. defaults to './data'.
        """

        debugger.debug(f"Storing asset data in {path}")
        for a in self.algo:
            a.config()

        self._setup(source, interval, aggregations, path, start, end, period)
        self.broker.setup(self.stats, self.main)
        self.streamer.setup(self.stats, self.main)

        for a in self.algo:
            a.init(self.stats)
            a.setup()
            a.trader = self

        self.run_backtest()

    def _setup(
        self,
        source: str,
        interval: str,
        aggregations: List,
        path: str,
        start,
        end,
        period,
    ):
        self._setup_params(interval, aggregations)
        self._setup_account()

        self.df = {}

        self.storage.limit_size = False

        start = convert_input_to_datetime(start, self.stats.timezone)
        end = convert_input_to_datetime(end, self.stats.timezone)
        period = convert_input_to_timedelta(period)

        if start is None:
            if end is None:
                start = "MAX" if period is None else "PERIOD"
            else:
                start = end - period
        if end is None:
            if start == "MAX" or start == "PERIOD" or period is None:
                end = "MAX"
            else:
                end = start + period

        if source == "PICKLE":
            self.read_pickle_data()
        elif source == "CSV":
            self.read_csv_data(path)
        else:
            raise Exception(f"Invalid source {source}. Must be 'PICKLE' or 'CSV'")

        common_start = None
        common_end = None
        for s in self.stats.interval:
            for i in [self.stats.interval[s]["interval"]] + self.stats.interval[s][
                "aggregations"
            ]:
                df = self.storage.load(s, i)
                df = pandas_datetime_to_utc(df, self.stats.timezone)
                if common_start is None or df.index[0] > common_start:
                    common_start = df.index[0]
                if common_end is None or df.index[-1] < common_end:
                    common_end = df.index[-1]

        if start != "MAX" and start != "PERIOD" and start < common_start:
            raise Exception(f"Not enough data is available for a start time of {start}")
        if end != "MAX" and end > common_end:
            raise Exception(
                f"Not enough data is available for an end time of {end}: \nLast datapoint is {common_end}"
            )

        if start == "MAX":
            start = common_start
        elif start == "PERIOD":
            start = common_end - period
        if end == "MAX":
            end = common_end

        self.common_start = start
        self.common_end = end

        print(f"Common start: {start}, common end: {end}")

        for s in self.stats.interval:
            for i in [self.stats.interval[s]["interval"]] + self.stats.interval[s][
                "aggregations"
            ]:
                df = self.storage.load(s, i).copy()
                df = df.loc[start:end]
                self.storage.reset(s, i)
                self.storage.store(s, i, df)

        conv = {
            Interval.MIN_1: 1,
            Interval.MIN_5: 5,
            Interval.MIN_15: 15,
            Interval.MIN_30: 30,
            Interval.HR_1: 60,
            Interval.DAY_1: 1440,
        }

        # Generate the "simulated aggregation" data
        for sym in self.stats.interval:
            interval = self.stats.interval[sym]["interval"]
            interval_txt = interval_enum_to_string(interval)
            df = self.storage.load(sym, interval)
            df_len = len(df.index)

            debugger.debug(f"Formatting {sym} data...")
            for agg in self.stats.interval[sym]["aggregations"]:
                agg_txt = interval_enum_to_string(agg)
                # tmp_path = f"{path}/{sym}-{interval_txt}+{agg_txt}.pickle"
                tmp_path = f"{path}/{sym}@{int(agg)-16}.pickle"
                file = Path(tmp_path)
                if file.is_file():
                    data = self.storage.open(sym, int(agg) - 16)
                    self.storage.store(sym, int(agg) - 16, data, save_pickle=False)
                    continue
                    # TODO: check if file is updated with latest data
                debugger.debug(
                    f"Formatting aggregation from {interval_txt} to {agg_txt}..."
                )
                points = int(conv[agg] / conv[interval])
                for i in tqdm(range(df_len)):
                    df_tmp = df.iloc[0 : i + 1]
                    df_tmp = df_tmp.iloc[
                        -points:
                    ]  # Only get recent data, since aggregating the entire df will take too long
                    agg_df = aggregate_df(df_tmp, agg)
                    self.storage.store(
                        sym,
                        int(agg) - 16,
                        agg_df.iloc[[-1]],
                        remove_duplicate=False,
                        save_pickle=False,
                    )
        debugger.debug("Formatting complete")
        for sym in self.stats.interval:
            for agg in self.stats.interval[sym]["aggregations"]:
                data = self.storage.load(sym, int(agg) - 16)
                data = pandas_datetime_to_utc(data, self.stats.timezone)
                self.storage.store(
                    sym,
                    int(agg) - 16,
                    data,
                    remove_duplicate=False,
                )

        # # Save the current state of the queue
        # for s in self.watch:
        #     self.load.append_entry(s, self.stats.interval, self.storage.load(s, self.stats.interval))
        #     for i in self.aggregations:
        #         self.load.append_entry(s, '-'+i, self.storage.load(s, '-'+i), False, True)
        #         self.load.append_entry(s, i, self.storage.load(s, i))

        # Move all data to a cached dataframe
        for sym in self.stats.interval:
            self.df[sym] = {}
            inter = self.stats.interval[sym]["interval"]
            interval_txt = interval_enum_to_string(inter)
            df = self.storage.load(sym, inter)
            self.df[sym][inter] = df.copy()

            for agg in self.stats.interval[sym]["aggregations"]:
                # agg_txt = interval_enum_to_string(agg)
                # agg_txt = f"{interval_txt}+{agg_txt}"
                df = self.storage.load(sym, int(agg) - 16)
                self.df[sym][int(agg) - 16] = df.copy()

        # Trim data so start and end dates match between assets and intervals
        # data_start = pytz.utc.localize(dt.datetime(1970, 1, 1))
        # data_end = pytz.utc.localize(dt.datetime.utcnow().replace(microsecond=0, second=0))
        # for i in [self.stats.interval] + self.aggregations:
        #     for s in self.watch:
        #         start = self.df[i][s].index[0]
        #         end = self.df[i][s].index[-1]
        #         if start > data_start:
        #             data_start = start
        #         if end < data_end:
        #             data_end = end

        # for i in [self.stats.interval] + self.aggregations:
        #     for s in self.watch:
        #         self.df[i][s] = self.df[i][s].loc[data_start:data_end]

        self.load_watch = True

    def read_pickle_data(self):
        """Function to read backtesting data from a local file.

        :interval: The interval of the data
        :path: Path to the local data file
        :date_format: The format of the data's timestamps
        """
        for s in self.stats.interval:
            for i in [self.stats.interval[s]["interval"]] + self.stats.interval[s][
                "aggregations"
            ]:
                df = self.storage.open(s, i).dropna()
                if df.empty or now() - df.index[-1] > dt.timedelta(days=1):
                    df = self.streamer.fetch_price_history(s, i).dropna()
                self.storage.store(s, i, df)

    def read_csv_data(self, path: str, date_format: str = "%Y-%m-%d %H:%M:%S"):
        """Function to read backtesting data from a local CSV file.

        :interval: The interval of the data
        :path: Path to the local data file
        :date_format: The format of the data's timestamps
        """
        for s in self.stats.interval:
            for i in [self.stats.interval[s]["interval"]] + self.stats.interval[s][
                "aggregations"
            ]:
                i_txt = interval_enum_to_string(i)
                df = self.read_csv(f"{path}/{s}-{i_txt}.csv").dropna()
                if df.empty:
                    df = self.streamer.fetch_price_history(s, i).dropna()
                self.storage.store(s, i, df)

    def read_csv(self, path: str) -> pd.DataFrame:
        """Reads a CSV file and returns a Pandas DataFrame.

        :path: Path to the CSV file.
        """
        if not os.path.isfile(path):
            return pd.DataFrame()
        df = pd.read_csv(path)
        df = df.set_index(["timestamp"])
        if isinstance(df.index[0], str):
            df.index = pd.to_datetime(df.index)
        else:
            df.index = pd.to_datetime(df.index, unit="s")
        df = df[["open", "high", "low", "close", "volume"]].astype(float)
        df = df.sort_index()
        return df

    def run_backtest(self):

        # import cProfile
        # pr = cProfile.Profile()
        # pr.enable()
        # Reset them

        for s in self.stats.interval:
            for i in [self.stats.interval[s]["interval"]] + self.stats.interval[s][
                "aggregations"
            ]:
                self.storage.reset(s, i)

        self.storage.limit_size = True

        common_start = self.common_start
        common_end = self.common_end

        counter = {}
        for s in self.stats.interval:
            inter = self.stats.interval[s]["interval"]
            start_index = list(self.df[s][inter].index).index(common_start)
            self.stats.interval[s]["start"] = start_index
            counter[s] = 0

        self.timestamp = common_start.to_pydatetime()
        print(f"Starting backtest from {common_start}")

        while self.timestamp <= common_end:
            df_dict = {}
            for sym in self.stats.interval:
                inter = self.stats.interval[sym]["interval"]
                if is_freq(self.timestamp, inter):
                    # If data is not in the cache, skip it
                    if self.timestamp in self.df[sym][inter].index:
                        df_dict[sym] = self.df[sym][inter].loc[self.timestamp]

            update = self._update_order_queue()
            self._update_position_cache(df_dict, new=update, option_update=True)
            for sym in self.stats.interval:
                inter = self.stats.interval[sym]["interval"]
                if is_freq(self.timestamp, inter):

                    # If data is not in the cache, skip it
                    if not self.timestamp in self.df[sym][inter].index:
                        continue
                    df = self.df[sym][inter].loc[[self.timestamp], :]
                    self.storage.store(s, inter, df, save_pickle=False)
                    # Add data to aggregation queue
                    for agg in self.stats.interval[sym]["aggregations"]:
                        df = self.df[s][int(agg) - 16].iloc[
                            [self.stats.interval[sym]["start"] + counter[sym]], :
                        ]
                        self.storage.store(s, agg, df)
                    counter[sym] += 1
            new_algo = []
            for a in self.algo:
                if not is_freq(self.timestamp, a.interval):
                    new_algo.append(a)
                    continue
                try:
                    a.main()
                    new_algo.append(a)
                except Exception as e:
                    debugger.debug(
                        f"Algorithm {a} failed, removing from algorithm list.\nException: {e}"
                    )
            if len(new_algo) == 0:
                debugger.debug(f"No algorithms left, exiting")
                break
            self.algo = new_algo

            self.timestamp += interval_to_timedelta(self.streamer.poll_interval)

        # pr.disable()
        # import pstats
        # st = pstats.Stats(pr)
        # st.sort_stats('cumtime')
        # st.print_stats(0.1)
        # st.dump_stats("stat.txt")

        debugger.debug(self.account)

    def _queue_update(self, new_df: pd.DataFrame, time):
        pass

    def _setup_account(self):
        self.account = {
            "equity": 1000000.0,
            "cash": 1000000.0,
            "buying_power": 1000000.0,
            "multiplier": 1,
        }

    def fetch_position(self, key):
        pass

    def fetch_account(self):
        pass
