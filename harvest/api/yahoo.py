# Builtins
import datetime as dt
from typing import Any, Dict, List, Tuple

# External libraries
import tzlocal
import pandas as pd
import yfinance as yf

# Submodule imports
from harvest.api._base import API
from harvest.utils import *


class YahooStreamer(API):

    interval_list = [
        Interval.MIN_1,
        Interval.MIN_5,
        Interval.MIN_15,
        Interval.MIN_30,
        Interval.HR_1,
    ]
    exchange = "NASDAQ"

    def __init__(self, path=None):
        self.timestamp = now()

    def setup(self, interval: Dict, trader_main=None):
        super().setup(interval, trader_main)

        self.watch_ticker = {}

        for s in self.stats.watchlist_cfg:
            if is_crypto(s):
                self.watch_ticker[s] = yf.Ticker(s[1:] + "-USD")
            else:
                self.watch_ticker[s] = yf.Ticker(s)

        self.option_cache = {}

    def fmt_interval(self, interval):
        val, unit = expand_interval(interval)
        if unit == "MIN":
            interval_fmt = f"{val}m"
        elif unit == "HR":
            interval_fmt = f"{val}h"

        return interval_fmt

    def fmt_symbol(self, symbol: str):
        return symbol[1:] + "-USD" if is_crypto(symbol) else symbol

    def unfmt_symbol(self, symbol: str):
        if symbol[-4:] == "-USD":
            return "@" + symbol[:-4]
        return symbol

    def exit(self):
        self.option_cache = {}

    def main(self):
        df_dict = {}
        combo = [
            self.fmt_symbol(sym)
            for sym in self.interval
            if is_freq(self.timestamp, self.interval[sym]["interval"])
        ]

        if len(combo) == 1:
            s = combo[0]
            interval_fmt = self.fmt_interval(
                self.interval[self.unfmt_symbol(s)]["interval"]
            )
            df = yf.download(s, period="1d", interval=interval_fmt, prepost=True)
            debugger.debug(f"From yfinance got: {df}")
            if len(df.index) == 0:
                return
            s = self.unfmt_symbol(s)
            df = self._format_df(df, s)
            df_dict[s] = df
        else:
            names = " ".join(combo)
            df = None
            required_intervals = {}
            for s in combo:
                i = self.interval[self.unfmt_symbol(s)]["interval"]
                if i in required_intervals:
                    required_intervals[i].append(s)
                else:
                    required_intervals[i] = [s]
            for i in required_intervals:
                names = " ".join(required_intervals[i])
                df_tmp = yf.download(
                    names, period="1d", interval=self.fmt_interval(i), prepost=True
                )
                debugger.debug(f"From yfinance got: {df_tmp}")
                df = df_tmp if df is None else df.join(df_tmp)

            if len(df.index) == 0:
                return
            for s in combo:
                df_tmp = df.iloc[:, df.columns.get_level_values(1) == s]
                if len(df_tmp.index) == 0:
                    continue
                df_tmp.columns = df_tmp.columns.droplevel(1)
                if s[-4:] == "-USD":
                    s = "@" + s[:-4]
                df_tmp = self._format_df(df_tmp, s)
                df_dict[s] = df_tmp

        debugger.debug(f"From yfinance dict: {df_dict}")
        self.trader_main(df_dict)

    # -------------- Streamer methods -------------- #

    @API._exception_handler
    def fetch_price_history(
        self,
        symbol: str,
        interval: Interval,
        start: dt.datetime = None,
        end: dt.datetime = None,
    ):

        debugger.debug(f"Fetching {symbol} {interval} price history")
        if isinstance(interval, str):
            interval = interval_string_to_enum(interval)

        if start is None:
            start = epoch_zero()
        if end is None:
            end = now()

        df = pd.DataFrame()

        if start >= end:
            return df

        val, unit = expand_interval(interval)
        if unit == "MIN":
            get_fmt = f"{val}m"
        elif unit == "HR":
            get_fmt = f"{val}h"
        else:
            get_fmt = "1d"

        if interval == Interval.MIN_1:
            period = "5d"
        elif interval >= Interval.MIN_5 and interval <= Interval.HR_1:
            period = "1mo"
        else:
            period = "max"

        crypto = False
        if is_crypto(symbol):
            symbol = symbol[1:] + "-USD"
            crypto = True

        df = yf.download(symbol, period=period, interval=get_fmt, prepost=True)
        if crypto:
            symbol = "@" + symbol[:-4]
        df = self._format_df(df, symbol)
        df = df.loc[start:end]
        return df

    @API._exception_handler
    def fetch_chain_info(self, symbol: str):
        option_list = self.watch_ticker[symbol].options
        return {
            "id": "n/a",
            "exp_dates": [
                convert_input_to_datetime(s, tzlocal.get_localzone())
                for s in option_list
            ],
            "multiplier": 100,
        }

    @API._exception_handler
    def fetch_chain_data(self, symbol: str, date: dt.datetime):

        if (
            bool(self.option_cache)
            and symbol in self.option_cache
            and date in self.option_cache[symbol]
        ):
            return self.option_cache[symbol][date]

        df = pd.DataFrame(columns=["contractSymbol", "exp_date", "strike", "type"])

        chain = self.watch_ticker[symbol].option_chain(date_to_str(date))
        puts = chain.puts
        puts["type"] = "put"
        calls = chain.calls
        calls["type"] = "call"
        df = df.append(puts)
        df = df.append(calls)

        df = df.rename(columns={"contractSymbol": "occ_symbol"})
        df["exp_date"] = df.apply(
            lambda x: self.occ_to_data(x["occ_symbol"])[1], axis=1
        )
        df = df[["occ_symbol", "exp_date", "strike", "type"]]
        df.set_index("occ_symbol", inplace=True)

        if symbol not in self.option_cache:
            self.option_cache[symbol] = {}
        self.option_cache[symbol][date] = df

        return df

    @API._exception_handler
    def fetch_option_market_data(self, occ_symbol: str):
        occ_symbol = occ_symbol.replace(" ", "")
        symbol, date, typ, _ = self.occ_to_data(occ_symbol)
        chain = self.watch_ticker[symbol].option_chain(date_to_str(date))
        chain = chain.calls if typ == "call" else chain.puts
        df = chain[chain["contractSymbol"] == occ_symbol]

        debugger.debug(df)
        return {
            "price": float(df["lastPrice"].iloc[0]),
            "ask": float(df["ask"].iloc[0]),
            "bid": float(df["bid"].iloc[0]),
        }

    # ------------- Broker methods ------------- #

    # Not implemented functions:
    #   fetch_stock_positions
    #   fetch_option_positions
    #   fetch_crypto_positions
    #   update_option_positions
    #   fetch_account
    #   fetch_stock_order_status
    #   fetch_option_order_status
    #   fetch_crypto_order_status
    #   fetch_order_queue

    # --------------- Methods for Trading --------------- #

    # Not implemented functions:
    #   order_limit
    #   order_option_limit

    # ------------- Helper methods ------------- #

    def _format_df(self, df: pd.DataFrame, symbol: str):
        df = df.copy()
        df.reset_index(inplace=True)
        ts_name = df.columns[0]
        df["timestamp"] = df[ts_name]
        df = df.set_index(["timestamp"])
        d = df.index[0]
        if d.tzinfo is None or d.tzinfo.utcoffset(d) is None:
            df = df.tz_localize("UTC")
        else:
            df = df.tz_convert(tz="UTC")
        df = df.drop([ts_name], axis=1)
        df = df.rename(
            columns={
                "Open": "open",
                "Close": "close",
                "High": "high",
                "Low": "low",
                "Volume": "volume",
            }
        )
        df = df[["open", "high", "low", "close", "volume"]].astype(float)

        df.columns = pd.MultiIndex.from_product([[symbol], df.columns])

        return df.dropna()
