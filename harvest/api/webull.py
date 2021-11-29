# Builtins
import datetime as dt
from typing import Any, Dict, List, Tuple
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
        self.paper = paper_trader
        self.wb_tokens = None
        self.timestamp = now()
        wb_filename = "webull_credentials.json"
        if os.path.isfile(wb_filename):
            self.wb_tokens = pd.read_pickle(wb_filename)
        self.api = webull()
        if self.paper:
            debugger.debug("Using Webull Paper Account...")
            print("Using Webull Paper Account...")
            self.api = paper_webull()
        if self.wb_tokens or hasattr(self, "config"):
            self.login()

    def login(self):
        debugger.debug("Logging into Webull...")
        wb_tokens = self.wb_tokens
        if wb_tokens:
            debugger.debug("Trying token login")
            try:
                ret = self.api.api_login(
                    access_token=wb_tokens["accessToken"],
                    refresh_token=wb_tokens["refreshToken"],
                    token_expire=wb_tokens["tokenExpireTime"],
                    uuid=wb_tokens["uuid"],
                )
                if not self.api.is_logged_in():
                    debugger.debug(f"Token login failed. \n{e}")
                    wb_tokens = None
            except Exception as e:
                debugger.debug(f"Token login failed. \n{e}")
                wb_tokens = None
        if not wb_tokens and hasattr(self, "config"):
            debugger.debug("Trying interactive login.")
            self.api.login(
                self.config["wb_username"], self.config["wb_password"], save_token=True
            )
        debugger.debug(f"Logged-in?: {self.api.is_logged_in()}, Paper: {self.paper}")

    def refresh_cred(self):
        super().refresh_cred()
        # self.api.logout()
        self.api.refresh_login(save_token=True)
        # self.login()

    def enter_live_trade_pin(self):
        if not hasattr(self, "config"):
            return
        if self.paper:
            return
        return self.api.get_trade_token(self.config["wb_trade_pin"])

    def setup(self, interval: Dict, trader_main=None):
        super().setup(interval, trader_main)
        self.watch_stock = []
        self.watch_crypto = []
        self.watch_crypto_fmt = []

        val, unit = expand_interval(self.poll_interval)
        if unit == "MIN":
            self.interval_fmt = f"m{val}"
        elif unit == "HR":
            self.interval_fmt = f"h{val}"

        for s in interval:
            if is_crypto(s):
                self.watch_crypto_fmt.append(s[1:])
                self.watch_crypto.append(s)
            else:
                self.watch_stock.append(s)

        self.__option_cache = {}

    def exit(self):
        pass

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
        interval: Interval,
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
        typ = []
        id_ = []
        occ = []
        for entry in ret:
            date = entry["call"]["expireDate"]
            date = str_to_date(date)
            price = float(entry["strikePrice"])
            if entry.get("call"):
                exp_date.append(date)
                strike.append(price)
                typ.append("call")
                id_.append(entry["call"]["tickerId"])
                occ.append(self.data_to_occ(symbol, date, "call", price))
            if entry.get("put"):
                exp_date.append(date)
                strike.append(price)
                typ.append("put")
                id_.append(entry["put"]["tickerId"])
                occ.append(self.data_to_occ(symbol, date, "put", price))

        df = pd.DataFrame(
            {
                "occ_symbol": occ,
                "exp_date": exp_date,
                "strike": strike,
                "type": typ,
                "id": id_,
            }
        )

        df = df.set_index("occ_symbol")
        if not symbol in self.__option_cache:
            self.__option_cache[symbol] = {}
        self.__option_cache[symbol][date] = df

        return df

    @API._exception_handler
    def fetch_option_market_data(self, symbol: str):
        sym, date, _, price = self.occ_to_data(symbol)
        date = str_to_date(date_to_str(date))

        oc_id = self.__option_cache[sym][date][
            self.__option_cache[sym][date].index == symbol
        ].id[0]

        ret = self.api.get_option_quote(stock=sym, optionId=oc_id)
        if not ret.get("data"):
            debugger.error(f"Error in fetch_option_market_data.\nReturned: {ret}")
            raise Exception(f"Error in fetch_option_market_data.\nReturned: {ret}")
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
            if r.get("assetType") and r.get("assetType") != "stock":
                continue
            pos.append(
                {
                    "symbol": r["ticker"]["disSymbol"],
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
            if not r.get("assetType") or r.get("assetType") != "OPTION":
                continue
            # Get option data such as expiration date
            data = self.api.get_option_quote(
                stock=r["ticker"]["tickerId"], optionId=r["tickerId"]
            )
            pos.append(
                {
                    "base_symbol": r["ticker"]["symbol"],
                    "avg_price": float(r["cost"])
                    / float(data["data"][0]["quoteMultiplier"]),
                    "quantity": float(r["position"]),
                    "multiplier": float(data["data"][0]["quoteMultiplier"]),
                    "exp_date": data["data"][0]["expireDate"],
                    "strike_price": float(data["data"][0]["strikePrice"]),
                    "type": data["data"][0]["direction"],
                }
            )
            pos[-1]["symbol"] = data["data"][0]["symbol"]

        return pos

    @API._exception_handler
    def fetch_crypto_positions(self, key=None):
        ret = self.api.get_positions()
        pos = []
        for r in ret:
            if not r.get("assetType") or r.get("assetType") != "crypto":
                continue
            qty = float(r["position"])

            pos.append(
                {
                    "symbol": "@" + r["ticker"]["symbol"][:-3],
                    "avg_price": float(r["cost"]) / qty,
                    "quantity": qty,
                }
            )
        return pos

    @API._exception_handler
    def update_option_positions(self, positions: List[Any]):
        for r in positions:
            sym, date, _, price = self.occ_to_data(r["occ_symbol"])
            oc_id = self.__option_cache[sym][date][
                self.__option_cache[sym][date].index == symbol
            ].id[0]
            ret = self.api.get_option_quote(stock=sym, optionId=oc_id)

            r["current_price"] = float(ret["data"][0]["close"])
            r["market_value"] = float(ret["data"][0]["close"]) * r["quantity"]
            r["cost_basis"] = r["avg_price"] * r["quantity"]

    def fmt_fetch_account(self, val, data):
        for line in data:
            if line["key"] == val:
                return line["value"]
        return -1

    @API._exception_handler
    def fetch_account(self):
        if not self.api.is_logged_in():
            return None
        ret = self.api.get_account()["accountMembers"]
        return {
            "equity": float(self.fmt_fetch_account("totalMarketValue", ret)),
            "cash": float(self.fmt_fetch_account("cashBalance", ret))
            if not self.paper
            else float(self.fmt_fetch_account("usableCash", ret)),
            "buying_power": float(self.fmt_fetch_account("dayBuyingPower", ret))
            if not self.paper
            else float(self.fmt_fetch_account("usableCash", ret)),
            "bp_options": float(self.fmt_fetch_account("optionBuyingPower", ret)),
            "bp_crypto": float(self.fmt_fetch_account("cryptoBuyingPower", ret)),
            "multiplier": float(-1),
        }

    @API._exception_handler
    def fetch_stock_order_status(self, id):
        ret = self.api.get_history_orders(status="All")
        for r in ret:
            if r["orders"][0]["orderId"] == id:
                return {
                    "type": "STOCK",
                    "id": r["orders"][0]["orderId"],
                    "symbol": r["orders"][0]["ticker"]["symbol"],
                    "price": r.get("lmtPrice"),
                    "avg_price": r.get("avgFilledPrice"),
                    "quantity": r.get("totalQuantity"),
                    "filled_quantity": r.get("filledQuantity"),
                    "side": r["action"],
                    "time_in_force": r["timeInForce"],
                    "status": r["status"].lower(),
                }

    @API._exception_handler
    def fetch_option_order_status(self, id):
        ret = self.api.get_history_orders(status="All")
        for r in ret:
            if r["orders"][0]["orderId"] == id:
                return {
                    "type": "OPTION",
                    "id": r["orders"][0]["orderId"],
                    "symbol": self.data_to_occ(
                        r["orders"][0]["symbol"],
                        str_to_date(r["orders"][0]["optionExpireDate"]),
                        r["orders"][0]["optionType"],
                        float(r["orders"][0]["optionExercisePrice"]),
                    ),
                    "price": r.get("lmtPrice"),
                    "avg_price": r.get("avgFilledPrice"),
                    "qty": r["quantity"],
                    "filled_qty": r["filledQuantity"],
                    "side": r["orders"][0]["optionType"],
                    "time_in_force": r["timeInForce"],
                    "status": r["status"].lower(),
                }

    @API._exception_handler
    def fetch_crypto_order_status(self, id):
        ret = self.api.get_history_orders(status="All")
        for r in ret:
            if r["orderId"] == id:
                return {
                    "type": "CRYPTO",
                    "id": r["orders"][0]["orderId"],
                    "symbol": f"@{r['orders'][0]['ticker']['symbol'].replace('USD', '')}",
                    "qty": float(r["quantity"]),
                    "filled_qty": float(r["cumulative_quantity"]),
                    "filled_price": float(r["executions"][0]["effective_price"])
                    if len(r["executions"])
                    else 0,
                    "filled_cost": float(r["rounded_executed_notional"]),
                    "side": r["side"],
                    "time_in_force": r["timeInForce"],
                    "status": r["status"].lower(),
                }

    @API._exception_handler
    def fetch_order_queue(self):
        queue = []
        ret = self.api.get_current_orders()
        for r in ret:
            queue.append(
                {
                    "type": "STOCK" if self.paper else r["assetType"].upper(),
                    "id": r["orderId"],
                    "symbol": r["ticker"]["symbol"],
                    "price": r.get("lmtPrice"),
                    # " avg_price": r.get["orders"][0].get("avgFilledPrice"),
                    "quantity": r["totalQuantity"],
                    "filled_qty": r["filledQuantity"],
                    "time_in_force": r["timeInForce"],
                    "status": r["status"].lower(),
                    "side": r["action"],
                }
            )
        return queue

    # Order functions are not wrapped in the exception handler to prevent duplicate
    # orders from being made.
    def order_stock_limit(
        self,
        side: str,
        symbol: str,
        quantity: float,
        limit_price: float,
        in_force: str = "gtc",
        extended: bool = False,
    ):
        ret = None
        if not self.enter_live_trade_pin():
            debugger.error("Error while setting trade pin.")
            raise Exception("Error while setting trade pin.")

        try:
            ret = self.api.place_order(
                stock=symbol,
                tId=None,
                price=limit_price,
                action=side.upper(),
                orderType="LMT",
                enforce=in_force.upper(),
                quant=quantity,
                outsideRegularTradingHour=extended,
            )
            typ = "STOCK"
            if not ret.get("success"):
                debugger.error(f"Error while placing order.\nReturned: {ret}")
                raise Exception("Error while placing order.")
            return {"type": typ, "id": ret["data"]["orderId"], "symbol": symbol}
        except Exception as e:
            debugger.error(
                f"Error while placing order.\nReturned: {ret}", exc_info=True
            )
            raise Exception("Error while placing order.")

    def order_crypto_limit(
        self,
        side: str,
        symbol: str,
        quantity: float,
        limit_price: float,
        in_force: str = "gtc",
        extended: bool = False,
    ):
        ret = None
        if not self.enter_live_trade_pin():
            debugger.error("Error while setting trade pin.")
            raise Exception("Error while setting trade pin.")

        try:
            ret = self.api.place_order_crypto(
                stock=symbol,
                tId=None,
                price=limit_price,
                action=side.upper(),
                orderType="LMT",
                enforce=in_force.upper(),
                entrust_type="QTY",
                quant=quantity,
                outsideRegularTradingHour=extended,
            )
            typ = "CRYPTO"
            if not ret.get("success"):
                debugger.error(f"Error while placing order.\nReturned: {ret}")
                raise Exception("Error while placing order.")
            return {"type": typ, "id": ret["data"]["orderId"], "symbol": symbol}
        except Exception as e:
            debugger.error(
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
        self.enter_live_trade_pin()
        ret = None
        sym = self.data_to_occ(symbol, exp_date, side, strike)
        date = str_to_date(date_to_str(exp_date))
        oc_id = (
            self.__option_cache[symbol][date][
                self.__option_cache[symbol][date].index == sym
            ]
            .id[0]
            .item()
        )

        if not isinstance(oc_id, int):
            debugger.error(
                "Error while placing order_option_limit. Can't find optionId."
            )
            raise Exception("Error while placing order.")
        try:
            ret = self.api.place_order_option(
                optionId=oc_id,
                lmtPrice=limit_price,
                stpPrice=None,
                action=side.upper(),
                orderType="LMT",
                enforce=in_force.upper(),
                quant=quantity,
            )

            if not ret or not ret.get("orderId"):
                debugger.error(f"Error while placing order.\nReturned: {ret}")
                raise Exception("Error while placing order.")
            return {"type": "OPTION", "id": ret["orderId"], "symbol": symbol}

        except:
            debugger.error(
                f"Error while placing order.\nReturned: {ret}", exc_info=True
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

        pin = w.get_password("Enter trade PIN for live trading: ")

        while len(pin) != 6:
            new_pin = w.get_bool(
                "The pin code should be only 6 digits... do you want to re-try?",
                default="n",
            )
            if new_pin:
                pin = w.get_password("PIN for live trading: ")
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

        if isinstance(pin, int) and not wb.get_trade_token(pin):
            w.println(
                f"Trade PIN verification failed... check your info and try again.\nReason: {ret}"
            )
            return False

        wb.logout()
        w.println(f"All steps are complete now 🎉. Generating secret.yml...")

        d = {"wb_username": username, "wb_password": password, "wb_trade_pin": pin}

        with open(path, "w") as file:
            yml = yaml.dump(d, file)

        w.println(
            f"secret.yml has been created! Make sure you keep this file somewhere secure and never share it with other people."
        )

        return True
