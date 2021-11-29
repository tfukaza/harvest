# Builtins
import yaml
import threading
import datetime as dt
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
        self.data = {}

    async def update_data(self, bar):
        # Update data with the latest bars
        self.data_lock.acquire()
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

        symbol = f"@{symbol}" if is_crypto(symbol) else symbol
        debugger.info(f"Got data for {symbol}")
        df = self._format_df(df, symbol)
        self.data[symbol] = df
        if set(self.data.keys()) == set(self.watch_stock + self.watch_crypto):
            data = self.data
            self.data = {}
            self.data_lock.release()
            self.trader_main(data)
        else:
            self.data_lock.release()

    def setup(self, interval: Dict, trader_main=None):
        super().setup(interval, trader_main)

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
        self.stream.run()

    def exit(self):
        self.option_cache = {}

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
            start = now() - dt.timedelta(days=365 * 5)
        if end is None:
            end = now()

        if start >= end:
            return pd.DataFrame()

        df = self.get_data_from_alpaca(symbol, interval, start, end)
        return df

    @API._exception_handler
    def fetch_chain_info(self, symbol: str):
        raise NotImplementedError("Alpaca does not support options.")

    @API._exception_handler
    def fetch_chain_data(self, symbol: str, date: dt.datetime):
        raise NotImplementedError("Alpaca does not support options.")

    @API._exception_handler
    def fetch_option_market_data(self, occ_symbol: str):
        raise NotImplementedError("Alpaca does not support options.")

    # ------------- Broker methods ------------- #

    @API._exception_handler
    def fetch_stock_positions(self):
        def fmt(stock: Dict[str, Any]):
            return {
                "symbol": stock["symbol"],
                "avg_price": float(stock["avg_entry_price"]),
                "quantity": float(stock["qty"]),
                "alpaca": stock,
            }

        return [
            fmt(pos.__dict__["_raw"])
            for pos in self.api.list_positions()
            if pos.asset_class != "crypto"
        ]

    @API._exception_handler
    def fetch_option_positions(self):
        debugger.error("Alpaca does not support options. Returning an empty list.")
        return []

    @API._exception_handler
    def fetch_crypto_positions(self, key=None):
        if self.basic:
            debugger.error(
                "Alpaca basic accounts do not support crypto. Returning an empty list."
            )
            return []

        def fmt(crypto: Dict[str, Any]):
            return {
                "symbol": "@" + crypto["symbol"],
                "avg_price": float(crypto["avg_entry_price"]),
                "quantity": float(stock["qty"]),
                "alpaca": crypto,
            }

        return [
            fmt(pos.__dict__["_raw"])
            for pos in self.api.list_positions()
            if pos.asset_class == "crypto"
        ]

    @API._exception_handler
    def update_option_positions(self, positions: List[Any]):
        debugger.error("Alpaca does not support options. Doing nothing.")

    @API._exception_handler
    def fetch_account(self):
        account = self.api.get_account().__dict__["_raw"]
        return {
            "equity": float(account["equity"]),
            "cash": float(account["cash"]),
            "buying_power": float(account["buying_power"]),
            "multiplier": float(account["multiplier"]),
            "alpaca": account,
        }

    @API._exception_handler
    def fetch_stock_order_status(self, id: str):
        return self.api.get_order(id).__dict__["_raw"]

    @API._exception_handler
    def fetch_option_order_status(self, id):
        raise NotImplementedError("Alpaca does not support options.")

    @API._exception_handler
    def fetch_crypto_order_status(self, id):
        if self.basic:
            raise Exception("Alpaca basic accounts do not support crypto.")
        return self.api.get_order(id).__dict__["_raw"]

    @API._exception_handler
    def fetch_order_queue(self):
        return [
            self.format_order_status(pos.__dict__["_raw"])
            for pos in self.api.list_orders()
        ]

    # --------------- Methods for Trading --------------- #

    def order_stock_limit(
        self,
        side: str,
        symbol: str,
        quantity: float,
        limit_price: float,
        in_force: str = "gtc",
        extended: bool = False,
    ):

        return self.api.submit_order(
            symbol,
            quantity,
            side=side,
            type="limit",
            limit_price=limit_price,
            time_in_force=in_force,
            extended_hours=extended,
        )

    def order_crypto_limit(
        self,
        side: str,
        symbol: str,
        quantity: float,
        limit_price: float,
        in_force: str = "gtc",
        extended: bool = False,
    ):
        if self.basic:
            raise Exception("Alpaca basic accounts do not support crypto.")

        symbol = symbol[1:]

        order = self.api.submit_order(
            asset,
            quantity,
            side=side,
            type="limit",
            limit_price=limit_price,
            time_in_force=in_force,
            extended_hours=extended,
        ).__dict__["_raw"]

        return {
            "type": "CRYPTO" if is_crypto(symbol) else "STOCK",
            "id": order["id"],
            "symbol": symbol,
            "alpaca": order,
        }

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
        raise NotImplementedError("Alpaca does not support options.")

    # ------------- Helper methods ------------- #

    def format_order_status(self, order: Dict[str, Any], is_stock: bool = True):
        return {
            "type": "STOCK" if is_stock else "CRYPTO",
            "id": order["id"],
            "symbol": ("" if is_stock else "@") + order["symbol"],
            "quantity": float(order["qty"]),
            "filled_quantity": float(order["filed_qty"]),
            "side": order["side"],
            "time_in_force": order["time_in_force"],
            "status": order["status"],
            "alpaca": order,
        }

    def get_data_from_alpaca(
        self,
        symbol: str,
        interval: Interval,
        start: dt.datetime,
        end: dt.datetime,
    ) -> pd.DataFrame:
        if self.basic and is_crypto(symbol):
            debugger.error(
                "Alpaca basic accounts do not support crypto. Returning empty dataframe"
            )
            return pd.DataFrame()

        current_time = now()
        if self.basic and start < current_time - dt.timedelta(days=365 * 5):
            debugger.warning(
                "Start time is over five years old! Only data from the past five years will be returned for basic accounts."
            )
            start = current_time - dt.timedelta(days=365 * 5)

        if self.basic and end >= current_time - dt.timedelta(minutes=15):
            debugger.warning(
                "End time is less than 15 minutes old! Only data over 15 minutes old will be returned for basic accounts."
            )
            end = current_time - dt.timedelta(minutes=15)

        timespan = expand_interval(interval)[1]
        if timespan == "MIN":
            timespan = "1Min"
        elif timespan == "HR":
            timespan = "1Hour"
        elif timespan == "DAY":
            timespan = "1Day"

        start_str = start.isoformat()
        end_str = end.isoformat()

        temp_symbol = symbol[1:] if is_crypto(symbol) else symbol
        bars = self.api.get_bars(
            temp_symbol, TimeFrame(timespan), start_str, end_str, adjustment="raw"
        )
        df = pd.DataFrame((bar.__dict__["_raw"] for bar in bars))
        df = self._format_df(df, symbol)
        df = aggregate_df(df, interval)
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

        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df.set_index("timestamp", inplace=True)

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
