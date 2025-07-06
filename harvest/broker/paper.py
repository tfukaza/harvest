import datetime as dt
import os
import pickle
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Union

from harvest.broker._base import Broker
from harvest.definitions import OPTION_QTY_MULTIPLIER, Account, Stats
from harvest.enum import DataBrokerType, Interval
from harvest.events.events import OrderFilledEvent
from harvest.events.event_bus import EventBus
from harvest.storage import Storage
from harvest.util.factory import load_broker
from harvest.util.helper import data_to_occ, debugger, is_crypto


class PaperBroker(Broker):
    """
    PaperBroker is a broker class that simulates buying and selling of assets.
    It does this by keeping track of orders and assets in a local database.
    It does not have the ability to retrieve real data from the market,
    so it must be used in conjunction with another broker that can provide data.
    """

    interval_list = [
        Interval.MIN_1,
        Interval.MIN_5,
        Interval.MIN_15,
        Interval.MIN_30,
        Interval.HR_1,
        Interval.DAY_1,
    ]

    def __init__(
        self,
        path: str = None,
        data_source_broker: DataBrokerType = DataBrokerType.DUMMY,
        commission_fee: Union[float, str, Dict[str, Any]] = 0,
        save: bool = False,
    ) -> None:
        """
        :path: Path to a configuration file holding account information for the user.
        :data_source_broker: A broker that can provide data to the PaperBroker.
        :commission_fee: When this is a number it is assumed to be a flat price
            on all buys and sells of assets. When this is a string formatted as
            'XX%' then it is assumed that commission fees are that percent of the
            original cost of the buy or sell. When commission fee is a dictionary
            with the keys 'buy' and 'sell' you can specify different commission
            fees when buying and selling assets. The values must be numbers or
            strings formatted as 'XX%'.
        :save: Whether or not to save the state of the broker to a file.
        """

        super().__init__(path)

        self.stocks = []
        self.options = []
        self.cryptos = []
        self.orders = []
        self.order_id = 0
        self.commission_fee = commission_fee
        self.save = save

        self.data_broker_ref = load_broker(data_source_broker)()

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

        debugger.debug("Broker state: {}".format(self.config))

        # Event bus for publishing order events
        self.event_bus: EventBus | None = None

    def set_event_bus(self, event_bus: EventBus) -> None:
        """Set the event bus for publishing order events"""
        self.event_bus = event_bus

    def _load_account(self) -> None:
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

    def _save_account(self) -> None:
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

    def _delete_account(self) -> None:
        try:
            os.remove(self.save_path)
            debugger.debug("Removed saved account file.")
        except OSError:
            debugger.warning("Saved account file does not exists.")

    def setup(self, stats: Stats, account: Account, trader_main: Callable = None) -> None:
        super().setup(stats, account, trader_main)
        self.backtest = False

    def setup_backtest(self, storage: Storage) -> None:
        self.backtest = True
        self.storage = storage

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

        debugger.debug(f"Backtest: {self.backtest}")

        if self.backtest:
            price = self.storage.load(sym, self.stats.watchlist_cfg[sym]["interval"])[sym]["close"][-1]
        else:
            price = self.data_broker_ref.fetch_price_history(
                sym,
                self.stats.watchlist_cfg[sym]["interval"],
                self.data_broker_ref.get_current_time() - dt.timedelta(days=7),
                self.data_broker_ref.get_current_time(),
            )[sym]["close"][-1]

        debugger.debug(f"Price of {sym} is {price}")

        qty = ret["quantity"]
        original_price = price * qty
        # If order is open, simulate asset buy/sell if possible
        if ret["status"] == "open":
            lst = self.cryptos if is_crypto(ret["symbol"]) else self.stocks
            pos = next((r for r in lst if r["symbol"] == sym), None)
            if ret["side"] == "buy":
                # Check to see if user has enough funds to buy the stock
                debugger.debug(f"Original price: {original_price}")
                actual_price = self.apply_commission(original_price, self.commission_fee, "buy")
                # Check if user has enough buying power
                if self.buying_power + ret["limit_price"] * qty < actual_price:
                    debugger.error(
                        f"""Not enough buying power.\n Total price ({actual_price}) exceeds buying power {self.buying_power}.\n Reduce purchase quantity or increase buying power."""
                    )
                elif ret["limit_price"] < price:
                    limit_price = ret["limit_price"]
                    debugger.info(f"Limit price for {sym} is less than current price ({limit_price} < {price}).")
                else:
                    # If asset already exists, buy more. If not, add a new entry
                    if pos is None:
                        lst.append({"symbol": sym, "avg_price": price, "quantity": qty})
                    else:
                        pos["avg_price"] = (pos["avg_price"] * pos["quantity"] + price * qty) / (qty + pos["quantity"])
                        pos["quantity"] = pos["quantity"] + qty

                    self.cash -= actual_price
                    self.buying_power += (
                        ret["limit_price"] * qty
                    )  # Add back the buying power that was used to buy the stock
                    self.buying_power -= actual_price
                    ret_1 = ret.copy()
                    self.orders.remove(ret)
                    ret = ret_1
                    ret["status"] = "filled"
                    ret["filled_time"] = self.data_broker_ref.get_current_time()
                    ret["filled_price"] = price

                    # Publish order filled event
                    if self.event_bus:
                        event_data = {
                            'order_id': ret["order_id"],
                            'symbol': ret["symbol"],
                            'side': ret["side"],
                            'quantity': ret["quantity"],
                            'filled_price': ret["filled_price"],
                            'filled_time': ret["filled_time"],
                            'algorithm_name': ''  # Will be set by the service
                        }
                        self.event_bus.publish('order_filled', event_data)
            else:
                if pos is None:
                    raise Exception(f"Cannot sell {sym}, is not owned")

                pos["quantity"] = pos["quantity"] - qty
                if pos["quantity"] < 1e-8:
                    lst.remove(pos)
                actual_worth = self.apply_commission(original_price, self.commission_fee, "sell")
                self.cash += actual_worth
                self.buying_power += actual_worth
                ret_1 = ret.copy()
                self.orders.remove(ret)
                ret = ret_1
                ret["status"] = "filled"
                ret["filled_time"] = self.data_broker_ref.get_current_time()
                ret["filled_price"] = price

                # Publish order filled event
                if self.event_bus:
                    event_data = {
                        'order_id': ret["order_id"],
                        'symbol': ret["symbol"],
                        'side': ret["side"],
                        'quantity': ret["quantity"],
                        'filled_price': ret["filled_price"],
                        'filled_time': ret["filled_time"],
                        'algorithm_name': ''  # Will be set by the service
                    }
                    self.event_bus.publish('order_filled', event_data)

            self.equity = self._calc_equity()

        if "filled_time" not in ret:
            ret["filled_time"] = None
        if "filled_price" not in ret:
            ret["filled_price"] = None

        debugger.debug(f"Returning status: {ret}")
        debugger.debug(f"Positions:\n{self.stocks}\n=========\n{self.cryptos}")
        debugger.debug(f"Equity:{self._calc_equity()}")
        self._save_account()
        return ret

    def fetch_option_order_status(self, order_id: int) -> Dict[str, Any]:
        ret = next(r for r in self.orders if r["order_id"] == order_id)
        sym = ret["base_symbol"]
        occ_sym = ret["symbol"]

        price = self.data_broker_ref.fetch_option_market_data(occ_sym)["price"]

        qty = ret["quantity"]
        original_price = price * qty * OPTION_QTY_MULTIPLIER
        # If order has been opened, simulate asset buy/sell
        if ret["status"] == "open":
            pos = next((r for r in self.options if r["symbol"] == occ_sym), None)
            if ret["side"] == "buy":
                # Check to see if user has enough funds to buy the stock
                actual_price = self.apply_commission(original_price, self.commission_fee, "buy")
                if self.buying_power < actual_price:
                    debugger.error(
                        f"""Not enough buying power.\n Total price ({actual_price}) exceeds buying power {self.buying_power}.\n Reduce purchase quantity or increase buying power."""
                    )
                elif ret["limit_price"] < price:
                    limit_price = ret["limit_price"]
                    debugger.warn(
                        f"Limit price for {sym} is less than current price ({limit_price} < {price}). Cannot buy {sym}!"
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
                                "multiplier": OPTION_QTY_MULTIPLIER,
                                "exp_date": date,
                                "strike_price": strike,
                                "type": option_type,
                            }
                        )
                    else:
                        pos["avg_price"] = (pos["avg_price"] * pos["quantity"] + price * qty) / (qty + pos["quantity"])
                        pos["quantity"] = pos["quantity"] + qty

                    self.cash -= actual_price
                    self.buying_power += ret["limit_price"] * qty * OPTION_QTY_MULTIPLIER
                    self.buying_power -= actual_price
                    ret["status"] = "filled"
                    ret["filled_time"] = self.data_broker_ref.get_current_time()
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
                actual_price = self.apply_commission(original_price, self.commission_fee, "sell")
                self.cash += actual_price
                self.buying_power += actual_price
                debugger.debug(f"Made {sym} {occ_sym} {qty} {price}: {self.buying_power}")
                if pos["quantity"] < 1e-8:
                    self.options.remove(pos)
                ret["status"] = "filled"
                ret["filled_time"] = self.data_broker_ref.get_current_time()
                ret["filled_price"] = price
                ret_1 = ret.copy()
                self.orders.remove(ret)
                ret = ret_1

            self.equity = self._calc_equity()

        debugger.debug(f"Returning status: {ret}")
        debugger.debug(f"Positions:\n{self.stocks}\n{self.options}\n{self.cryptos}")
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
    ) -> Dict[str, Any]:
        self._validate_order(side, quantity, limit_price)

        data = {
            "type": "STOCK",
            "symbol": symbol,
            "quantity": quantity,
            "filled_qty": 0,
            "filled_price": 0,
            "limit_price": limit_price,
            "order_id": self.order_id,
            "time_in_force": in_force,
            "status": "open",
            "side": side,
        }

        self.orders.append(data)
        self.order_id += 1
        ret = {"order_id": data["order_id"], "symbol": data["symbol"]}
        if side == "buy":
            self.buying_power -= quantity * limit_price

        return ret

    def order_crypto_limit(
        self,
        side: str,
        symbol: str,
        quantity: float,
        limit_price: float,
        in_force: str = "gtc",
        extended: bool = False,
    ) -> Dict[str, Any]:
        self._validate_order(side, quantity, limit_price)

        data = {
            "type": "CRYPTO",
            "symbol": "@" + symbol,
            "quantity": quantity,
            "filled_qty": 0,
            "filled_price": 0,
            "limit_price": limit_price,
            "order_id": self.order_id,
            "time_in_force": in_force,
            "status": "open",
            "side": side,
        }

        self.orders.append(data)
        self.order_id += 1
        ret = {"order_id": data["order_id"], "symbol": data["symbol"]}

        if side == "buy":
            self.buying_power -= quantity * limit_price
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
    ) -> Dict[str, Any]:
        self._validate_order(side, quantity, limit_price)

        data = {
            "type": "OPTION",
            "symbol": data_to_occ(symbol, exp_date, option_type, strike),
            "quantity": quantity,
            "filled_qty": 0,
            "filled_price": 0,
            "order_id": self.order_id,
            "time_in_force": in_force,
            "status": "open",
            "side": side,
            "limit_price": limit_price,
            "base_symbol": symbol,
        }

        self.orders.append(data)
        self.order_id += 1
        if side == "buy":
            self.buying_power -= quantity * limit_price * OPTION_QTY_MULTIPLIER

        return {"order_id": data["order_id"], "symbol": data["symbol"]}

    # ------------- Helper methods ------------- #

    def _calc_equity(self) -> float:
        """
        Calculates the total worth of the broker by adding together the
        worth of all stocks, cryptos, options and cash in the broker.
        """
        e = 0
        # Add value of current assets
        for asset in self.stocks + self.cryptos + self.options:
            add = asset["avg_price"] * asset["quantity"]
            if "multiplier" in asset:
                add = add * asset["multiplier"]
            e += add
        e += self.cash
        return float(e)

    def apply_commission(
        self,
        inital_price: float,
        commission_fee: Union[float, str, Dict[str, Any]],
        side: str,
    ) -> float:
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
            raise Exception(f"`commission_fee` {commission_fee} not valid must match this regex expression: {pattern}")
        elif type(commission_fee) is dict:
            return self.apply_commission(inital_price, commission_fee[side], side)
