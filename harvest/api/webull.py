# Builtins
import datetime as dt
from typing import Any, Dict, List, Tuple
import logging
import os.path

# External libraries
import pandas as pd
from webull import webull, paper_webull
import yaml

# Submodule imports
from harvest.api._base import API
from harvest.utils import *


class Webull(API):
    def __init__(self, path: str = None, paper_trader: bool = False):
        super().__init__(path)
        self.debugger = logging.getLogger("harvest")
        self.paper = paper_trader
        self.wb_tokens = None
        wb_filename = "webull_credentials.json"
        if os.path.isfile(wb_filename):
            self.wb_tokens = pd.read_pickle(wb_filename)
        self.api = webull()
        if self.paper:
            self.api = paper_webull()
        if self.wb_tokens or hasattr(self, "config"):
            self.login()

    def login(self):
        self.debugger.debug("Logging into Webull...")
        wb_tokens = self.wb_tokens
        if wb_tokens:
            self.debugger.debug("Trying token login")
            try:
                ret = self.api.api_login(
                    access_token=wb_tokens["accessToken"],
                    refresh_token=wb_tokens["refreshToken"],
                    token_expire=wb_tokens["tokenExpireTime"],
                    uuid=wb_tokens["uuid"],
                )
                if not self.api.is_logged_in():
                    self.debugger.debug(f"Token login failed. \n{e}")
                    wb_tokens = None
            except Exception as e:
                self.debugger.debug(f"Token login failed. \n{e}")
                wb_tokens = None
        elif not wb_tokens and hasattr(self, "config"):
            self.debugger.debug("Trying interactive login.")
            self.api.login(self.config["wb_username"], self.config["wb_password"])
        self.debugger.debug(
            f"Logged-in?: {self.api.is_logged_in()}, Paper: {self.paper}"
        )

    def refresh_cred(self):
        self.debugger.debug("Refreshing creds for Webull...")
        # self.api.logout()
        self.api.refresh_login(save_token=True)
        # self.login()

    def setup(self, watch: List[str], interval, trader=None, trader_main=None):
        self.watch_stock = []
        self.watch_crypto = []
        self.watch_crypto_fmt = []
        if interval not in self.interval_list:
            raise Exception(f"Invalid interval {interval}")

        for s in watch:
            if is_crypto(s):
                self.watch_crypto_fmt.append(s[1:])
                self.watch_crypto.append(s)
            else:
                self.watch_stock.append(s)

        val, unit = expand_interval(interval)
        if unit == "MIN":
            self.interval_fmt = f"m{val}"
        elif unit == "HR":
            self.interval_fmt = f"h{val}"

        self.__option_cache = {}
        super().setup(watch, interval, interval, trader, trader_main)

    def exit(self):
        self.__option_cache = {}

    def main(self):
        df_dict = {}
        df_dict.update(self.fetch_latest_stock_price())
        df_dict.update(self.fetch_latest_crypto_price())

        self.trader_main(df_dict)

    @API._exception_handler
    def fetch_latest_stock_price(self):
        df = {}
        for s in self.watch_stock:
            ret = self.api.get_bars(stock=s, interval=self.interval_fmt)
            if len(ret) == 0:
                continue
            df_tmp = pd.DataFrame.from_dict(ret)
            df_tmp = self._format_df(df_tmp, [s], self.interval).iloc[[-1]]
            df[s] = df_tmp

        return df

    @API._exception_handler
    def fetch_latest_crypto_price(self):
        df = {}
        for s in self.watch_crypto_fmt:
            ret = self.api.get_bars(stock=s, interval=self.interval_fmt)
            df_tmp = pd.DataFrame.from_dict(ret)
            df_tmp = self._format_df(df_tmp, ["@" + s], self.interval).iloc[[-1]]
            df["@" + s] = df_tmp

        return df

    # -------------- Streamer methods -------------- #

    @API._exception_handler
    def fetch_price_history(
        self,
        symbol: str,
        interval: str,
        start: dt.datetime = None,
        end: dt.datetime = None,
    ):

        if start is None:
            start = dt.datetime(1970, 1, 1)
        if end is None:
            end = dt.datetime.now()

        df = pd.DataFrame()

        if start >= end:
            return df

        val, unit = expand_interval(interval)
        if unit == "MIN":
            self.interval_fmt = f"m{val}"
        elif unit == "HR":
            self.interval_fmt = f"h{val}"

        delta = end - start
        delta = delta.total_seconds()
        delta = delta / 3600
        period = 1
        timeframe = 1
        if interval == "DAY" and delta < 24:
            return df
        if delta < 1 or interval == "15SEC" or interval == "1MIN":
            span = "hour"
            period = 1
            timeframe = 1
        elif delta >= 1 and delta < 24 or interval in ["5MIN", "15MIN", "30MIN", "1HR"]:
            span = "day"
        elif delta >= 24 and delta < 24 * 28:
            span = "month"
        elif delta < 24 * 300:
            span = "year"
        else:
            span = "5year"

        if is_crypto(symbol):
            df = self.api.get_bars(
                symbol[1:],
                interval=self.interval_fmt,
                count=int((390 * int(period)) / int(timeframe)),
            )
        else:
            df = self.api.get_bars(
                symbol,
                interval=self.interval_fmt,
                count=int((390 * int(period)) / int(timeframe)),
            )

        df = self._format_df(df, [symbol], interval)

        return df

    @API._exception_handler
    def fetch_chain_info(self, symbol: str):
        ret = self.api.get_options_expiration_dates(symbol)
        return {
            "id": "n/a",
            "exp_dates": [str_to_date(s["date"]) for s in ret],
            "multiplier": 100,
        }

    @API._exception_handler
    def fetch_chain_data(self, symbol: str, date: dt.datetime):

        if (
            bool(self.__option_cache)
            and symbol in self.__option_cache
            and date in self.__option_cache[symbol]
        ):
            return self.__option_cache[symbol][date]

        ret = self.api.get_options(stock=symbol, expireDate=date_to_str(date))
        exp_date = []
        strike = []
        type = []
        id = []
        occ = []
        for entry in ret:
            date = entry["call"]["expireDate"]
            date = str_to_date(date)
            price = float(entry["strikePrice"])
            if entry.get("call"):
                exp_date.append(date)
                strike.append(price)
                type.append("call")
                id.append(entry["call"]["tickerId"])
                occ.append(self.data_to_occ(symbol, date, "call", price))
            if entry.get("put"):
                exp_date.append(date)
                strike.append(price)
                type.append("put")
                id.append(entry["put"]["tickerId"])
                occ.append(self.data_to_occ(symbol, date, "put", price))

        df = pd.DataFrame(
            {
                "occ_symbol": occ,
                "exp_date": exp_date,
                "strike": strike,
                "type": type,
                "id": id,
            }
        )
        df = df.set_index("occ_symbol")

        if not symbol in self.__option_cache:
            self.__option_cache[symbol] = {}
        self.__option_cache[symbol][date] = df

        return df

    @API._exception_handler
    def fetch_option_market_data(self, symbol: str):
        sym, date, type, price = self.occ_to_data(symbol)
        oc_id = self.__option_cache[sym][date][
            self.__option_cache[sym][date].index == symbol
        ].id[0]
        ret = self.api.get_option_quote(stock=sym, optionId=oc_id)
        if not ret.get("data"):
            self.debugger.error(f"Error in fetch_option_market_data.\nReturned: {ret}")
            raise Exception(f"Error in fetch_option_market_data.\nReturned: {ret}")
            return
        try:
            price = float(ret["data"][0]["close"])
        except:
            price = (
                float(ret["data"][0]["askList"][0]["price"])
                + float(ret["data"][0]["bidList"][0]["price"])
            ) / 2
        return {
            "price": price,
            "ask": float(ret["data"][0]["askList"][0]["price"]),
            "bid": float(ret["data"][0]["bidList"][0]["price"]),
        }

    # ------------- Broker methods ------------- #

    @API._exception_handler
    def fetch_stock_positions(self):
        ret = self.api.get_positions()
        pos = []
        for r in ret:
            if r["assetType"] != "stock":
                continue
            pos.append(
                {
                    "symbol": disSymbol,
                    "avg_price": float(r["costPrice"]),
                    "quantity": float(r["position"]),
                }
            )
        return pos

    @API._exception_handler
    def fetch_option_positions(self):
        ret = self.api.get_positions()
        pos = []
        for r in ret:
            if r["assetType"] != "OPTION":
                continue
            # Get option data such as expiration date
            data = self.api.get_option_quote(
                stock=r["ticker"]["tickerId"], optionId=r["tickerId"]
            )
            pos.append(
                {
                    "symbol": r["ticker"]["symbol"],
                    "avg_price": float(r["cost"])
                    / float(data["data"][0]["quoteMultiplier"]),
                    "quantity": float(r["position"]),
                    "multiplier": float(data["data"][0]["quoteMultiplier"]),
                    "exp_date": data["data"][0]["expireDate"],
                    "strike_price": float(data["data"][0]["strikePrice"]),
                    "type": data["data"][0]["direction"],
                }
            )
            pos[-1]["occ_symbol"] = data["data"][0]["symbol"]

        return pos

    @API._exception_handler
    def fetch_crypto_positions(self, key=None):
        ret = self.api.get_positions()
        pos = []
        for r in ret:
            if r["assetType"] != "crypto":
                continue
            qty = float(r["position"])

            pos.append(
                {
                    "symbol": "@" + r["ticker"]["symbol"],
                    "avg_price": float(r["cost"]) / qty,
                    "quantity": qty,
                }
            )
        return pos

    @API._exception_handler
    def update_option_positions(self, positions: List[Any]):
        for r in positions:
            sym, date, type, price = self.occ_to_data(r["occ_symbol"])
            oc_id = self.__option_cache[sym][date][
                self.__option_cache[sym][date].index == symbol
            ].id[0]
            ret = self.api.get_option_quote(stock=sym, optionId=oc_id)

            r["current_price"] = float(ret["data"][0]["close"])
            r["market_value"] = float(ret["data"][0]["close"]) * r["quantity"]
            r["cost_basis"] = r["avg_price"] * r["quantity"]

    @API._exception_handler
    def fetch_account(self):
        ret = self.api.get_account()["accountMembers"]
        return {
            "equity": float(ret["equities"]["equity"]["amount"]),
            "cash": float(ret["cashBalance"]),
            "buying_power": float(ret["dayBuyingPower"]),
            "bp_options": float(ret["optionBuyingPower"]),
            "bp_crypto": float(ret["cryptoBuyingPower"]),
            "multiplier": float(-1),
        }

    @API._exception_handler
    def fetch_stock_order_status(self, id):
        ret = self.api.get_history_orders()
        for r in ret:
            if r["orderId"] == id:
                return {
                    "type": "STOCK",
                    "id": r["orderId"],
                    "symbol": ret["symbol"],
                    "quantity": ret["qty"],
                    "filled_quantity": ret["filled_qty"],
                    "side": ret["side"],
                    "time_in_force": ret["time_in_force"],
                    "status": ret["status"],
                }

    @API._exception_handler
    def fetch_option_order_status(self, id):
        ret = self.api.get_history_orders()
        for res in ret:
            if r["orderId"] == id:
                return {
                    "type": "OPTION",
                    "id": ret["id"],
                    "symbol": r["chain_symbol"],
                    "qty": ret["quantity"],
                    "filled_qty": ret["processed_quantity"],
                    "side": ret["legs"][0]["side"],
                    "time_in_force": ret["time_in_force"],
                    "status": ret["state"],
                }

    @API._exception_handler
    def fetch_crypto_order_status(self, id):
        ret = self.api.get_history_orders()
        for r in ret:
            if r["orderId"] == id:
                return {
                    "type": "CRYPTO",
                    "id": ret["id"],
                    "qty": float(ret["quantity"]),
                    "filled_qty": float(ret["cumulative_quantity"]),
                    "filled_price": float(ret["executions"][0]["effective_price"])
                    if len(ret["executions"])
                    else 0,
                    "filled_cost": float(ret["rounded_executed_notional"]),
                    "side": ret["side"],
                    "time_in_force": ret["time_in_force"],
                    "status": ret["state"],
                }

    @API._exception_handler
    def fetch_order_queue(self):
        queue = []
        ret = self.api.get_current_orders()
        for r in ret:
            queue.append(
                {
                    "type": r["assetType"],
                    "symbol": r["ticker"]["symbol"],
                    "quantity": r["totalQuantity"],
                    "filled_qty": r["filledQuantity"],
                    "id": r["orderId"],
                    "time_in_force": r["timeInForce"],
                    "status": r["status"],
                    "side": r["action"],
                }
            )
        return queue

    # Order functions are not wrapped in the exception handler to prevent duplicate
    # orders from being made.
    def order_limit(
        self,
        side: str,
        symbol: str,
        quantity: float,
        limit_price: float,
        in_force: str = "gtc",
        extended: bool = False,
    ):
        ret = None
        try:
            if symbol[0] == "@":
                symbol = symbol[1:]
                ret = place_order_crypto(
                    stock=symbol,
                    tId=None,
                    price=limit_price,
                    action=side.upper(),
                    orderType="LMT",
                    enforce=in_force,
                    entrust_type="QTY",
                    quant=quantity,
                    outsideRegularTradingHour=extended,
                )
                typ = "CRYPTO"
            else:
                ret = self.api.place_order(
                    stock=symbol,
                    tId=None,
                    price=limit_price,
                    action=side.upper(),
                    orderType="LMT",
                    enforce=in_force,
                    quant=quantity,
                    outsideRegularTradingHour=extended,
                )
                typ = "STOCK"
            if not ret or not ret.get("data"):
                self.debugger.error(f"Error while placing order.\nReturned: {ret}")
                raise Exception("Error while placing order.")
            return {
                "type": typ,
                "id": ret["data"]["orderId"],
                "symbol": symbol,
            }
        except:
            self.debugger.error(
                f"Error while placing order.\nReturned: {ret}", exc_info=True
            )
            raise Exception("Error while placing order.")

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
        ret = None
        oc_id = self.__option_cache[sym][date][
            self.__option_cache[sym][date].index == symbol
        ].id[0]
        if not isinstance(oc_id, int):
            self.debugger.error(
                f"Error while placing order_option_limit. Can't find optionId."
            )
            raise Exception("Error while placing order.")
        try:
            ret = self.api.place_order_option(
                optionId=oc_id,
                lmtPrice=limit_price,
                stpPrice=None,
                action=side.upper(),
                orderType="LMT",
                enforce=in_force,
                quant=quantity,
            )

            if not ret or not ret.get("data"):
                self.debugger.error(f"Error while placing order.\nReturned: {ret}")
                raise Exception("Error while placing order.")
            return {
                "type": "OPTION",
                "id": ret["data"]["orderId"],
                "symbol": symbol,
            }

        except:
            self.debugger.error(
                "Error while placing order.\nReturned: {ret}", exc_info=True
            )
            raise Exception("Error while placing order")

    def _format_df(
        self, df: pd.DataFrame, watch: List[str], interval: str, latest: bool = False
    ):
        df = df[["open", "close", "high", "low", "volume"]].astype(float)
        df.columns = pd.MultiIndex.from_product([watch, df.columns])
        return df.dropna()

    def create_secret(self, path):
        import harvest.wizard as wizard

        w = wizard.Wizard()

        w.println(
            "Hmm, looks like you haven't set up login credentials for Webull yet."
        )
        should_setup = w.get_bool("Do you want to set it up now?", default="y")

        if not should_setup:
            w.println("Webull has limited functionality when not logged in.")
            w.println("You can set up the credentials manually, or use other brokers.")
            return False

        w.println("Alright! Let's get started")

        have_account = w.get_bool("Do you have a Webull account?", default="y")
        if not have_account:
            w.println(
                "In that case you'll first need to make an account. I'll wait here, so hit Enter or Return when you've done that."
            )
            w.wait_for_input()

        username = w.get_string("Username: ")
        password = w.get_password("Password: ")
        device = w.get_string("Device Name (e.g. Harvester): ")
        w.println(f"Getting security question.")
        from webull import webull

        wb = webull()
        sec_question = wb.get_security(username)[0]

        if not sec_question:
            w.println("Come back after setting up a security question.")
            return False

        sec_answer = w.get_string(f"{sec_question['questionName']}: ")

        if sec_question["questionId"] == "1001":
            sec_check = len(sec_answer)
            while sec_check != 4:
                new_passcode = w.get_bool(
                    "The code should be only 4 digits... do you want to re-try?",
                    default="n",
                )
                if new_passcode:
                    sec_answer = w.get_string(f"{sec_question['questionName']}: ")
                    sec_check = len(sec_answer)
                else:
                    break

        w.println(f"Requesting MFA code via email.")
        wb.get_mfa(username)
        mfa = w.get_password("MFA Code: ")

        ret = wb.login(
            username,
            password,
            device,
            mfa,
            sec_question["questionId"],
            sec_answer,
            save_token=True,
        )

        if not wb.is_logged_in():
            w.println(f"Login failed... check your info and try again.\nReason: {ret}")
            return False

        wb.logout()
        w.println(f"All steps are complete now 🎉. Generating secret.yml...")

        d = {"wb_username": f"{username}", "wb_password": f"{password}"}

        with open(path, "w") as file:
            yml = yaml.dump(d, file)

        w.println(
            f"secret.yml has been created! Make sure you keep this file somewhere secure and never share it with other people."
        )

        return True