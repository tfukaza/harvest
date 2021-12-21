# Builtins
import re
import datetime as dt
from typing import Any, Dict, List, Tuple

# External libraries
import pandas as pd
import yaml

# Submodule imports
from harvest.api._base import API
from harvest.api.dummy import DummyStreamer
from harvest.utils import *


class PaperBroker(API):
    """DummyBroker, as its name implies, is a dummy broker class that can
    be useful for testing algorithms. When used as a streamer, it will return
    randomly generated prices. When used as a broker, it paper trades.
    """

    interval_list = [
        Interval.MIN_1,
        Interval.MIN_5,
        Interval.MIN_15,
        Interval.MIN_30,
        Interval.HR_1,
        Interval.DAY_1,
    ]

    def __init__(self, path: str = None, commission_fee=0, streamer=None):
        """
        :commission_fee: When this is a number it is assumed to be a flat price
            on all buys and sells of assets. When this is a string formatted as
            'XX%' then it is assumed that commission fees are that percent of the
            original cost of the buy or sell. When commission fee is a dictionary
            with the keys 'buy' and 'sell' you can specify different commission
            fees when buying and selling assets. The values must be numbers or
            strings formatted as 'XX%'.
        """

        super().__init__(path)
        self.path = path
        self.options = []
        self.orders = []
        self.commission_fee = commission_fee
        self.id = 0
        self.streamer = DummyStreamer() if streamer is None else streamer

        if self.config is None:
            self.config = {
                "equity": 1000000.0,
                "cash": 1000000.0,
                "buying_power": 1000000.0,
                "multiplier": 1,
                "stocks": [],
                "cryptos": [],
            }

        print("Config", self.config)

    def setup(self, interval, trader_main=None):
        super().setup(interval, trader_main)

    # -------------- Streamer methods -------------- #

    # Not implemented:
    #   fetch_price_history
    #   fetch_chain_info
    #   fetch_chain_data
    #   fetch_option_market_data

    # ------------- Broker methods ------------- #

    def fetch_stock_positions(self) -> List[Dict[str, Any]]:
        return self.config["stocks"]

    def fetch_option_positions(self) -> List[Dict[str, Any]]:
        return self.options

    def fetch_crypto_positions(self) -> List[Dict[str, Any]]:
        return self.config["cryptos"]

    def update_option_positions(self, positions) -> List[Dict[str, Any]]:
        for r in self.options:
            occ_sym = r["symbol"]
            price = self.streamer.fetch_option_market_data(occ_sym)["price"]

            r["current_price"] = price
            r["market_value"] = price * r["quantity"] * 100
            r["cost_basis"] = r["avg_price"] * r["quantity"] * 100

    def fetch_account(self) -> Dict[str, Any]:
        self.config["equity"] = self._calc_equity()
        self.update_account()
        return {
            "equity": self.config["equity"],
            "cash": self.config["cash"],
            "buying_power": self.config["buying_power"],
            "multiplier": self.config["multiplier"],
        }

    def fetch_stock_order_status(self, id: int) -> Dict[str, Any]:
        ret = next(r for r in self.orders if r["id"] == id)
        sym = ret["symbol"]

        price = self.streamer.fetch_price_history(
            sym,
            self.interval[sym]["interval"],
            self.streamer.get_current_time() - dt.timedelta(days=7),
            self.streamer.get_current_time(),
        )[sym]["close"][-1]

        qty = ret["quantity"]
        original_price = price * qty
        # If order is open, simulate asset buy/sell if possible
        if ret["status"] == "open":
            lst = (
                self.config["cryptos"]
                if is_crypto(ret["symbol"])
                else self.config["stocks"]
            )
            pos = next((r for r in lst if r["symbol"] == sym), None)
            if ret["side"] == "buy":
                # Check to see if user has enough funds to buy the stock
                actual_price = self.apply_commission(
                    original_price, self.commission_fee, "sell"
                )
                if self.config["buying_power"] < actual_price:
                    buying_power = self.config["buying_power"]
                    debugger.error(
                        f"""Not enough buying power.\n Total price ({actual_price}) exceeds buying power {buying_power}.\n Reduce purchase quantity or increase buying power."""
                    )
                elif ret["limit_price"] < price:
                    limit_price = ret["limit_price"]
                    debugger.info(
                        f"Limit price for {sym} is less than current price ({limit_price} < {price})."
                    )
                else:
                    # If asset already exists, buy more. If not, add a new entry
                    if pos is None:
                        lst.append({"symbol": sym, "avg_price": price, "quantity": qty})
                    else:
                        pos["avg_price"] = (
                            pos["avg_price"] * pos["quantity"] + price * qty
                        ) / (qty + pos["quantity"])
                        pos["quantity"] = pos["quantity"] + qty

                    self.config["cash"] -= actual_price
                    self.config["buying_power"] -= actual_price
                    ret_1 = ret.copy()
                    self.orders.remove(ret)
                    ret = ret_1
                    ret["status"] = "filled"
                    ret["filled_time"] = self.streamer.get_current_time()
                    ret["filled_price"] = price
            else:
                if pos is None:
                    raise Exception(f"Cannot sell {sym}, is not owned")

                pos["quantity"] = pos["quantity"] - qty
                if pos["quantity"] < 1e-8:
                    lst.remove(pos)
                actual_worth = self.apply_commission(
                    original_price, self.commission_fee, "sell"
                )
                self.config["cash"] += actual_worth
                self.config["buying_power"] += actual_worth
                ret_1 = ret.copy()
                self.orders.remove(ret)
                ret = ret_1
                ret["status"] = "filled"
                ret["filled_time"] = self.streamer.get_current_time()
                ret["filled_price"] = price

            self.config["equity"] = self._calc_equity()

        debugger.debug(f"Returning status: {ret}")
        stocks, cryptos = self.config["stocks"], self.config["cryptos"]
        debugger.debug(f"Positions:\n{stocks}\n=========\n{cryptos}")
        debugger.debug(f"Equity:{self._calc_equity()}")
        self.update_account()
        return ret

    def fetch_option_order_status(self, id: int) -> Dict[str, Any]:
        ret = next(r for r in self.orders if r["id"] == id)
        sym = ret["base_symbol"]
        occ_sym = ret["symbol"]

        price = self.streamer.fetch_option_market_data(occ_sym)["price"]

        qty = ret["quantity"]
        original_price = price * qty
        # If order has been opened, simulate asset buy/sell
        if ret["status"] == "open":
            pos = next((r for r in self.options if r["symbol"] == occ_sym), None)
            if ret["side"] == "buy":
                # Check to see if user has enough funds to buy the stock
                actual_price = self.apply_commission(
                    original_price, self.commission_fee, "buy"
                )
                if self.config["buying_power"] < actual_price:
                    buying_power = self.config["buying_power"]
                    debugger.error(
                        f"""Not enough buying power.\n Total price ({actual_price}) exceeds buying power {buying_power}.\n Reduce purchase quantity or increase buying power."""
                    )
                elif ret["limit_price"] < price:
                    limit_price = ret["limit_price"]
                    debugger.info(
                        f"Limit price for {sym} is less than current price ({limit_price} < {price})."
                    )
                else:
                    # If asset already exists, buy more. If not, add a new entry
                    if pos is None:
                        sym, date, option_type, strike = self.occ_to_data(occ_sym)
                        self.options.append(
                            {
                                "base_symbol": sym,
                                "symbol": ret["symbol"],
                                "avg_price": price,
                                "quantity": ret["quantity"],
                                "multiplier": 100,
                                "exp_date": date,
                                "strike_price": strike,
                                "type": option_type,
                            }
                        )
                    else:
                        pos["avg_price"] = (
                            pos["avg_price"] * pos["quantity"] + price * qty
                        ) / (qty + pos["quantity"])
                        pos["quantity"] = pos["quantity"] + qty

                    self.config["cash"] -= actual_price
                    self.config["buying_power"] -= actual_price
                    ret["status"] = "filled"
                    ret["filled_time"] = self.streamer.get_current_time()
                    ret["filled_price"] = price
                    buying_power = self.config["buying_power"]
                    debugger.debug(f"After BUY: {buying_power}")
                    ret_1 = ret.copy()
                    self.orders.remove(ret)
                    ret = ret_1
            else:
                if pos is None:
                    raise Exception(f"Cannot sell {sym}, is not owned")
                pos["quantity"] = pos["quantity"] - qty
                buying_power = self.config["buying_power"]
                debugger.debug(f"current:{buying_power}")
                actual_price = self.apply_commission(
                    original_price, self.commission_fee, "sell"
                )
                self.config["cash"] += actual_price
                self.config["buying_power"] += actual_price
                buying_power = self.config["buying_power"]
                debugger.debug(f"Made {sym} {occ_sym} {qty} {price}: {buying_power}")
                if pos["quantity"] < 1e-8:
                    self.options.remove(pos)
                ret["status"] = "filled"
                ret["filled_time"] = self.streamer.get_current_time()
                ret["filled_price"] = price
                ret_1 = ret.copy()
                self.orders.remove(ret)
                ret = ret_1

            self.config["equity"] = self._calc_equity()

        debugger.debug(f"Returning status: {ret}")
        stocks, cryptos = self.config["stocks"], self.config["cryptos"]
        debugger.debug(f"Positions:\n{stocks}\n{self.options}\n{cryptos}")
        debugger.debug(f"Equity:{self._calc_equity()}")
        self.update_account()
        return ret

    def fetch_crypto_order_status(self, id: int) -> Dict[str, Any]:
        return self.fetch_stock_order_status(id)

    def fetch_order_queue(self) -> List[Dict[str, Any]]:
        return self.orders

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
        data = {
            "type": "STOCK",
            "symbol": symbol,
            "quantity": quantity,
            "filled_qty": quantity,
            "limit_price": limit_price,
            "id": self.id,
            "time_in_force": in_force,
            "status": "open",
            "side": side,
        }

        self.orders.append(data)
        self.id += 1
        ret = {"type": "STOCK", "id": data["id"], "symbol": data["symbol"]}
        return ret

    def order_crypto_limit(
        self,
        side: str,
        symbol: str,
        quantity: float,
        limit_price: float,
        in_force: str = "gtc",
        extended: bool = False,
    ):
        data = {
            "type": "CRYPTO",
            "symbol": "@" + symbol,
            "quantity": quantity,
            "filled_qty": quantity,
            "limit_price": limit_price,
            "id": self.id,
            "time_in_force": in_force,
            "status": "open",
            "side": side,
        }

        self.orders.append(data)
        self.id += 1
        ret = {"type": "CRYPTO", "id": data["id"], "symbol": data["symbol"]}
        return ret

    def order_option_limit(
        self,
        side: str,
        symbol: str,
        quantity: float,
        limit_price: float,
        type: str,
        exp_date: dt.datetime,
        strike: float,
        in_force: str = "gtc",
    ):

        data = {
            "type": "OPTION",
            "symbol": self.data_to_occ(symbol, exp_date, type, strike),
            "quantity": quantity,
            "filled_qty": 0,
            "id": self.id,
            "time_in_force": in_force,
            "status": "open",
            "side": side,
            "limit_price": limit_price,
            "base_symbol": symbol,
        }

        self.orders.append(data)
        self.id += 1
        return {"type": "OPTION", "id": data["id"], "symbol": data["symbol"]}

    # ------------- Helper methods ------------- #

    def _calc_equity(self):
        """
        Calculates the total worth of the broker by adding together the
        worth of all stocks, cryptos, options and cash in the broker.
        """
        e = 0
        for asset in self.config["stocks"] + self.config["cryptos"] + self.options:
            add = asset["avg_price"] * asset["quantity"]
            if "multiplier" in asset:
                add = add * asset["multiplier"]
            e += add
        e += self.config["cash"]
        return float(e)

    def apply_commission(self, inital_price: float, commission_fee, side: str) -> float:
        if side == "buy":
            f = lambda a, b: float(a + b)
        elif side == "sell":
            f = lambda a, b: float(a - b)

        if type(commission_fee) in (int, float):
            return f(inital_price, commission_fee)
        elif type(commission_fee) is str:
            pattern = r"([0-9]+\.?[0-9]*)\%"
            match = re.fullmatch(pattern, commission_fee)
            if match is not None:
                commission_fee = inital_price * 0.01 * float(match.group(1))
                return f(inital_price, commission_fee)
            raise Exception(
                f"`commission_fee` {commission_fee} not valid, must match this regex expression: {pattern}"
            )
        elif type(commission_fee) is dict:
            return self.apply_commission(inital_price, commission_fee[side], side)

    def update_account(self):
        """
        If the path is set, then save and update the account information.
        """
        print(self.config)
        if self.path is not None:
            with open(self.path, "w") as account:
                yaml.dump(self.config, account)
