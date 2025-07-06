import datetime as dt
from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import Any, Iterator, List
from zoneinfo import ZoneInfo

import polars as pl


class AssetType(StrEnum):
    STOCK = "stock"
    OPTION = "option"
    CRYPTO = "cryptocurrency"


class Interval(StrEnum):
    MIN_1 = "1min"
    MIN_5 = "5min"
    MIN_15 = "15min"
    MIN_30 = "30min"
    HOUR_1 = "1hour"
    DAY_1 = "1day"


class TimeSpan(StrEnum):
    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"


class TimeDelta:
    def __init__(self, unit: TimeSpan, value: int):
        self.unit = unit
        self.value = value

    def __str__(self) -> str:
        return f"{self.value} {self.unit}"

    @property
    def delta_datetime(self) -> dt.timedelta:
        if self.unit == TimeSpan.MINUTE:
            return dt.timedelta(minutes=self.value)
        elif self.unit == TimeSpan.HOUR:
            return dt.timedelta(hours=self.value)
        elif self.unit == TimeSpan.DAY:
            return dt.timedelta(days=self.value)
        elif self.unit == TimeSpan.WEEK:
            return dt.timedelta(weeks=self.value)
        else:
            raise ValueError(f"Invalid time span unit: {self.unit}")


@dataclass
class RuntimeData:
    broker_timezone: ZoneInfo
    utc_timestamp: dt.datetime

    def __str__(self) -> str:
        return f"Timestamp: {self.utc_timestamp}\nTimezone: {self.broker_timezone}"

    @property
    def broker_timestamp(self) -> dt.datetime:
        return self.utc_timestamp.astimezone(self.broker_timezone)


class OrderTimeInForce(str, Enum):
    GTC = "gtc"
    GTD = "gtd"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    OPEN = "open"
    FILLED = "filled"


class OrderEvent(str, Enum):
    ORDER = "ORDER"
    FILL = "FILL"


@dataclass
class Order:
    order_type: AssetType
    symbol: str
    quantity: float
    time_in_force: OrderTimeInForce
    side: OrderSide
    order_id: Any
    status: OrderStatus = OrderStatus.OPEN
    filled_time: dt.datetime | None = None
    filled_price: float | None = None
    filled_quantity: float | None = None
    base_symbol: str | None = None

    def __str__(self) -> str:
        return f"""
        order_id:       {self.order_id}
        symbol:         {self.symbol}
        type:           {self.order_type}
        side:           {self.side}
        quantity:       {self.quantity}
        time_in_force:  {self.time_in_force}
        status:         {self.status}
        filled_time:    {self.filled_time}
        filled_price:   {self.filled_price}
        filled_quantity:{self.filled_quantity}

        """

    # def update(self, val: Dict[str, Any]) -> None:
    #     self._filled_quantity = val["quantity"]
    #     self._status = val["status"]
    #     self._filled_price = val["filled_price"]
    #     self._filled_time = val["filled_time"]


@dataclass
class OrderList:
    orders: dict[str, Order]

    def __str__(self) -> str:
        return "\n".join(str(order) for order in self.orders)

    def __getitem__(self, key: str) -> Order | None:
        return self.orders.get(key, None)

    def __setitem__(self, key: str, value: Order) -> None:
        self.orders[key] = value

    def __contains__(self, key: str) -> bool:
        return key in self.orders

    def __iter__(self) -> Iterator[Order]:
        return iter(self.orders.values())

    def __len__(self) -> int:
        return len(self.orders)

    def add_order(self, order: Order) -> None:
        self.orders[order.order_id] = order

    def remove_filled_orders(self) -> None:
        for order_id in list(self.orders.keys()):
            if self.orders[order_id].status == OrderStatus.FILLED:
                del self.orders[order_id]

    @property
    def symbols(self) -> List[str]:
        return [o.symbol for o in self.orders.values()]


@dataclass
class Position:
    symbol: str
    quantity: float
    avg_price: float
    value: float = 0
    profit: float = 0
    profit_percent: float = 0
    _current_price: float = 0

    # Warning: These perform local calculations that may deviate from the actual values
    # in the broker's database.
    @property
    def current_price(self) -> float:
        return self._current_price

    @current_price.setter
    def current_price(self, value: float) -> None:
        self._current_price = value
        self.value = self._current_price * self.quantity
        self.profit = self.value - self.avg_price * self.quantity
        self.profit_percent = self.profit / (self.avg_price * self.quantity)

    def apply_order(self, order: Order) -> None:
        if order.status != OrderStatus.FILLED:
            raise ValueError(f"Order {order.order_id} is not filled")
        if order.side == OrderSide.BUY:
            self.buy(order.quantity, order.filled_price)
        else:
            self.sell(order.quantity, order.filled_price)

    def buy(self, quantity, price):
        self.avg_price = (self.avg_price * self.quantity + price * quantity) / (self.quantity + quantity)
        self.quantity += quantity

    def sell(self, quantity, price):
        self.quantity -= quantity

    def __str__(self):
        return (
            f"\n[{self.symbol}]\n"
            + f" Quantity:\t{self.quantity}\n"
            + f" Avg. Cost:\t${self.avg_price}\n"
            + f" Price:  \t${self.current_price}\n"
            + f" Value:  \t${self.value}\n"
            + f" Profit:\t${self.profit}\n"
            + f" Returns:\t{'▲' if self.profit_percent > 0 else '▼'}{self.profit_percent * 100}%\n"
            + "─" * 50
        )


OPTION_QTY_MULTIPLIER = 100


@dataclass(kw_only=True)
class OptionPosition(Position):
    base_symbol: str
    strike: float
    expiration: dt.datetime
    option_type: str
    multiplier: float = OPTION_QTY_MULTIPLIER


def symbol_type(symbol: str) -> AssetType:
    if symbol.startswith("@"):
        return AssetType.CRYPTO
    elif len(symbol) > 6:
        return AssetType.OPTION
    else:
        return AssetType.STOCK


@dataclass
class Positions:
    positions: dict[str, Position]

    def __init__(self, positions: dict[str, Position]):
        self.positions = positions

    def __getitem__(self, key: str) -> Position | None:
        return self.positions.get(key, None)

    def __setitem__(self, key: str, value: Position) -> None:
        self.positions[key] = value

    def add_position(self, value: Position) -> None:
        self.positions[value.symbol] = value

    @property
    def stock(self) -> List[Position]:
        return [p for p in self.positions.values() if symbol_type(p.symbol) == AssetType.STOCK]

    @property
    def option(self) -> List[Position]:
        return [p for p in self.positions.values() if symbol_type(p.symbol) == AssetType.OPTION]

    @property
    def crypto(self) -> List[Position]:
        return [p for p in self.positions.values() if symbol_type(p.symbol) == AssetType.CRYPTO]

    @property
    def all(self) -> List[Position]:
        return list(self.positions.values())

    def __str__(self):
        return (
            "Positions: \n"
            + f"\tStocks : {'='.join(str(p) for p in self.stock)}\n"
            + f"\tOptions: {'='.join(str(p) for p in self.option)}\n"
            + f"\tCrypto : {'='.join(str(p) for p in self.crypto)}"
        )


@dataclass
class Account:
    """
    Maintains account data for the broker.
    """

    account_name: str
    positions: Positions
    orders: OrderList
    asset_value: float
    cash: float
    equity: float
    buying_power: float
    multiplier: float

    def __str__(self) -> str:
        return (
            f"Account:\t{self.account_name}\n"
            + f"Cash:\t{self.cash}\n"
            + f"Equity:\t{self.equity}\n"
            + f"Buying Power:\t{self.buying_power}\n"
            + f"Multiplier:\t{self.multiplier}\n\n"
            + f"Positions:\n{self.positions}\n\n"
            + f"Orders:\n{self.orders}"
        )


@dataclass
class TickerCandle:
    timestamp: dt.datetime
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, TickerCandle):
            return False
        return (
            self.timestamp == value.timestamp
            and self.symbol == value.symbol
            and self.open == value.open
            and self.high == value.high
            and self.low == value.low
            and self.close == value.close
            and self.volume == value.volume
        )


class TickerFrame:
    """
    A wrapper around a polars dataframe to provide type hints and additional functionality.
    """

    _df: pl.DataFrame

    def __init__(self, df: pl.DataFrame):
        self._df = df

    @property
    def df(self) -> pl.DataFrame:
        return self._df

    def __getitem__(self, index: int) -> TickerCandle:
        if index < 0:
            index = len(self._df) + index
        df = self._df.row(index, named=True)
        data = {
            "timestamp": df["timestamp"],
            "symbol": df["symbol"],
            "open": df["open"],
            "high": df["high"],
            "low": df["low"],
            "close": df["close"],
            "volume": df["volume"],
        }
        return TickerCandle(**data)


@dataclass
class Transaction:
    timestamp: dt.datetime
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    event: OrderEvent
    algorithm_name: str


class TransactionFrame:
    _df: pl.DataFrame

    def __init__(self, df: pl.DataFrame):
        self._df = df

    @property
    def df(self) -> pl.DataFrame:
        return self._df

    def __getitem__(self, index: int) -> Transaction:
        df = self._df.row(index, named=True)
        data = {
            "timestamp": df["timestamp"],
            "symbol": df["symbol"],
            "side": df["side"],
            "quantity": df["quantity"],
            "price": df["price"],
            "event": df["event"],
            "algorithm_name": df["algorithm_name"],
        }
        return Transaction(**data)


@dataclass
class ChainInfo:
    chain_id: str
    expiration_list: list[dt.date]


class ChainData:
    _df: pl.DataFrame

    def __init__(self, df: pl.DataFrame):
        self._df = df


@dataclass
class OptionData:
    symbol: str
    price: float
    ask: float
    bid: float
    expiration: dt.datetime
    strike: float
