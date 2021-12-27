# Builtins
import re
import datetime as dt
from typing import Any, Dict, List, Tuple
from pathlib import Path
import pickle
import os

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
    req_keys = []

    def __init__(self, path: str = None, streamer=None, commission_fee=0, save=False):
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

        self.stocks = []
        self.options = []
        self.cryptos = []
        self.orders = []
        self.order_id = 0
        self.commission_fee = commission_fee
        self.save = save

        self.streamer = DummyStreamer() if streamer is None else streamer

        if path is None:
            self.save_path = "./save"
        else:
            self.save_path = path.replace("secret.yaml", "save")

        # If there is a previously saved broker status, load it
        save_file = Path(self.save_path)
        if save_file.is_file() and save:
            self._load_account()

        if path is None or self.config is None:
            self.config = {
                "paper_equity": 1000000.0,
                "paper_cash": 1000000.0,
                "paper_buying_power": 1000000.0,
                "paper_multiplier": 1,
            }
        else:
            self.commission_fee = self.config["commission_fee"]

        self.equity = self.config["paper_equity"]
        self.cash = self.config["paper_cash"]
        self.buying_power = self.config["paper_buying_power"]
        self.multiplier = self.config["paper_multiplier"]

    def _load_account(self):
        with open(self.save_path, "rb") as stream:
            save_data = pickle.load(stream)

            account = save_data["account"]
            self.equity = account["equity"]
            self.cash = account["cash"]
            self.buying_power = account["buying_power"]
            self.multiplier = account["multiplier"]

            positions = save_data["positions"]
            self.stocks = positions["stocks"]
            self.options = positions["options"]
            self.cryptos = positions["cryptos"]

            orders = save_data["orders"]
            self.orders = orders["orders"]
            self.order_id = orders["order_id"]

    def _save_account(self):
        with open(self.save_path, "wb") as stream:
            save_data = {
                "account": {
                    "equity": self.equity,
                    "cash": self.cash,
                    "buying_power": self.buying_power,
                    "multiplier": self.multiplier,
                },
                "positions": {
                    "stocks": self.stocks,
                    "options": self.options,
                    "cryptos": self.cryptos,
                },
                "orders": {
                    "orders": self.orders,
                    "order_id": self.order_id,
                },
            }
            pickle.dump(save_data, stream)

    def _delete_account(self):
        try:
            os.remove(self.save_path)
            debugger.debug("Removed saved account file.")
        except:
            debugger.warning("Saved account file does not exists.")

    def setup(self, stats, account, trader_main=None):
        super().setup(stats, account, trader_main)

    # -------------- Streamer methods -------------- #

    # Not implemented:
    #   fetch_price_history
    #   fetch_chain_info
    #   fetch_chain_data
    #   fetch_option_market_data

    # ------------- Broker methods ------------- #

    def fetch_stock_positions(self) -> List[Dict[str, Any]]:
        return self.stocks

    def fetch_option_positions(self) -> List[Dict[str, Any]]:
        return self.options

    def fetch_crypto_positions(self) -> List[Dict[str, Any]]:
        return self.cryptos

    # def update_option_positions(self, positions) -> List[Dict[str, Any]]:
    #     for r in self.options:
    #         occ_sym = r["symbol"]
    #         price = self.streamer.fetch_option_market_data(occ_sym)["price"]

    #         r["current_price"] = price
    #         r["market_value"] = price * r["quantity"] * 100
    #         r["cost_basis"] = r["avg_price"] * r["quantity"] * 100

    def fetch_account(self) -> Dict[str, Any]:
        self.equity = self._calc_equity()
        self._save_account()
        return {
            "equity": self.equity,
            "cash": self.cash,
            "buying_power": self.buying_power,
            "multiplier": self.multiplier,
        }

    def fetch_stock_order_status(self, order_id: int) -> Dict[str, Any]:
        ret = next(r for r in self.orders if r["order_id"] == order_id)
        sym = ret["symbol"]

        price = self.streamer.fetch_price_history(
            sym,
            self.stats.watchlist_cfg[sym]["interval"],
            self.streamer.get_current_time() - dt.timedelta(days=7),
            self.streamer.get_current_time(),
        )[sym]["close"][-1]

        qty = ret["quantity"]
        original_price = price * qty
        # If order is open, simulate asset buy/sell if possible
        if ret["status"] == "open":
            lst = self.cryptos if is_crypto(ret["symbol"]) else self.stocks
            pos = next((r for r in lst if r["symbol"] == sym), None)
            if ret["side"] == "buy":
                # Check to see if user has enough funds to buy the stock
                actual_price = self.apply_commission(
                    original_price, self.commission_fee, "sell"
                )
                if self.buying_power < actual_price:
                    debugger.error(
                        f"""Not enough buying power.\n Total price ({actual_price}) exceeds buying power {self.buying_power}.\n Reduce purchase quantity or increase buying power."""
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

                    self.cash -= actual_price
                    self.buying_power -= actual_price
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
                self.cash += actual_worth
                self.buying_power += actual_worth
                ret_1 = ret.copy()
                self.orders.remove(ret)
                ret = ret_1
                ret["status"] = "filled"
                ret["filled_time"] = self.streamer.get_current_time()
                ret["filled_price"] = price

            self.equity = self._calc_equity()

        debugger.debug(f"Returning status: {ret}")
        stocks, cryptos = self.stocks, self.cryptos
        debugger.debug(f"Positions:\n{stocks}\n=========\n{cryptos}")
        debugger.debug(f"Equity:{self._calc_equity()}")
        self._save_account()
        return ret

    def fetch_option_order_status(self, order_id: int) -> Dict[str, Any]:
        ret = next(r for r in self.orders if r["order_id"] == order_id)
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
                if self.buying_power < actual_price:
                    debugger.error(
                        f"""Not enough buying power.\n Total price ({actual_price}) exceeds buying power {self.buying_power}.\n Reduce purchase quantity or increase buying power."""
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

                    self.cash -= actual_price
                    self.buying_power -= actual_price
                    ret["status"] = "filled"
                    ret["filled_time"] = self.streamer.get_current_time()
                    ret["filled_price"] = price
                    debugger.debug(f"After BUY: {self.buying_power}")
                    ret_1 = ret.copy()
                    self.orders.remove(ret)
                    ret = ret_1
            else:
                if pos is None:
                    raise Exception(f"Cannot sell {sym}, is not owned")
                pos["quantity"] = pos["quantity"] - qty
                debugger.debug(f"current:{self.buying_power}")
                actual_price = self.apply_commission(
                    original_price, self.commission_fee, "sell"
                )
                self.cash += actual_price
                self.buying_power += actual_price
                debugger.debug(
                    f"Made {sym} {occ_sym} {qty} {price}: {self.buying_power}"
                )
                if pos["quantity"] < 1e-8:
                    self.options.remove(pos)
                ret["status"] = "filled"
                ret["filled_time"] = self.streamer.get_current_time()
                ret["filled_price"] = price
                ret_1 = ret.copy()
                self.orders.remove(ret)
                ret = ret_1

            self.equity = self._calc_equity()

        debugger.debug(f"Returning status: {ret}")
        stocks, cryptos = self.stocks, self.cryptos
        debugger.debug(f"Positions:\n{stocks}\n{self.options}\n{cryptos}")
        debugger.debug(f"Equity:{self._calc_equity()}")
        self._save_account()
        return ret

    def fetch_crypto_order_status(self, order_id: int) -> Dict[str, Any]:
        return self.fetch_stock_order_status(order_id)

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
            "order_id": self.order_id,
            "time_in_force": in_force,
            "status": "open",
            "side": side,
        }

        self.orders.append(data)
        self.order_id += 1
        ret = {"order_id": data["order_id"], "symbol": data["symbol"]}
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
            "order_id": self.order_id,
            "time_in_force": in_force,
            "status": "open",
            "side": side,
        }

        self.orders.append(data)
        self.order_id += 1
        ret = {"order_id": data["order_id"], "symbol": data["symbol"]}
        return ret

    def order_option_limit(
        self,
        side: str,
        symbol: str,
        quantity: float,
        limit_price: float,
        option_type: str,
        exp_date: dt.datetime,
        strike: float,
        in_force: str = "gtc",
    ):

        data = {
            "type": "OPTION",
            "symbol": data_to_occ(symbol, exp_date, option_type, strike),
            "quantity": quantity,
            "filled_qty": 0,
            "order_id": self.order_id,
            "time_in_force": in_force,
            "status": "open",
            "side": side,
            "limit_price": limit_price,
            "base_symbol": symbol,
        }

        self.orders.append(data)
        self.order_id += 1
        return {"order_id": data["order_id"], "symbol": data["symbol"]}

    # ------------- Helper methods ------------- #

    def _calc_equity(self):
        """
        Calculates the total worth of the broker by adding together the
        worth of all stocks, cryptos, options and cash in the broker.
        """
        e = 0
        for asset in self.stocks + self.cryptos + self.options:
            add = asset["avg_price"] * asset["quantity"]
            if "multiplier" in asset:
                add = add * asset["multiplier"]
            e += add
        e += self.cash
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
                f"`commission_fee` {commission_fee} not valid must match this regex expression: {pattern}"
            )
        elif type(commission_fee) is dict:
            return self.apply_commission(inital_price, commission_fee[side], side)
