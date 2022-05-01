import datetime as dt
from typing import Any, Callable, Dict, Iterable, List
from harvest.utils import symbol_type, occ_to_data


class Stats:
    def __init__(
        self, timestamp: dt.datetime = None, timezone=None, watchlist_cfg=None
    ) -> None:
        self._timestamp = timestamp
        self._timezone = timezone
        self._watchlist_cfg = watchlist_cfg

    def __str__(self) -> str:
        return f"{self.timestamp} {self.timezone} {self.watchlist_cfg}"

    @property
    def timestamp(self) -> dt.datetime:
        return self._timestamp

    @timestamp.setter
    def timestamp(self, value: dt.datetime) -> None:
        self._timestamp = value

    @property
    def timezone(self):
        return self._timezone

    @timezone.setter
    def timezone(self, value) -> None:
        self._timezone = value

    @property
    def watchlist_cfg(self):
        return self._watchlist_cfg

    @watchlist_cfg.setter
    def watchlist_cfg(self, value) -> None:
        self._watchlist_cfg = value


class Functions:
    def __init__(
        self,
        buy: Callable = None,
        sell: Callable = None,
        fetch_chain_data: Callable = None,
        fetch_chain_info: Callable = None,
        fetch_option_market_data: Callable = None,
        get_asset_quantity: Callable = None,
        load: Callable = None,
        save: Callable = None,
        load_daytrade: Callable = None,
    ) -> None:
        self.buy = buy
        self.sell = sell
        self.fetch_chain_data = fetch_chain_data
        self.fetch_chain_info = fetch_chain_info
        self.fetch_option_market_data = fetch_option_market_data
        self.get_asset_quantity = get_asset_quantity
        self.load = load
        self.save = save
        self.load_daytrade = load_daytrade


class Account:
    def __init__(self, account_name: str = None) -> None:
        self._account_name = account_name or "MyAccount"
        self._positions = Positions()
        self._orders = Orders()

        self._asset_value = 0
        self._cash = 0
        self._equity = 0

        self._buying_power = 0
        self._multiplier = 1

    def __str__(self) -> str:
        return (
            f"Account:\t{self._account_name}\n"
            + f"Cash:\t{self._cash}\n"
            + f"Equity:\t{self._equity}\n"
            + f"Buying Power:\t{self._buying_power}\n"
            + f"Multiplier:\t{self._multiplier}\n\n"
            + f"Positions:\n{self._positions}\n\n"
            + f"Orders:\n{self._orders}"
        )

    def init(self, dict: Dict[str, float]) -> None:
        self._equity = dict["equity"]
        self._cash = dict["cash"]
        self._buying_power = dict["buying_power"]
        self._multiplier = dict["multiplier"]

    def update(self) -> None:
        self._asset_value = self._positions.value
        self._equity = self._asset_value + self._cash

    @property
    def account_name(self) -> str:
        return self._account_name

    @property
    def positions(self) -> List:
        return self._positions

    @property
    def orders(self) -> List:
        return self._orders

    @property
    def equity(self) -> float:
        return self._equity

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def buying_power(self) -> float:
        return self._buying_power

    @property
    def multiplier(self) -> float:
        return self._multiplier


class Order:
    def __init__(
        self, symbol: str, order_id: Any, side: str, quantity: float, time_in_force
    ) -> None:
        self._symbol = symbol
        self._order_id = order_id
        self._type = symbol_type(symbol)
        self._side = side
        self._time_in_force = time_in_force
        self._quantity = quantity

        self._status = None
        self._filled_time = None
        self._filled_price = None
        self._filled_quantity = None

    def __str__(self) -> str:
        return f"""
        order_id:       {self._order_id} 
        symbol:         {self._symbol}
        type:           {self._type}
        side:           {self._side}
        quantity:       {self._quantity}
        time_in_force:  {self._time_in_force}
        status:         {self._status}
        filled_time:    {self._filled_time}
        filled_price:   {self._filled_price}
        filled_quantity:{self._filled_quantity}
        """

    @property
    def symbol(self) -> str:
        return self._symbol

    @property
    def type(self) -> str:
        return self._type

    @property
    def quantity(self) -> float:
        return self._quantity

    @property
    def filled_quantity(self) -> float:
        return self._filled_quantity

    @property
    def order_id(self) -> Any:
        return self._order_id

    @property
    def time_in_force(self):
        return self._time_in_force

    @property
    def status(self) -> str:
        return self._status

    @property
    def filled_time(self):
        return self._filled_time

    @property
    def filled_price(self):
        return self._filled_price

    @property
    def side(self) -> str:
        return self._side

    def update(self, val: Dict[str, Any]) -> None:
        self._filled_quantity = val["quantity"]
        self._status = val["status"]
        self._filled_price = val["filled_price"]
        self._filled_time = val["filled_time"]


class Orders:
    def __init__(self) -> None:
        self._orders = []

    def __str__(self) -> str:
        return "\n".join(str(order) for order in self._orders)

    def init(self, orders: Iterable[Dict[str, Any]]) -> None:
        self._orders = [Order(**o) for o in orders]

    @property
    def orders(self) -> List[Order]:
        return self._orders

    def get_order(self, order_id: Any) -> Order:
        for o in self._orders:
            if o.order_id == order_id:
                return o

    def add_new_order(
        self, symbol: str, order_id: Any, side: str, quantity: float, time_in_force
    ) -> None:
        self._orders.append(Order(symbol, order_id, side, quantity, time_in_force))

    def remove_non_open(self) -> None:
        self._orders = list(filter(lambda x: x.status == "open", self._orders))

    @property
    def symbols(self) -> List[str]:
        return [o.symbol for o in self._orders]

    @property
    def stock_crypto_symbols(self) -> List[str]:
        return [o.base_symbol if o.type == "OPTION" else o.symbol for o in self._orders]


class OptionOrder(Order):
    def __init__(
        self,
        type,
        symbol,
        quantity,
        filled_qty,
        id,
        time_in_force,
        status,
        side,
        filled_time,
        filled_price,
        base_symbol,
    ):
        super().__init__(
            type,
            symbol,
            quantity,
            filled_qty,
            id,
            time_in_force,
            status,
            side,
            filled_time,
            filled_price,
        )
        self._base_symbol = base_symbol

    def __str__(self):
        s = super().__str__()
        return f"{s} {self.base_symbol}"

    @property
    def base_symbol(self):
        return self._base_symbol


class Position:
    def __init__(self, symbol, quantity, avg_price):
        self._symbol = symbol
        self._quantity = quantity
        self._avg_price = avg_price

        self._current_price = 0
        self._value = 0
        self._profit = 0
        self._profit_percent = 0

    def update(self, current_price: float):
        self._current_price = current_price
        self._value = self._current_price * self._quantity
        self._profit = self._value - self._avg_price * self._quantity
        self._profit_percent = self._profit / (self._avg_price * self._quantity)

    def buy(self, quantity, price):
        self._avg_price = (self._avg_price * self._quantity + price * quantity) / (
            self._quantity + quantity
        )
        self._quantity += quantity

    def sell(self, quantity, price):
        self._quantity -= quantity

    @property
    def symbol(self):
        return self._symbol

    @property
    def quantity(self):
        return self._quantity

    @property
    def value(self):
        return self._value

    @property
    def avg_price(self):
        return self._avg_price

    @property
    def asset_type(self):
        return symbol_type(self._symbol)

    @property
    def current_price(self):
        return self._current_price

    @property
    def profit(self):
        return self._profit

    @property
    def profit_percent(self):
        return self._profit_percent

    def __str__(self):
        return (
            f"\n[{self._symbol}]\n"
            + f" Quantity:\t{self._quantity}\n"
            + f" Avg. Cost:\t${self._avg_price}\n"
            + f" Price:  \t${self._current_price}\n"
            + f" Value:  \t${self._value}\n"
            + f" Profit:\t${self._profit}\n"
            + f" Returns:\t{'▲' if self._profit_percent > 0 else '▼'}{self._profit_percent * 100}%\n"
            + "─" * 50
        )


class Positions:
    def __init__(self, stock=[], option=[], crypto=[]):
        self._stock = stock
        self._option = option
        self._crypto = crypto

        for p in self._stock + self._option:
            setattr(self, p.symbol, p)
        for p in self._crypto:
            setattr(self, "c_" + p.symbol[1:], p)

    def update(self, stock=None, option=None, crypto=None):
        current_symbols = [p.symbol for p in self.all]
        self._stock = stock
        self._option = option
        self._crypto = crypto
        new_symbols = [p.symbol for p in self.all]
        for p in self._stock + self._option:
            setattr(self, p.symbol, p)
        for p in self._crypto:
            setattr(self, "_" + p.symbol, p)

        deleted_symbols = list(set(current_symbols) - set(new_symbols))
        for s in deleted_symbols:
            if symbol_type(s) == "CRYPTO":
                delattr(self, "c_" + s[1:])
            else:
                delattr(self, s)

    def get(self, symbol):
        for p in self.all:
            if p.symbol == symbol:
                return p
        return None

    @property
    def stock(self):
        return self._stock

    @property
    def option(self):
        return self._option

    @property
    def crypto(self):
        return self._crypto

    @property
    def all(self):
        return self._stock + self._option + self._crypto

    @property
    def stock_crypto(self):
        return self._stock + self._crypto

    @property
    def value(self):
        return sum(p.value for p in self.all)

    def __str__(self):
        return (
            "Positions: \n"
            + f"\tStocks : {'='.join(str(p) for p in self._stock)}\n"
            + f"\tOptions: {'='.join(str(p) for p in self._option)}\n"
            + f"\tCrypto : {'='.join(str(p) for p in self._crypto)}"
        )


class OptionPosition(Position):
    def __init__(
        self, symbol, quantity, avg_price, strike, expiration, option_type, multiplier
    ):
        super().__init__(symbol, quantity, avg_price)
        self._base_symbol = occ_to_data(symbol)[0]
        self._strike = strike
        self._expiration = expiration
        self._option_type = option_type
        self._multiplier = multiplier

    @property
    def symbol(self):
        return self._symbol.replace(" ", "")

    @property
    def base_symbol(self):
        return self._base_symbol

    @property
    def value(self):
        return self._value * self._multiplier
