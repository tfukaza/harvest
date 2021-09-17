# Builtins
import yaml
import asyncio
import threading
import datetime as dt
from logging import critical, error, info, warning, debug
from typing import Any, Dict, List, Tuple

# External libraries
import pandas as pd
from alpaca_trade_api.rest import REST, TimeFrame, URL
from alpaca_trade_api import Stream

# Submodule imports
from harvest.api._base import StreamAPI, API
from harvest.utils import *


class Alpaca(StreamAPI):

    interval_list = [
        Interval.MIN_1,
    ]

    def __init__(
        self,
        path: str = None,
        is_basic_account: bool = False,
        paper_trader: bool = False,
    ):
        super().__init__(path)
        self.basic = is_basic_account

        endpoint = (
            "https://paper-api.alpaca.markets"
            if paper_trader
            else "https://api.alpaca.markets"
        )
        self.api = REST(self.config["api_key"], self.config["secret_key"], endpoint)

        data_feed = "iex" if self.basic else "sip"
        self.stream = Stream(
            self.config["api_key"],
            self.config["secret_key"],
            URL(endpoint),
            data_feed=data_feed,
        )
        self.data_lock = threading.Lock()
        self.data = {"stocks": {}, "cryptos": {}}

    async def update_data(self, bar):
        # Update data with the latest bars
        # self.data_lock.acquire()
        bar = bar.__dict__["_raw"]
        symbol = bar["symbol"]
        df = pd.DataFrame(
            [
                {
                    "t": bar["timestamp"],
                    "o": bar["open"],
                    "h": bar["high"],
                    "l": bar["low"],
                    "c": bar["close"],
                    "v": bar["volume"],
                }
            ]
        )
        if is_crypto(symbol):
            self.main(self._format_df(df, symbol))
        else:
            self.main(self._format_df(df, f"@{symbol}"))

    def setup(self, interval: Dict, trader=None, trader_main=None):
        super().setup(interval, trader, trader_main)

        self.watch_stock = []
        self.watch_crypto = []
        cryptos = []

        for s in interval:
            if is_crypto(s):
                self.watch_crypto.append(s)
                cryptos.append(s[1:])
            else:
                self.watch_stock.append(s)

        self.stream.on_bar(*(self.watch_stock + cryptos))(self.update_data)

        self.option_cache = {}

    def start(self):
        threading.Thread(target=self.capture_data, daemon=True).start()

    def capture_data(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.stream.run()

    def exit(self):
        self.option_cache = {}

    # -------------- Streamer methods -------------- #

    @API._exception_handler
    def fetch_price_history(
        self,
        symbol: str,
        interval: str,
        start: dt.datetime = None,
        end: dt.datetime = None,
    ):

        debug(f"Fetching {symbol} {interval} price history")

        if start is None:
            start = now() - dt.timedelta(days=365 * 5)
        if end is None:
            end = now()

        if start >= end:
            return pd.DataFrame()

        val, unit = expand_interval(interval)
        df = self.get_data_from_alpaca(symbol, val, unit, start, end)

        return df

    @API._exception_handler
    def fetch_chain_info(self, symbol: str):
        return {
            "id": "n/a",
            "exp_dates": [str_to_date(s) for s in self.watch_ticker[symbol].options],
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

        if not symbol in self.option_cache:
            self.option_cache[symbol] = {}
        self.option_cache[symbol][date] = df

        return df

    @API._exception_handler
    def fetch_option_market_data(self, occ_symbol: str):
        occ_symbol = occ_symbol.replace(" ", "")
        symbol, date, typ, _ = self.occ_to_data(occ_symbol)
        chain = self.watch_ticker[symbol].option_chain(date_to_str(date))
        if typ == "call":
            chain = chain.calls
        else:
            chain = chain.puts
        df = chain[chain["contractSymbol"] == occ_symbol]
        print(occ_symbol, df)
        return {
            "price": float(df["lastPrice"].iloc[0]),
            "ask": float(df["ask"].iloc[0]),
            "bid": float(df["bid"].iloc[0]),
        }

    # ------------- Broker methods ------------- #

    @API._exception_handler
    def fetch_stock_positions(self):
        return [
            pos.__dict__["_raw"]
            for pos in self.api.list_positions()
            if pos.asset_class != "crypto"
        ]

    @API._exception_handler
    def fetch_option_positions(self):
        raise Exception("Not implemented")

    @API._exception_handler
    def fetch_crypto_positions(self, key=None):
        if self.basic:
            error("Basic accounts can't access crypto. Returning None")
            return None

        return [
            pos.__dict__["_raw"]
            for pos in self.api.list_positions()
            if pos.asset_class == "crypto"
        ]

    @API._exception_handler
    def update_option_positions(self, positions: List[Any]):
        raise Exception("Alpaca does not support options.")

    @API._exception_handler
    def fetch_account(self):
        return self.api.get_account().__dict__["_raw"]

    @API._exception_handler
    def fetch_stock_order_status(self, order_id: str):
        return self.api.get_order(order_id).__dict__["_raw"]

    @API._exception_handler
    def fetch_option_order_status(self, id):
        raise Exception("Alpaca does not support options.")

    @API._exception_handler
    def fetch_crypto_order_status(self, id):
        if self.basic:
            error("Basic accounts can't access crypto. Returning None")
            return None
        return self.api.get_order(order_id).__dict__["_raw"]

    @API._exception_handler
    def fetch_order_queue(self):
        return [pos.__dict__["_raw"] for pos in self.api.list_positions()]

    def order_limit(
        self,
        side: str,
        symbol: str,
        quantity: float,
        limit_price: float,
        in_force: str = "gtc",
        extended: bool = False,
    ):
        if self.basic and is_crypto(symbol):
            error("Basic accounts can't buy/sell crypto. Returning None")
            return None

        if is_crypto(symbol):
            symbol = symbol[1:]

        return self.api.submit_order(
            symbol,
            quantity,
            side=side,
            type="limit",
            limit_price=limit_price,
            time_in_force=in_force,
            extended_hours=extended,
        )

    def order_option_limit(
        self,
        side: str,
        symbol: str,
        quantity: int,
        limit_price: float,
        option_type,
        exp_date: dt.datetime,
        strike,
        in_force: str = "gtc",
    ):
        raise Exception("Alpaca does not support options.")

    # ------------- Helper methods ------------- #

    def get_data_from_alpaca(
        self,
        symbol: str,
        multipler: int,
        timespan: str,
        start: dt.datetime,
        end: dt.datetime,
    ) -> pd.DataFrame:
        if self.basic and is_crypto(symbol):
            error("Basic accounts can't access crypto. Returning empty dataframe")
            return pd.DataFrame()

        if self.basic and start < now() - dt.timedelta(days=365 * 5):
            warning(
                "Start time is over five years old! Only data from the past five years will be returned for basic accounts."
            )

        if timespan == "MIN":
            timespan = "1Min"
        elif timespan == "HR":
            timespan = "1Hour"
        elif timespan == "DAY":
            timespan = "1Day"

        start_str = start.strftime("%Y-%m-%d")
        end_str = end.strftime("%Y-%m-%d")

        temp_symbol = symbol[1:] if is_crypto(symbol) else symbol
        bars = self.api.get_bars(
            temp_symbol, TimeFrame(timespan), start_str, end_str, adjustment="raw"
        )
        df = pd.DataFrame((bar.__dict__["_raw"] for bar in bars))
        df = self._format_df(df, symbol)
        df = aggregate_df(df, f"{multipler}{timespan}")
        df = df.loc[start:end]
        return df

    def _format_df(self, df: pd.DataFrame, symbol: str):
        df = df[["t", "o", "h", "l", "c", "v"]]
        df.rename(
            columns={
                "t": "timestamp",
                "o": "open",
                "h": "high",
                "l": "low",
                "c": "close",
                "v": "volume",
            },
            inplace=True,
        )
        df.set_index("timestamp", inplace=True)
        df.index = pd.DatetimeIndex(df.index)

        df.columns = pd.MultiIndex.from_product([[symbol], df.columns])

        return df.dropna()

    def create_secret(self, path: str) -> bool:
        import harvest.wizard as wizard

        w = wizard.Wizard()

        w.println("Hmm, looks like you haven't set up an api key for Alpaca.")
        should_setup = w.get_bool("Do you want to set it up now?", default="y")

        if not should_setup:
            w.println("You can't use Alpaca without an API key.")
            w.println(
                "You can set up the credentials manually, or use other streamers."
            )
            return False

        w.println("Alright! Let's get started")

        have_account = w.get_bool("Do you have an Alpaca account?", default="y")
        if not have_account:
            w.println(
                "In that case you'll first need to make an account. This takes a few steps."
            )
            w.println(
                "First visit: https://alpaca.markets/ and sign up. Hit Enter or Return for the next step."
            )
            w.wait_for_input()
            w.println("Follow the setups to make an individual or buisness account.")
            w.wait_for_input()
            w.println(
                "In the sidebar of the Alpaca Dashboard, note if you want to use a live account (real money) or a paper account (simulated)."
            )
            w.wait_for_input()
            w.println(
                "On the right-hand side, in the Your API Keys box, click View and then Generate API Key. Copy these somewhere safe."
            )
            w.wait_for_input()

        api_key_id = w.get_string("Enter your API key ID")
        secret_key = w.get_password("Enter your API secret key")

        w.println(f"All steps are complete now 🎉. Generating {path}...")

        d = {"api_key": f"{api_key_id}", "secret_key": f"{secret_key}"}

        with open(path, "w") as file:
            yml = yaml.dump(d, file)

        w.println(
            f"{path} has been created! Make sure you keep this file somewhere secure and never share it with other people."
        )

        return True
