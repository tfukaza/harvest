# Builtins
import json
import datetime as dt
from typing import Any, Dict, List, Tuple, Union
import requests

# External libraries
import pandas as pd
import pytz

# Submodule imports
from harvest.api._base import API
from harvest.definitions import *
from harvest.utils import *


class PolygonStreamer(API):

    interval_list = [Interval.MIN_1, Interval.MIN_5, Interval.HR_1, Interval.DAY_1]
    req_keys = ["polygon_api_key"]

    def __init__(self, path: str = None, is_basic_account: bool = False):
        super().__init__(path)

        if self.config is None:
            raise Exception(
                f"Account credentials not found! Expected file path: {path}"
            )

        self.basic = is_basic_account
        self.option_cache = {}

    def main(self):
        df_dict = {}
        combo = self.stats.watchlist_cfg.keys()
        if self.basic and len(combo) > 5:
            debugger.error(
                "Basic accounts only allow for 5 API calls per minute, trying to get data for more than 5 assets! Aborting."
            )
            return

        for s in combo:
            df = self.fetch_price_history(
                s, Interval.MIN_1, now() - dt.timedelta(days=3), now()
            ).iloc[[-1]]
            df_dict[s] = df
            debugger.debug(df)
        self.trader_main(df_dict)

    def exit(self):
        self.option_cache = {}

    # -------------- Streamer methods -------------- #

    @API._exception_handler
    def get_current_time(self) -> dt.datetime:
        key = self.config["polygon_api_key"]
        request = f"https://api.polygon.io/v1/marketstatus/now?apiKey={key}"
        server_time = requests.get(request).json().get("serverTime")
        return dt.datetime.fromisoformat(server_time)

    @API._exception_handler
    def fetch_price_history(
        self,
        symbol: str,
        interval: Interval,
        start: dt.datetime = None,
        end: dt.datetime = None,
    ):

        debugger.debug(f"Fetching {symbol} {interval} price history")

        start = convert_input_to_datetime(start)
        end = convert_input_to_datetime(end)

        if start is None:
            start = now() - dt.timedelta(days=365 * 2)
        if end is None:
            end = now()

        if start >= end:
            return pd.DataFrame()

        val, unit = expand_interval(interval)
        return self._get_data_from_polygon(symbol, val, unit, start, end)

    @API._exception_handler
    def fetch_chain_info(self, symbol: str):
        key = self.config["polygon_api_key"]
        request = f"https://api.polygon.io/v3/reference/options/contracts?underlying_ticker={symbol}&apiKey={key}"
        response = self._handle_request_response(request)
        if response is None:
            raise Exception(f"Failed to fech chain info for {symbol}.")

        dates = {dt.datetime.strptime(contract["expiration_date"], "%Y-%m-%d") for contract in response}
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
        key = self.config["polygon_api_key"]
        request = f"https://api.polygon.io/v3/reference/options/contracts?underlying_ticker={symbol}&expiration_date={exp_date}&apiKey={key}"
        response = self._handle_request_response(request)
        if response is None:
            debugger.error(f"Failed to get chain data for {symbol} at {date}. Returning an empty dataframe.")
            return pd.DataFrame()

        df = pd.DataFrame.from_dict(response)
        df = df.rename(
            columns={
                "contract_type": "type",
                "strike_price": "strike",
                "ticker": "occ_symbol",
            }
        )
        # Remove the "O:" prefix from the option ticker symbol
        df["occ_symbol"] = df["occ_symbol"].str.replace("O:", "")
        # Convert the string timestamps of dataframe to datetime objects
        df["exp_date"] = pd.to_datetime(df["expiration_date"], utc=True)
        df = df[["occ_symbol", "exp_date", "strike", "type"]]
        df.set_index("occ_symbol", inplace=True)

        if symbol not in self.option_cache:
            self.option_cache[symbol] = {}
        self.option_cache[symbol][date] = df

        return df

    @API._exception_handler
    def fetch_option_market_data(self, occ_symbol: str):
        if self.basic:
            raise Exception("Basic accounts do not have access to options.")
        key = self.config["polygon_api_key"]
        occ_symbol.replace(" ", "")
        symbol = occ_to_data(occ_symbol)[0]
        request = f"https://api.polygon.io/v3/snapshot/options/{symbol}/O:{occ_symbol}?apiKey={key}"
        response = self._handle_request_response(request)
        if response is None:
            raise Exception(f"Failed to fetch option market data for {occ_symbol}.")

        return {
            "price": response["day"]["close"],
            "ask": response["last_quote"]["ask"],
            "bid": response["last_quote"]["bid"],
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

    def create_secret(self) -> Dict[str, str]:
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
            "polygon_api_key": f"{api_key}",
        }

        w.println(
            f"{path} has been created! Make sure you keep this file somewhere secure and never share it with other people."
        )

        return d

    def _get_data_from_polygon(
        self,
        symbol: str,
        multiplier: int,
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
        key = self.config["polygon_api_key"]
        temp_symbol = symbol
        if is_crypto(symbol):
            temp_symbol = "X:" + temp_symbol[1:] + "USD"

        request = f"https://api.polygon.io/v2/aggs/ticker/{ temp_symbol }/range/{ multiplier }/{ timespan }/{ start_str }/{ end_str }?adjusted=true&sort=asc&apiKey={ key }"
        response = self._handle_request_response(request)

        if response is None:
            debugger.error(f"Request error! Returning empty dataframe.")
            return pd.DataFrame()

        df = pd.DataFrame(response) 
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
        df.index = pd.DatetimeIndex(
            pd.to_datetime(df["timestamp"], unit="ms", utc=True), tz=dt.timezone.utc
        )
        df.drop(columns=["timestamp"], inplace=True)
        df.columns = pd.MultiIndex.from_product([[symbol], df.columns])

        return df.dropna()

    def _handle_request_response(self, request):
        response = requests.get(request).json()
        if response["status"] == "OK":
            return response["results"]
        message = response["message"]
        debugger.error(f"Request Error!\nRequest: {request}\nResponse: {message}")
        return None 
