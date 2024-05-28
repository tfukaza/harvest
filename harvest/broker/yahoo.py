import datetime
import datetime as dt
import re
from typing import Any, Callable, Dict, Union
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf

from harvest.broker._base import Broker
from harvest.definitions import Account, Stats
from harvest.enum import Interval
from harvest.util.date import convert_input_to_datetime, date_to_str, str_to_datetime, utc_current_time, utc_epoch_zero
from harvest.util.helper import (
    check_interval,
    debugger,
    expand_interval,
    interval_string_to_enum,
    is_crypto,
)


class YahooBroker(Broker):
    interval_list = [
        Interval.MIN_1,
        Interval.MIN_5,
        Interval.MIN_15,
        Interval.MIN_30,
        Interval.HR_1,
    ]
    exchange = "NASDAQ"

    def __init__(self, path: str = None) -> None:
        pass

    def setup(self, stats: Stats, account: Account, trader_main: Callable = None):
        super().setup(stats, account, trader_main)

        self.watch_ticker = {}

        for s in self.stats.watchlist_cfg:
            if is_crypto(s):
                self.watch_ticker[s] = yf.Ticker(s[1:] + "-USD")
            else:
                self.watch_ticker[s] = yf.Ticker(s)

        self.option_cache = {}

    def fmt_interval(self, interval: Interval) -> str:
        val, unit = expand_interval(interval)
        if unit == "MIN":
            interval_fmt = f"{val}m"
        elif unit == "HR":
            interval_fmt = f"{val}h"

        return interval_fmt

    def fmt_symbol(self, symbol: str) -> str:
        return symbol[1:] + "-USD" if is_crypto(symbol) else symbol

    def unfmt_symbol(self, symbol: str) -> str:
        if symbol[-4:] == "-USD":
            return "@" + symbol[:-4]
        return symbol

    def exit(self) -> None:
        self.option_cache = {}

    def step(self) -> None:
        df_dict = {}
        combo = [
            self.fmt_symbol(sym)
            for sym in self.stats.watchlist_cfg
            if check_interval(self.stats.timestamp, self.stats.watchlist_cfg[sym]["interval"])
        ]

        if len(combo) == 1:
            s = combo[0]
            interval_fmt = self.fmt_interval(self.stats.watchlist_cfg[self.unfmt_symbol(s)]["interval"])
            df = yf.download(s, period="1d", interval=interval_fmt, prepost=True, progress=False)
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
                i = self.stats.watchlist_cfg[self.unfmt_symbol(s)]["interval"]
                if i in required_intervals:
                    required_intervals[i].append(s)
                else:
                    required_intervals[i] = [s]
            debugger.debug(f"Required intervals: {required_intervals}")
            for i in required_intervals:
                names = " ".join(required_intervals[i])
                df_tmp = yf.download(
                    names,
                    period="1d",
                    interval=self.fmt_interval(i),
                    prepost=True,
                    progress=False,
                )
                debugger.debug(f"From yfinance got: {df_tmp}")
                df = df_tmp if df is None else df.join(df_tmp)

            if len(df.index) == 0:
                return
            for s in combo:
                debugger.debug(f"Formatting {df}")
                df_tmp = df.iloc[:, df.columns.get_level_values(1) == s]
                if len(df_tmp.index) == 0:
                    continue
                df_tmp.columns = df_tmp.columns.droplevel(1)
                if s[-4:] == "-USD":
                    s = "@" + s[:-4]
                df_tmp = self._format_df(df_tmp, s)
                df_dict[s] = df_tmp

        debugger.debug(f"From yfinance dict: {df_dict}")
        self.broker_hub_cb(df_dict)

    # -------------- Streamer methods -------------- #

    @Broker._exception_handler
    def fetch_price_history(
        self,
        symbol: str,
        interval: Interval,
        start: Union[str, dt.datetime] = None,
        end: Union[str, dt.datetime] = None,
    ) -> pd.DataFrame:
        debugger.debug(f"Fetching {symbol} {interval} price history")
        if isinstance(interval, str):
            interval = interval_string_to_enum(interval)

        start = convert_input_to_datetime(start)
        end = convert_input_to_datetime(end)

        if start is None:
            start = utc_epoch_zero()
        if end is None:
            end = utc_current_time()

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

        if interval <= Interval.MIN_1:
            period = "5d"
        elif interval >= Interval.MIN_5 and interval <= Interval.HR_1:
            period = "1mo"
        else:
            period = "max"

        crypto = False
        if is_crypto(symbol):
            symbol = symbol[1:] + "-USD"
            crypto = True

        df = yf.download(symbol, period=period, interval=get_fmt, prepost=True, progress=False)
        debugger.debug(df)
        if crypto:
            symbol = "@" + symbol[:-4]
        df = self._format_df(df, symbol)
        debugger.debug(f"From yfinance got: {df}")
        debugger.debug(f"Filtering from {start} to {end}")
        df = df.loc[start:end]

        return df

    @Broker._exception_handler
    def fetch_chain_info(self, symbol: str) -> Dict[str, Any]:
        """
        Return the list of option expirations dates available for the given symbol.
        YFinance returns option chain data as tuple of expiration dates, formatted as "YYYY-MM-DD".
        YFinance gets data from  NASDAQ, NYSE, and NYSE America, sp option expiration dates
        use the Eastern Time Zone. (TODO: Check if this is correct)
        """
        option_list = self.watch_ticker[symbol].options
        return {
            "id": "n/a",
            "exp_dates": [str_to_datetime(date) for date in option_list],
            "multiplier": 100,
        }

    @Broker._exception_handler
    def fetch_chain_data(self, symbol: str, date: dt.datetime) -> pd.DataFrame:
        """
        Return the option chain list for a given symbol and expiration date.

        YFinance returns option chain data in the Options class.
        This class has two attributes: calls and puts, each which are DataFrames in the following format:
            contractSymbol          lastTradeDate               strike      lastPrice   bid     ask     change  percentChange   volume  openInterest    impliedVolatility   inTheMoney  contractSize    currency
        0   MSFT240614P00220000     2024-05-13 13:55:14+00:00   220.0       0.02        ...     ...     ...     ...             ...     ...             0.937501            False       REGULAR         USD
        """
        if bool(self.option_cache) and symbol in self.option_cache and date in self.option_cache[symbol]:
            return self.option_cache[symbol][date]

        df = pd.DataFrame(columns=["contractSymbol", "exp_date", "strike", "type"])

        chain = self.watch_ticker[symbol].option_chain(date_to_str(date))

        puts = chain.puts
        puts["type"] = "put"
        calls = chain.calls
        calls["type"] = "call"
        df = pd.concat([df, puts, calls])

        df = df.rename(columns={"contractSymbol": "occ_symbol"})
        df["exp_date"] = df.apply(lambda x: self.occ_to_data(x["occ_symbol"])[1], axis=1)
        df = df[["occ_symbol", "exp_date", "strike", "type"]]
        df.set_index("occ_symbol", inplace=True)

        if symbol not in self.option_cache:
            self.option_cache[symbol] = {}
        self.option_cache[symbol][date] = df

        return df

    @Broker._exception_handler
    def fetch_option_market_data(self, occ_symbol: str) -> Dict[str, Any]:
        """
        Return the market data for a given option symbol.
        """
        occ_symbol = occ_symbol.replace(" ", "")
        symbol, date, typ, _ = self.occ_to_data(occ_symbol)
        chain = self.watch_ticker[symbol].option_chain(date_to_str(date))
        chain = chain.calls if typ == "call" else chain.puts
        df = chain[chain["contractSymbol"] == occ_symbol]
        return {
            "price": float(df["lastPrice"].iloc[0]),
            "ask": float(df["ask"].iloc[0]),
            "bid": float(df["bid"].iloc[0]),
        }

    @Broker._exception_handler
    def fetch_market_hours(self, date: datetime.date) -> Dict[str, Any]:
        """
        Get the market hours for the given date.
        yfinance does not support getting market hours, so use the free Tradier API instead.
        See documentation.tradier.com/brokerage-api/markets/get-clock

        This API cannot be used to check market hours on a specific date, only the current day.
        """

        if date.date() != utc_current_time().date():
            raise ValueError("Cannot check market hours for a specific date")

        response = requests.get(
            "https://api.tradier.com/v1/markets/clock",
            params={"delayed": "false"},
            headers={"Authorization": "123", "Accept": "application/json"},
        )
        ret = response.json()
        debugger.debug(f"Market hours: {ret}")
        ret = ret["clock"]
        desc = ret["description"]
        state = ret["state"]
        if state == "open":
            times = re.sub(r"[^0-9:]", "", desc)
            open_at = convert_input_to_datetime(
                dt.datetime.strptime(times[:5], "%H:%M"),
                ZoneInfo("America/New_York"),
            )
            close_at = convert_input_to_datetime(
                dt.datetime.strptime(times[5:], "%H:%M"),
                ZoneInfo("America/New_York"),
            )
        else:
            open_at = None
            close_at = None

        return {
            "is_open": state == "open",
            "open_at": open_at,
            "close_at": close_at,
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

    def _format_df(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """
        Format the DataFrame returned by yfinance to the format expected by the BrokerHub.

        If the Dataframe contains 1 ticker, Yfinance returns with the following columns:
            Open        High         Low       Close   Adj Close     Volume
        Index is a pandas datetime index

        If the Dataframe contains multiple tickers, Yfinance returns the following multi-index columns:

        Price:  Open            High            Low             Close           Adj Close       Volume
        Ticker: TICK1  TICK2    TICK1  TICK2    TICK1  TICK2    TICK1  TICK2    TICK1  TICK2    TICK1  TICK2
        Index is a pandas datetime index

        """
        # df = df.copy()
        df.reset_index(inplace=True)
        ts_name = df.columns[0]
        df["timestamp"] = df[ts_name]
        print(df)
        df = df.set_index(["timestamp"])
        d = df.index[0]
        if d.tzinfo is None or d.tzinfo.utcoffset(d) is None:
            df = df.tz_localize("UTC")
        else:
            df = df.tz_convert(tz="UTC")
        df = df.drop([ts_name], axis=1)
        # Drop adjusted close column
        df = df.drop(["Adj Close"], axis=1)
        print(df)
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

        print(df)

        df.dropna(inplace=True)

        return df
