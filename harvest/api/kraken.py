# Builtins
import yaml
import datetime as dt
from typing import Any, Dict, List, Tuple

# External libraries
import krakenex
import pandas as pd

# Submodule imports
from harvest.api._base import API
from harvest.utils import *


class Kraken(API):

    interval_list = [Interval.MIN_1, Interval.MIN_5, Interval.HR_1, Interval.DAY_1]

    crypto_ticker_to_kraken_names = {
        "BTC": "XXBTZ",
        "ETH": "XETH",
        "ADA": "ADA",
        "USDT": "USDT",
        "XRP": "XXRP",
        "SOL": "SOL",
        "DOGE": "XDG",
        "DOT": "DOT",
        "USDC": "USDC",
        "UNI": "UNI",
        "LTC": "XLTC",
        "LINK": "LINK",
        "BCH": "BCH",
        "FIL": "FIL",
        "MATIC": "MATIC",
        "WBTC": "WBTC",
        "ETC": "XETC",
        "XLM": "XXLM",
        "TRX": "TRX",
        "DAI": "DAI",
        "EOS": "EOS",
        "ATOM": "ATOM",
        "AAVE": "AAVE",
        "XMR": "XXMR",
        "AXS": "AXS",
        "GRT": "GRT",
        "XTZ": "XXTZ",
        "ALGO": "ALGO",
        "MKR": "MKR",
        "KSM": "KSM",
        "WAVE": "WAVE",
        "COMP": "COMP",
        "DASH": "DASH",
        "CHZ": "CHZ",
        "ZEC": "XZEC",
        "MANA": "MANA",
        "ENJ": "ENJ",
        "SUSHI": "SUSHI",
        "YFI": "YFI",
        "QTUM": "QTUM",
        "FLOW": "FLOW",
        "SNX": "SNX",
        "BAT": "BAT",
        "SC": "SC",
        "ICX": "ICX",
        "PERP": "PERP",
        "BNT": "BNT",
        "OMG": "OMG",
        "CRV": "CRV",
        "ZRX": "ZRX",
        "NANO": "NANO",
        "ANKR": "ANKR",
        "SAND": "SAND",
        "REN": "REN",
        "KAVA": "KAVA",
        "MINA": "MINA",
        "1INCH": "1INCH",
        "GHST": "GHST",
        "ANT": "ANT",
        "REP": "XREP",
        "REPV2": "XREPV2",
        "BADGER": "BADGER",
        "BAL": "BAL",
        "BAND": "BAND",
        "CTSI": "CTSI",
        "CQT": "CQT",
        "EWT": "EWT",
        "MLN": "XMLN",
        "ETH2": "ETH2",
        "GNO": "GNO",
        "INJ": "INJ",
        "KAR": "KAR",
        "KEEP": "KEEP",
        "KNC": "KNC",
        "LSK": "LSK",
        "LTP": "LTP",
        "LRC": "LRC",
        "MIR": "MIR",
        "OCEAN": "OCEAN",
        "PAXG": "PAXG",
        "RARI": "RARI",
        "REN": "REN",
        "XRP": "XXRP",
        "SRM": "SRM",
        "STORJ": "STORJ",
        "TBTC": "TBTC",
        "OGN": "OGN",
        "OXT": "OXT",
    }

    kraken_names_to_crypto_ticker = {
        v: k for k, v in crypto_ticker_to_kraken_names.items()
    }

    def __init__(self, path: str = None):
        super().__init__(path)
        self.api = krakenex.API(self.config["api_key"], self.config["secret_key"])

    def setup(self, interval: Dict, trader_main=None):
        super().setup(interval, trader_main)
        self.watch_crypto = []
        for sym in interval:
            if is_crypto(sym):
                self.watch_crypto.append(sym)
            else:
                debugger.warning(f"Kraken does not support stocks. Ignoring {sym}.")

        self.option_cache = {}

    def exit(self):
        self.option_cache = {}

    def main(self):
        df_dict = {}
        df_dict.update(self.fetch_latest_crypto_price())

        self.trader_main(df_dict)

    @API._exception_handler
    def fetch_latest_crypto_price(self):
        dfs = {}
        for symbol in self.watch_crypto:
            dfs[symbol] = self.fetch_price_history(
                symbol,
                self.interval[symbol]["interval"],
                now() - dt.timedelta(days=7),
                now(),
            ).iloc[[-1]]
        return dfs

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
        elif not has_timezone(start):
            start = set_system_timezone(start)
        if end is None:
            end = now()
        elif not has_timezone(end):
            end = set_system_timezone(end)

        if start >= end:
            return pd.DataFrame()

        if interval not in self.interval_list:
            raise Exception(
                f"Interval {interval} not in interval list. Possible options are: {self.interval_list}"
            )
        val, unit = expand_interval(interval)
        df = self.get_data_from_kraken(symbol, val, unit, start, end)

        return df

    def fetch_chain_info(self, symbol: str):
        raise NotImplementedError("Kraken does not support options.")

    def fetch_chain_data(self, symbol: str, date: dt.datetime):
        raise NotImplementedError("Kraken does not support options.")

    def fetch_option_market_data(self, occ_symbol: str):
        raise NotImplementedError("Kraken does not support options.")

    # ------------- Broker methods ------------- #

    @API._exception_handler
    def fetch_stock_positions(self):
        debugger.error("Kraken does not support stocks. Returning an empty list.")
        return []

    @API._exception_handler
    def fetch_option_positions(self):
        debugger.error("Kraken does not support options")
        return []

    @API._exception_handler
    def fetch_crypto_positions(self):
        positions = self.get_result(self.api.query_private("OpenPositions"))

        def fmt(crypto: Dict[str, Any]):
            # Remove the currency
            symbol = crypto["pair"][:-4]
            # Convert from kraken name to crypto currency ticker
            symbol = kraken_name_to_crypto_ticker.get(symbol)
            return {
                "symbol": "@" + symbol,
                "avg_price": float(crypto["cost"]) / float(crypto["vol"]),
                "quantity": float(crypto["vol"]),
                "kraken": crypto,
            }

        return [fmt(pos) for pos in positions]

    def update_option_positions(self, positions: List[Any]):
        debugger.error("Kraken does not support options. Doing nothing.")

    @API._exception_handler
    def fetch_account(self):
        account = self.get_result(self.api.query_private("Balance"))
        if account is None:
            equity = 0
            cash = 0
        else:
            equity = sum(float(v) for k, v in account.items() if k != "ZUSD")
            cash = account.get("ZUSD", 0)
        return {
            "equity": equity,
            "cash": cash,
            "buying_power": equity + cash,
            "multiplier": 1,
            "kraken": account,
        }

    def fetch_stock_order_status(self, order_id: str):
        return NotImplementedError("Kraken does not support stocks.")

    def fetch_option_order_status(self, order_id: str):
        raise Exception("Kraken does not support options.")

    @API._exception_handler
    def fetch_crypto_order_status(self, order_id: str):
        order = self.api.query_private("QueryOrders", {"txid": order_id})
        symbol = kraken_names_to_crypto_ticker.get(crypto["descr"]["pair"][:-4])
        return {
            "type": "CRYPTO",
            "symbol": "@" + symbol,
            "id": crypto.key(),
            "quantity": float(crypto["vol"]),
            "filled_quantity": float(crypto["vol_exec"]),
            "side": crypto["descr"]["type"],
            "time_in_force": None,
            "status": crypto["status"],
            "kraken": crypto,
        }

    # --------------- Methods for Trading --------------- #

    @API._exception_handler
    def fetch_order_queue(self):
        open_orders = self.get_result(self.api.query_private("OpenOrders"))
        open_orders = open_orders["open"]

        def fmt(crypto: Dict[str, Any]):
            symbol = kraken_names_to_crypto_ticker.get(crypto["descr"]["pair"][:-4])
            return {
                "type": "CRYPTO",
                "symbol": "@" + symbol,
                "id": crypto.key(),
                "quantity": float(crypto["vol"]),
                "filled_quantity": float(crypto["vol_exec"]),
                "side": crypto["descr"]["type"],
                "time_in_force": None,
                "status": crypto["status"],
                "kraken": crypto,
            }

        return [fmt(order) for order in open_orders]

    def order_limit(
        self,
        side: str,
        symbol: str,
        quantity: float,
        limit_price: float,
        in_force: str = "gtc",
        extended: bool = False,
    ):
        if is_crypto(symbol):
            symbol = ticker_to_kraken(symbol)
        else:
            raise Exception("Kraken does not support stocks.")

        order = self.get_result(
            self.api.query_private(
                "AddOrder",
                {
                    "ordertype": "limit",
                    "type": side,
                    "volume": quantity,
                    "pair": symbol,
                },
            )
        )

        return {
            "type": "CRYPTO",
            "id": order["txid"],
            "symbol": symbol,
            "kraken": order,
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
        raise NotImplementedError("Kraken does not support options.")

    # ------------- Helper methods ------------- #

    def get_data_from_kraken(
        self,
        symbol: str,
        multiplier: int,
        timespan: str,
        start: dt.datetime,
        end: dt.datetime,
    ) -> pd.DataFrame:
        if timespan == "MIN":
            multiplier *= 1
        elif timespan == "HR":
            multiplier *= 60
        elif timespan == "DAY":
            multiplier *= 1440

        if is_crypto(symbol):
            temp_symbol = self.ticker_to_kraken(symbol)
        else:
            raise Exception("Kraken does not support stocks.")
        bars = self.get_result(
            self.api.query_public(
                "OHLC",
                {"pair": temp_symbol, "interval": multiplier, "since": end.timestamp},
            )
        )
        df = pd.DataFrame(
            bars[temp_symbol],
            columns=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "vwap",
                "volume",
                "count",
            ],
        )
        df = self._format_df(df, symbol)
        df = df.loc[start:end]
        return df

    def _format_df(self, df: pd.DataFrame, symbol: str):
        df = df[["timestamp", "open", "high", "low", "close", "volume"]].astype(float)
        df.index = pd.to_datetime(df["timestamp"], unit="s", utc=True)
        df = df.drop(columns=["timestamp"])
        df.columns = pd.MultiIndex.from_product([[symbol], df.columns])

        return df.dropna()

    def ticker_to_kraken(self, ticker: str):
        if not is_crypto(ticker):
            raise Exception("Kraken does not support stocks.")

        if ticker[1:] in self.crypto_ticker_to_kraken_names:
            # Currently Harvest supports trades for USD and not other currencies.
            kraken_ticker = self.crypto_ticker_to_kraken_names.get(ticker[1:]) + "USD"
            asset_pairs = self.get_result(self.api.query_public("AssetPairs")).keys()
            if kraken_ticker in asset_pairs:
                return kraken_ticker
            else:
                raise Exception(f"{kraken_ticker} is not a valid asset pair.")
        else:
            raise Exception(f"Kraken does not support ticker {ticker}.")

    def get_result(self, response: Dict[str, Any]):
        """Given a kraken response from an endpoint, either raise an error if an
        error exists or return the data in the results key.
        """
        if len(response["error"]) > 0:
            raise Exception("\n".join(response["error"]))
        return response.get("result", None)

    def create_secret(self, path: str) -> bool:
        import harvest.wizard as wizard

        w = wizard.Wizard()

        w.println("Hmm, looks like you haven't set up an api key for Kraken.")
        should_setup = w.get_bool("Do you want to set it up now?", default="y")

        if not should_setup:
            w.println("You can't use Kraken without an API key.")
            w.println(
                "You can set up the credentials manually, or use other streamers."
            )
            return False

        w.println("Alright! Let's get started")

        have_account = w.get_bool("Do you have an Kraken account?", default="y")
        if not have_account:
            w.println(
                "In that case you'll first need to make an account. This takes a few steps."
            )
            w.println(
                "First visit: https://www.kraken.com/sign-up and sign up. Hit Enter or Return for the next step."
            )
            w.wait_for_input()
            w.println(
                "Create an account, go to your account dropdown > Security > API and create an API key."
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
