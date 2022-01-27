# Builtins
import json
from urllib import response
import yaml
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Tuple
import requests

# External libraries
import pandas as pd
import pytz

# Submodule imports
from harvest.api._base import API
from harvest.utils import *


class PolygonStreamer(API):

    interval_list = [Interval.MIN_1, Interval.MIN_5, Interval.HR_1, Interval.DAY_1]

    def __init__(self, path: str = None, is_basic_account: bool = False):
        super().__init__(path)
        self.basic = is_basic_account

    def setup(self, interval, trader_main=None):
        self.watch_stock = []
        self.watch_crypto = []

        for sym in interval:
            if is_crypto(sym):
                self.watch_crypto.append(sym)
            else:
                self.watch_stock.append(sym)

        self.option_cache = {}
        super().setup(interval, trader_main)

    def exit(self):
        self.option_cache = {}

    def main(self):
        df_dict = {}
        combo = self.watch_stock + self.watch_crypto
        if self.basic and len(combo) > 5:
            debugger.error(
                "Basic accounts only allow for 5 API calls per minute, trying to get data for more than 5 assets! Aborting."
            )
            return

        for s in combo:
            df = self.fetch_price_history(
                s, Interval.MIN_1, now() - dt.timedelta(days=1), now()
            ).iloc[-1]
            df_dict[s] = df
            debugger.debug(df)
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

        if start is None:
            start = now() - dt.timedelta(days=365 * 2)
        if end is None:
            end = now()

        if start >= end:
            return pd.DataFrame()

        val, unit = expand_interval(interval)
        return self.get_data_from_polygon(symbol, val, unit, start, end)

    @API._exception_handler
    def fetch_chain_info(self, symbol: str):
        key = self.config["polygon_api_key"]
        request = f"https://api.polygon.io/v3/reference/options/contracts?underlying_ticker={symbol}&apiKey={key}"
        response = requests.get(request)
        ret = response.json()
        dates = {contract["expiration"] for contract in ret["results"]}
        return {
            "id": "n/a",
            "exp_dates": list(dates),
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

        exp_date = date.strftime("%Y-%m-%d")
        key = self.config['polygon_api_key']
        request = f"https://api.polygon.io/v3/reference/options/contracts?underlying_ticker={symbol}&expiration_date={exp_date}&apiKey={key}"
        response = requests.get(request)
        ret = response.json()

        df = pd.DataFrame.from_dict(ret["results"])

        df = df.rename(columns={"contract_type": "type", "strike_price": "strike", "ticker": "occ_symbol"})
        # Remove the "O:" prefix from the option ticker symbol
        df["occ_symbol"] = df["occ_symbol"].str.replace("O:", "")
        # Convert the string timestamps of dataframe to datetime objects
        df["exp_date"] = pd.to_datetime(df["expiration"])
        df["exp_date"] =  pandas_datetime_to_utc(df["exp_date"], pytz.utc)

        
        df = df[["occ_symbol", "exp_date", "strike", "type"]]
        df.set_index("occ_symbol", inplace=True)

        if symbol not in self.option_cache:
            self.option_cache[symbol] = {}
        self.option_cache[symbol][date] = df

        return df

    @API._exception_handler
    def fetch_option_market_data(self, occ_symbol: str):
        key = self.config["polygon_api_key"]
        occ_symbol.replace(" ", "")
        symbol = occ_to_data(occ_symbol)[0]
        request = f"https://api.polygon.io/v3/snapshot/options/{symbol}/O:{occ_symbol}?apiKey={key}"
        response = requests.get(request)
        ret = response.json()
        return {
            "price": ret["results"]["day"]["close"],
            "ask": ret["results"]["last_quote"]["ask"],
            "bid": ret["results"]["last_quote"]["bid"],
        }
    
    @API._exception_handler
    def fetch_market_hours(self, date: datetime.date):
        # Polygon does not support getting market hours,
        # so use the free Tradier API instead.
        # See documentation.tradier.com/brokerage-api/markets/get-clock
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

    def get_data_from_polygon(
        self,
        symbol: str,
        multipler: int,
        timespan: str,
        start: dt.datetime,
        end: dt.datetime,
    ) -> pd.DataFrame:
        if self.basic and start < now() - dt.timedelta(days=365 * 2):
            debugger.warning(
                "Start time is over two years old! Only data from the past two years will be returned for basic accounts."
            )

        if timespan == "MIN":
            timespan = "minute"
        elif timespan == "HR":
            timespan = "hour"
        elif timespan == "DAY":
            timespan = "day"

        start_str = start.strftime("%Y-%m-%d")
        end_str = end.strftime("%Y-%m-%d")

        crypto = False
        if is_crypto(symbol):
            temp_symbol = "X:" + symbol[1:] + "USD"
            crypto = True

        request_form = "https://api.polygon.io/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{start}/{end}?adjusted=true&sort=desc&apiKey={api_key}"
        request = request_form.format(
            symbol=temp_symbol if crypto else symbol,
            multiplier=multipler,
            timespan=timespan,
            start=start_str,
            end=end_str,
            api_key=self.config["api_key"],
        )

        response = json.load(urllib.request.urlopen(request))

        if response["status"] != "ERROR":
            df = pd.DataFrame(response["results"]).iloc[::-1]
        else:
            debugger.error(f"Request error! Returning empty dataframe. \n {response}")
            return pd.DataFrame()

        df = self._format_df(df, symbol)
        df = df.loc[start:end]

        return df

    def _format_df(self, df: pd.DataFrame, symbol: str):
        df = df.rename(
            columns={
                "t": "timestamp",
                "o": "open",
                "c": "close",
                "h": "high",
                "l": "low",
                "v": "volume",
            }
        )
        df = df[["timestamp", "open", "high", "low", "close", "volume"]].astype(float)
        df.index = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.drop(columns=["timestamp"], inplace=True)
        df.columns = pd.MultiIndex.from_product([[symbol], df.columns])

        return df.dropna()

    def create_secret(self, path: str) -> bool:
        import harvest.wizard as wizard

        w = wizard.Wizard()

        w.println("Hmm, looks like you haven't set up an api key for Polygon.")
        should_setup = w.get_bool("Do you want to set it up now?", default="y")

        if not should_setup:
            w.println("You can't use Polygon without an API key.")
            w.println(
                "You can set up the credentials manually, or use other streamers."
            )
            return False

        w.println("Alright! Let's get started")

        have_account = w.get_bool("Do you have a Polygon account?", default="y")
        if not have_account:
            w.println(
                "In that case you'll first need to make an account. I'll wait here, so hit Enter or Return when you've done that."
            )
            w.wait_for_input()

        api_key = w.get_string("Enter your API key")

        w.println(f"All steps are complete now 🎉. Generating {path}...")

        d = {
            "api_key": f"{api_key}",
        }

        with open(path, "w") as file:
            yml = yaml.dump(d, file)

        w.println(
            f"{path} has been created! Make sure you keep this file somewhere secure and never share it with other people."
        )

        return True
