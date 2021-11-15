# Builtins
import datetime as dt
from logging import debug
from typing import Any, Dict, List, Tuple

# External libraries
import pandas as pd
import robin_stocks.robinhood as rh
import pytz
import pyotp
import yaml

# Submodule imports
from harvest.api._base import API
from harvest.utils import *


class Robinhood(API):

    interval_list = [Interval.SEC_15, Interval.MIN_5, Interval.HR_1, Interval.DAY_1]
    exchange = "NASDAQ"

    def __init__(self, path=None):
        super().__init__(path)
        self.login()

    def login(self):
        debugger.debug("Logging into Robinhood...")
        totp = pyotp.TOTP(self.config["robin_mfa"]).now()
        rh.login(
            self.config["robin_username"],
            self.config["robin_password"],
            store_session=True,
            mfa_code=totp,
        )

    def refresh_cred(self):
        super().refresh_cred()
        debugger.debug("Logging out of Robinhood...")
        rh.authentication.logout()
        self.login()
        debugger.debug("Logged into Robinhood...")

    # @API._run_once
    def setup(self, interval, trader_main=None):

        super().setup(interval, trader_main)

        # Robinhood only supports 15SEC, 1MIN interval for crypto
        for sym in interval:
            if not is_crypto(sym) and interval[sym]["interval"] < Interval.MIN_5:
                raise Exception(
                    f'Interval {interval[sym]["interval"]} is only supported for crypto'
                )

        # self.__watch_stock = []
        # self.__watch_crypto = []
        # self.__watch_crypto_fmt = []

        # for s in interval:
        #     if is_crypto(s):
        #         self.__watch_crypto_fmt.append(s[1:])
        #         self.__watch_crypto.append(s)
        #     else:
        #         self.__watch_stock.append(s)

        self.__option_cache = {}

    def exit(self):
        self.__option_cache = {}

    # @API._exception_handler
    # def fetch_latest_stock_price(self):
    #     df={}
    #     for s in self.__watch_stock:
    #         ret = rh.get_stock_historicals(
    #             s,
    #             interval=self.__interval_fmt,
    #             span='day',
    #             )
    #         if 'error' in ret or ret == None or (type(ret) == list and len(ret) == 0):
    #             continue
    #         df_tmp = pd.DataFrame.from_dict(ret)
    #         df_tmp = self._format_df(df_tmp, [s], self.interval).iloc[[-1]]
    #         df[s] = df_tmp

    #     return df

    # @API._exception_handler
    # def fetch_latest_crypto_price(self):
    #     df={}
    #     for s in self.__watch_crypto_fmt:
    #         ret = rh.get_crypto_historicals(
    #             s,
    #             interval=self.__interval_fmt,
    #             span='hour',
    #             )
    #         df_tmp = pd.DataFrame.from_dict(ret)
    #         df_tmp = self._format_df(df_tmp, ['@'+s], self.interval).iloc[[-1]]
    #         df['@'+s] = df_tmp

    #     return df

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

        get_interval_fmt = ""

        if interval == Interval.SEC_15:  # Not used
            if symbol[0] != "@":
                raise Exception("15SEC interval is only allowed for crypto")
            get_interval_fmt = "15second"
        elif interval == Interval.MIN_1:
            if symbol[0] != "@":
                raise Exception("MIN interval is only allowed for crypto")
            get_interval_fmt = "15second"
        elif interval == Interval.MIN_5:
            get_interval_fmt = "5minute"
        elif interval == Interval.MIN_15:
            get_interval_fmt = "5minute"
        elif interval == Interval.MIN_30:
            get_interval_fmt = "10minute"
        elif interval == Interval.HR_1:
            get_interval_fmt = "hour"
        elif interval == Interval.DAY_1:
            get_interval_fmt = "day"
        else:
            return df

        delta = end - start
        delta = delta.total_seconds()
        delta = delta / 3600
        if interval == Interval.DAY_1 and delta < 24:
            return df
        if delta < 1 and interval in [Interval.SEC_15, Interval.MIN_1]:
            span = "hour"
        elif delta < 24 or interval in [
            Interval.MIN_5,
            Interval.MIN_15,
            Interval.MIN_30,
            Interval.HR_1,
        ]:
            span = "day"
        elif delta < 24 * 28:
            span = "month"
        elif delta < 24 * 300:
            span = "year"
        else:
            span = "5year"

        if symbol[0] == "@":
            ret = rh.get_crypto_historicals(
                symbol[1:], interval=get_interval_fmt, span=span
            )
        else:
            ret = rh.get_stock_historicals(symbol, interval=get_interval_fmt, span=span)

        df = pd.DataFrame.from_dict(ret)
        df = self._format_df(df, [symbol], interval)
        df = aggregate_df(df, interval)

        return df

    @API._exception_handler
    def fetch_chain_info(self, symbol: str):
        ret = rh.get_chains(symbol)
        return {
            "id": "n/a",
            "exp_dates": [str_to_date(s) for s in ret["expiration_dates"]],
            "multiplier": ret["trade_value_multiplier"],
        }

    @API._exception_handler
    def fetch_chain_data(self, symbol: str, date: dt.datetime):

        if (
            bool(self.__option_cache)
            and symbol in self.__option_cache
            and date in self.__option_cache[symbol]
        ):
            return self.__option_cache[symbol][date]

        ret = rh.find_tradable_options(symbol, date_to_str(date))
        exp_date = []
        strike = []
        type = []
        id = []
        occ = []
        for entry in ret:
            date = entry["expiration_date"]
            date = dt.datetime.strptime(date, "%Y-%m-%d")
            date = pytz.utc.localize(date)
            exp_date.append(date)
            price = float(entry["strike_price"])
            strike.append(price)
            type.append(entry["type"])
            id.append(entry["id"])

            occ.append(self.data_to_occ(symbol, date, type[-1], price))

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

        if symbol not in self.__option_cache:
            self.__option_cache[symbol] = {}
        self.__option_cache[symbol][date] = df

        return df

    @API._exception_handler
    def fetch_option_market_data(self, symbol: str):

        sym, date, type, price = self.occ_to_data(symbol)
        ret = rh.get_option_market_data(
            sym, date.strftime("%Y-%m-%d"), str(price), type
        )
        ret = ret[0][0]
        return {
            "price": float(ret["adjusted_mark_price"]),
            "ask": float(ret["ask_price"]),
            "bid": float(ret["bid_price"]),
        }

    # ------------- Broker methods ------------- #

    @API._exception_handler
    def fetch_stock_positions(self):
        ret = rh.get_open_stock_positions()
        pos = []
        for r in ret:
            # 0 quantity means the order was not fulfilled yet
            if float(r["quantity"]) < 0.0001:
                continue
            sym = rh.get_symbol_by_url(r["instrument"])
            pos.append(
                {
                    "symbol": sym,
                    "avg_price": float(r["average_buy_price"]),
                    "quantity": float(r["quantity"]),
                }
            )
        return pos

    @API._exception_handler
    def fetch_option_positions(self):
        ret = rh.get_open_option_positions()
        pos = []
        # print(ret)
        for r in ret:
            # Get option data such as expiration date
            data = rh.get_option_instrument_data_by_id(r["option_id"])
            pos.append(
                {
                    "base_symbol": r["chain_symbol"],
                    "avg_price": float(r["average_price"])
                    / float(r["trade_value_multiplier"]),
                    "quantity": float(r["quantity"]),
                    "multiplier": float(r["trade_value_multiplier"]),
                    "exp_date": data["expiration_date"],
                    "strike_price": float(data["strike_price"]),
                    "type": data["type"],
                }
            )
            date = data["expiration_date"]
            date = dt.datetime.strptime(date, "%Y-%m-%d")
            pos[-1]["symbol"] = self.data_to_occ(
                r["chain_symbol"], date, data["type"], float(data["strike_price"])
            )

        return pos

    @API._exception_handler
    def fetch_crypto_positions(self, key=None):
        ret = rh.get_crypto_positions()
        pos = []
        for r in ret:
            # Note: It seems Robinhood misspelled 'cost_bases',
            # it should be 'cost_basis'
            if len(r["cost_bases"]) <= 0:
                continue
            qty = float(r["cost_bases"][0]["direct_quantity"])
            if qty < 1e-10:
                continue

            pos.append(
                {
                    "symbol": "@" + r["currency"]["code"],
                    "avg_price": float(r["cost_bases"][0]["direct_cost_basis"]) / qty,
                    "quantity": qty,
                }
            )
        return pos

    @API._exception_handler
    def update_option_positions(self, positions: List[Any]):
        for r in positions:
            sym, date, type, price = self.occ_to_data(r["symbol"])
            upd = rh.get_option_market_data(
                sym, date.strftime("%Y-%m-%d"), str(price), type
            )
            upd = upd[0][0]
            r["current_price"] = float(upd["adjusted_mark_price"])
            r["market_value"] = float(upd["adjusted_mark_price"]) * r["quantity"]
            r["cost_basis"] = r["avg_price"] * r["quantity"]

    @API._exception_handler
    def fetch_account(self):
        ret = rh.load_phoenix_account()
        ret = {
            "equity": float(ret["equities"]["equity"]["amount"]),
            "cash": float(ret["uninvested_cash"]["amount"]),
            "buying_power": float(ret["account_buying_power"]["amount"]),
            "multiplier": float(-1),
        }
        return ret

    @API._exception_handler
    def fetch_stock_order_status(self, id):
        ret = rh.get_stock_order_info(id)
        # Check if any of the orders were executed
        executions = ret["executions"]
        if len(executions) > 0:
            filled_time = self._rh_datestr_to_datetime(executions[0]["timestamp"])
            filled_time = filled_time.replace(tzinfo=pytz.utc)
            filled_price = float(executions[0]["effective_price"])
        else:
            filled_time = None
            filled_price = None
        return {
            "type": "STOCK",
            "id": ret["id"],
            "symbol": ret["symbol"],
            "quantity": ret["qty"],
            "filled_quantity": ret["filled_qty"],
            "side": ret["side"],
            "time_in_force": ret["time_in_force"],
            "status": ret["status"],
            "filled_time": filled_time,
            "filled_price": filled_price,
        }

    @API._exception_handler
    def fetch_option_order_status(self, id):
        ret = rh.get_option_order_info(id)
        debugger.debug(ret)
        # Check if any of the orders were executed
        executions = ret["legs"][0]["executions"]
        if len(executions) > 0:
            filled_time = self._rh_datestr_to_datetime(executions[0]["timestamp"])
            filled_time = filled_time.replace(tzinfo=pytz.utc)
            filled_price = float(executions[0]["effective_price"])
        else:
            filled_time = None
            filled_price = None
        return {
            "type": "OPTION",
            "id": ret["id"],
            "symbol": ret["chain_symbol"],
            "qty": ret["quantity"],
            "filled_qty": ret["processed_quantity"],
            "side": ret["legs"][0]["side"],
            "time_in_force": ret["time_in_force"],
            "status": ret["state"],
            "filled_time": filled_time,
            "filled_price": filled_price,
        }

    @API._exception_handler
    def fetch_crypto_order_status(self, id):
        ret = rh.get_crypto_order_info(id)
        debugger.debug(ret)
        # Check if any of the orders were executed
        executions = ret["executions"]
        if len(executions) > 0:
            filled_time = self._rh_datestr_to_datetime(executions[0]["timestamp"])
            filled_time = filled_time.replace(tzinfo=pytz.utc)
            filled_price = float(executions[0]["effective_price"])
        else:
            filled_time = None
            filled_price = None

        return {
            "type": "CRYPTO",
            "id": ret["id"],
            "symbol": ret["symbol"],
            "quantity": float(ret["quantity"]),
            "filled_qty": float(ret["cumulative_quantity"]),
            "side": ret["side"],
            "time_in_force": ret["time_in_force"],
            "status": ret["state"],
            "filled_time": filled_time,
            "filled_price": filled_price,
        }

    @API._exception_handler
    def fetch_order_queue(self):
        queue = []
        ret = rh.get_all_open_stock_orders()
        for r in ret:
            sym = rh.get_symbol_by_url(r["instrument"])
            queue.append(
                {
                    "type": "STOCK",
                    "symbol": sym,
                    "quantity": r["quantity"],
                    "filled_qty": r["cumulative_quantity"],
                    "id": r["id"],
                    "time_in_force": r["time_in_force"],
                    "status": r["state"],
                    "side": r["side"],
                    "filled_time": None,
                    "filled_price": None,
                }
            )

        ret = rh.get_all_open_option_orders()
        for r in ret:
            debugger.debug(r)
            legs = [{"id": l["id"], "side": l["side"]} for l in r["legs"]]
            date = r["legs"][0]["expiration_date"]
            date = dt.datetime.strptime(date, "%Y-%m-%d")
            s = self.data_to_occ(
                r["chain_symbol"],
                date,
                r["legs"][0]["option_type"],
                float(r["legs"][0]["strike_price"]),
            )
            queue.append(
                {
                    "type": "OPTION",
                    "symbol": s,
                    "base_symbol": r["chain_symbol"],
                    "quantity": r["quantity"],
                    "filled_qty": r["processed_quantity"],
                    "id": r["id"],
                    "time_in_force": r["time_in_force"],
                    "status": r["state"],
                    "legs": legs,
                    "filled_time": None,
                    "filled_price": None,
                }
            )
        ret = rh.get_all_open_crypto_orders()
        for r in ret:
            sym = rh.get_symbol_by_url(r["instrument"])
            queue.append(
                {
                    "type": "CRYPTO",
                    "symbol": sym,
                    "quantity": r["quantity"],
                    "filled_qty": r["cumulative_quantity"],
                    "id": r["id"],
                    "time_in_force": r["time_in_force"],
                    "status": r["state"],
                    "side": r["side"],
                    "filled_time": None,
                    "filled_price": None,
                }
            )
        return queue

    # --------------- Methods for Trading --------------- #

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
        try:
            if side == "buy":
                ret = rh.order_buy_limit(
                    symbol=symbol,
                    quantity=quantity,
                    timeInForce=in_force,
                    limitPrice=limit_price,
                )
            else:
                ret = rh.order_sell_limit(
                    symbol=symbol,
                    quantity=quantity,
                    timeInForce=in_force,
                    limitPrice=limit_price,
                )
            return {
                "type": "STOCK",
                "id": ret["id"],
                "symbol": symbol,
            }
        except:
            debugger.error("Error while placing order.\nReturned: {ret}", exc_info=True)
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
        try:
            if side == "buy":
                ret = rh.order_buy_crypto_limit(
                    symbol=symbol,
                    quantity=quantity,
                    timeInForce=in_force,
                    limitPrice=limit_price,
                )
            else:
                ret = rh.order_sell_crypto_limit(
                    symbol=symbol,
                    quantity=quantity,
                    timeInForce=in_force,
                    limitPrice=limit_price,
                )
            return {
                "type": "CRYPTO",
                "id": ret["id"],
                "symbol": "@" + symbol,
            }
        except:
            debugger.error("Error while placing order.\nReturned: {ret}", exc_info=True)
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
        try:
            if side == "buy":
                ret = rh.order_buy_option_limit(
                    positionEffect="open",
                    creditOrDebit="debit",
                    price=limit_price,
                    symbol=symbol,
                    quantity=quantity,
                    expirationDate=exp_date.strftime("%Y-%m-%d"),
                    strike=strike,
                    optionType=option_type,
                    timeInForce=in_force,
                )
            else:
                ret = rh.order_sell_option_limit(
                    positionEffect="close",
                    creditOrDebit="credit",
                    price=limit_price,
                    symbol=symbol,
                    quantity=quantity,
                    expirationDate=exp_date.strftime("%Y-%m-%d"),
                    strike=strike,
                    optionType=option_type,
                    timeInForce=in_force,
                )
            return {
                "type": "OPTION",
                "id": ret["id"],
                "symbol": symbol,
            }
        except:
            debugger.error("Error while placing order.\nReturned: {ret}", exc_info=True)
            raise Exception("Error while placing order")

    def _format_df(
        self, df: pd.DataFrame, watch: List[str], interval: str, latest: bool = False
    ):
        # Robinhood returns offset-aware timestamps based on timezone GMT-0, or UTC
        df["timestamp"] = pd.to_datetime(df["begins_at"])
        df = df.set_index(["timestamp"])
        df = df.drop(["begins_at"], axis=1)
        df = df.rename(
            columns={
                "open_price": "open",
                "close_price": "close",
                "high_price": "high",
                "low_price": "low",
            }
        )
        df = df[["open", "close", "high", "low", "volume"]].astype(float)

        # RH doesn't support 1MIN intervals natively, so it must be
        # aggregated from 15SEC intervals. In such case, datapoints that are not a full minute should be dropped
        # in case too much time has passed since when the API call was made.
        if interval == "1MIN":
            while df.index[-1].second != 45:
                df = df.iloc[:-1]

        df.columns = pd.MultiIndex.from_product([watch, df.columns])

        return df.dropna()

    def _rh_datestr_to_datetime(self, date_str: str):
        date_str = date_str[:-3] + date_str[-2:]
        return dt.datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f%z")

    def create_secret(self, path):
        import harvest.wizard as wizard

        w = wizard.Wizard()

        w.println(
            "Hmm, looks like you haven't set up login credentials for Robinhood yet."
        )
        should_setup = w.get_bool("Do you want to set it up now?", default="y")

        if not should_setup:
            w.println("You can't use Robinhood unless we can log you in.")
            w.println("You can set up the credentials manually, or use other brokers.")
            return False

        w.println("Alright! Let's get started")

        have_account = w.get_bool("Do you have a Robinhood account?", default="y")
        if not have_account:
            w.println(
                "In that case you'll first need to make an account. I'll wait here, so hit Enter or Return when you've done that."
            )
            w.wait_for_input()

        have_mfa = w.get_bool(
            "Do you have Two Factor Authentication enabled?", default="y"
        )

        if not have_mfa:
            w.println(
                "Robinhood (and Harvest) requires users to have 2FA enabled, so we'll turn that on next."
            )
        else:
            w.println(
                "We'll need to reconfigure 2FA to use Harvest, so temporarily disable 2FA"
            )
            w.wait_for_input()

        w.println(
            "Enable 2FA. Robinhood should ask you what authentication method you want to use."
        )
        w.wait_for_input()
        w.println("Select 'Authenticator App'.")
        w.wait_for_input()
        w.println("Select 'Can't scan'.")
        w.wait_for_input()

        mfa = w.get_string(
            "You should see a string of letters and numbers on the screen. Type it in here",
            pattern=r"[\d\w]+",
        )
        while True:
            try:
                totp = pyotp.TOTP(mfa).now()
            except:
                mfa = w.get_string(
                    "Woah😮 Something went wrong. Make sure you typed in the code correctly.",
                    pattern=r"[\d\w]+",
                )
                continue
            break

        w.print(
            f"Good! Robinhood should now be asking you for a 6-digit passcode. Type in: {totp}"
        )
        w.print(
            f"⚠️  Beware, this passcode expires in a few seconds! If you couldn't type it in time, it should be regenerated."
        )

        new_passcode = True
        while new_passcode:
            new_passcode = w.get_bool(
                "Do you want to generate a new passcode?", default="n"
            )
            if new_passcode:
                totp = pyotp.TOTP(mfa).now()
                w.print(f"New passcode: {totp}")
            else:
                break

        w.println(
            "Robinhood will show you a backup code. This is useful when 2FA fails, so make sure to keep it somewhere safe."
        )
        w.wait_for_input()
        w.println(
            "It is recommended you also set up 2FA using an app like Authy or Google Authenticator, so you don't have to run this setup wizard every time you log into Robinhood."
        )
        w.wait_for_input()
        w.println(
            f"Open an authenticator app of your choice, and use the MFA code you typed in earlier to set up OTP passcodes for Robinhood: {mfa}"
        )
        w.wait_for_input()

        w.println(f"Almost there! Type in your username and password for Robinhood")

        username = w.get_string("Username: ")
        password = w.get_password("Password: ")

        w.println(f"All steps are complete now 🎉. Generating secret.yml...")

        d = {
            "robin_mfa": f"{mfa}",
            "robin_username": f"{username}",
            "robin_password": f"{password}",
        }

        with open(path, "w") as file:
            yml = yaml.dump(d, file)

        w.println(
            f"secret.yml has been created! Make sure you keep this file somewhere secure and never share it with other people."
        )

        return True
