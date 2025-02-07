import datetime as dt
import logging
import random
import re
import sys
from datetime import timezone as tz
from typing import List, Tuple, Union

import pandas as pd
import polars as pl

from harvest.definitions import TickerFrame
from harvest.enum import BrokerType, DataBrokerType, Interval, IntervalUnit, StorageType, TimeRange, TradeBrokerType
from harvest.util.date import utc_current_time

# Configure a logger used by all of Harvest.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s : %(name)s : %(levelname)s : %(message)s",
    datefmt="%m/%d/%Y %I:%M:%S %p",
    handlers=[logging.FileHandler("harvest.log"), logging.StreamHandler(sys.stdout)],
)
debugger = logging.getLogger("harvest")


def interval_string_to_enum(str_interval: str) -> Interval:
    """
    Converts an interval string to an Interval IntEnum.
    """
    if str_interval == "15SEC":
        return Interval.SEC_15
    elif str_interval == "1MIN":
        return Interval.MIN_1
    elif str_interval == "5MIN":
        return Interval.MIN_5
    elif str_interval == "15MIN":
        return Interval.MIN_15
    elif str_interval == "30MIN":
        return Interval.MIN_30
    elif str_interval == "1HR":
        return Interval.HR_1
    elif str_interval == "1DAY":
        return Interval.DAY_1
    else:
        raise ValueError(f"Invalid interval string {str_interval}")


def interval_enum_to_string(enum: Interval) -> str:
    """
    Converts an Interval enum to string.
    """
    try:
        name = enum.name
        unit, val = name.split("_")
        return val + unit
    except ValueError:
        return str(enum)


def check_interval(time: dt.datetime, interval: Interval):
    """
    Determine if algorithm should be invoked for the
    current time, given the interval. For example, if interval is 30MIN,
    algorithm should be called when minutes are 0 and 30, like 11:30 or 12:00.

    :time: The current time
    :interval: The interval to check the time against
    """

    time = time.astimezone(tz.utc)  # Adjust to UTC timezone

    if interval == Interval.MIN_1:
        return True

    minutes = time.minute
    hours = time.hour
    if interval == Interval.DAY_1:
        # For now, assume market closes at 19:50 UTC
        # TODO: Use API to get real-time market hours
        return minutes == 50 and hours == 19
    elif interval == Interval.HR_1:
        return minutes == 0

    val, _ = expand_interval(interval)
    return minutes % val == 0


def applicable_intervals_for_time(time: dt.datetime) -> List[Interval]:
    """
    Returns a list of intervals that are applicable for the given time.
    For example, 11:45 UTC is applicable for 1MIN, 5MIN and 15MIN, but not 30MIN, 1HR, or 1DAY.
    """
    time = time.astimezone(tz.utc)
    minute = time.minute
    hour = time.hour

    applicable_intervals = [Interval.MIN_1]
    if minute % 5 == 0:
        applicable_intervals.append(Interval.MIN_5)
    if minute % 15 == 0:
        applicable_intervals.append(Interval.MIN_15)
    if minute % 30 == 0:
        applicable_intervals.append(Interval.MIN_30)
    if minute == 0:
        applicable_intervals.append(Interval.HR_1)
    if hour == 0 and minute == 0:
        applicable_intervals.append(Interval.DAY_1)
    return applicable_intervals


def expand_interval(interval: Interval) -> Tuple[int, str]:
    """
    Given a IntEnum interval, returns the unit of time and the number of units.
    """
    string = interval.name
    unit, value = string.split("_")
    return int(value), unit


def expand_string_interval(interval: str) -> Tuple[int, str]:
    """
    Given a string interval, returns the unit of time and the number of units.
    For example, "3DAY" should return (3, "DAY")
    """
    num = [c for c in interval if c.isdigit()]
    value = int("".join(num))
    unit = interval[len(num) :]
    return value, unit


def interval_to_timedelta(interval: Interval) -> dt.timedelta:
    """
    Converts an IntEnum interval into a timedelta object of equal value.
    """
    expanded_units = {"DAY": "days", "HR": "hours", "MIN": "minutes", "SEC": "seconds"}
    value, unit = expand_interval(interval)
    params = {expanded_units[unit]: value}
    return dt.timedelta(**params)


def symbol_type(symbol: str) -> str:
    """
    Determines the type of the asset the symbol represents.
    This can be 'STOCK', 'CRYPTO', or 'OPTION'
    """
    if len(symbol) > 6:
        return "OPTION"
    elif symbol[0] == "@" or symbol[:2] == "c_":
        return "CRYPTO"
    else:
        return "STOCK"


def occ_to_data(symbol: str) -> Tuple[str, dt.datetime, str, float]:
    """
    Converts options OCC symbol to data.
    For example, "AAPL  210319C00123000" should return ("AAPL", dt.datetime(2021, 3, 19), "call", 123)
    """
    original_symbol = symbol
    try:
        symbol = symbol.replace(" ", "")
        i = re.search(r"[^A-Z ]", symbol).start()
        sym = symbol[:i]
        symbol = symbol[i:]
        date = dt.datetime.strptime(symbol[:6], "%y%m%d")
        option_type = "call" if symbol[6] == "C" else "put"
        price = float(symbol[7:]) / 1000

        return sym, date, option_type, price
    except Exception as e:
        debugger.error(f"Error parsing OCC symbol: {original_symbol}, {e}")


def data_to_occ(symbol: str, date: dt.datetime, option_type: str, price: float) -> str:
    """
    Converts data into a OCC format string
    """
    occ = symbol  # + ((6 - len(symbol)) * " ")
    occ += date.strftime("%y%m%d")
    occ = occ + "C" if option_type == "call" else occ + "P"
    occ += f"{int(price*1000):08}"
    return occ


def convert_input_to_timedelta(period: Union[TimeRange, str, dt.timedelta]) -> dt.timedelta:
    """
    Converts period into a timedelta object.
    Period can be a string, timedelta object, or a TimeRange object.
    """
    if period is None:
        return None
    elif isinstance(period, TimeRange):
        return period.timerange
    elif isinstance(period, str):
        expanded_units = {"DAY": "days", "HR": "hours", "MIN": "minutes"}
        val, unit = expand_string_interval(period)
        return dt.timedelta(**{expanded_units[unit]: val})
    elif isinstance(period, dt.timedelta):
        return period
    else:
        raise ValueError(f"Cannot convert {period} to timedelta.")


def str_to_data_broker_type(name: str) -> DataBrokerType:
    """
    Converts a string to a DataBrokerType enum.
    """
    if name == "dummy":
        return DataBrokerType.DUMMY
    elif name == "yahoo":
        return DataBrokerType.YAHOO
    elif name == "polygon":
        return DataBrokerType.POLYGON
    elif name == "robinhood":
        return DataBrokerType.ROBINHOOD
    elif name == "alpaca":
        return DataBrokerType.ALPACA
    elif name == "webull":
        return DataBrokerType.WEBULL
    else:
        raise ValueError(f"Invalid DataBrokerType {name}")


def str_to_trade_broker_type(name: str) -> TradeBrokerType:
    """
    Converts a string to a TradeBrokerType enum.
    """
    if name == "paper":
        return TradeBrokerType.PAPER
    elif name == "robinhood":
        return TradeBrokerType.ROBINHOOD
    elif name == "alpaca":
        return TradeBrokerType.ALPACA
    elif name == "webull":
        return TradeBrokerType.WEBULL
    else:
        raise ValueError(f"Invalid TradeBrokerType {name}")


def str_to_broker_type(name: str) -> BrokerType:
    """
    Converts a string to a BrokerType enum.
    """
    if name == "dummy":
        return BrokerType.DUMMY
    elif name == "yahoo":
        return BrokerType.YAHOO
    elif name == "polygon":
        return BrokerType.POLYGON
    elif name == "robinhood":
        return BrokerType.ROBINHOOD
    elif name == "alpaca":
        return BrokerType.ALPACA
    elif name == "webull":
        return BrokerType.WEBULL
    elif name == "paper":
        return BrokerType.PAPER
    else:
        raise ValueError(f"Invalid BrokerType {name}")


def str_to_storage_type(name: str) -> StorageType:
    """
    Converts a string to a StorageType enum.
    """
    if name == "base":
        return StorageType.BASE
    elif name == "csv":
        return StorageType.CSV
    elif name == "pickle":
        return StorageType.PICKLE
    elif name == "db":
        return StorageType.DB
    else:
        raise ValueError(f"Invalid StorageType {name}")


# =========== DataFrame utils ===========


def normalize_pandas_dt_index(df: pd.DataFrame) -> pd.Index:
    return df.index.floor("min")


def aggregate_df(df, interval: Interval) -> pd.DataFrame:
    """
    Aggregate the dataframe data points to the given interval.
    """
    sym = df.columns[0][0]
    df = df[sym]
    op_dict = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    val, unit = expand_interval(interval)
    val = str(val)
    if unit == "HR":
        val = "H"
    elif unit == "MIN":
        val += "min"
    else:
        val = "D"
    df = df.resample(val).agg(op_dict)
    df.columns = pd.MultiIndex.from_product([[sym], df.columns])

    return df.dropna()


def aggregate_pl_df(df, interval: Interval) -> pl.DataFrame:
    """
    Aggregate the dataframe data points to the given interval.
    """
    # symbol = df.columns[0]
    # df = df.filter(pl.col("symbol") == symbol)
    # df = df.group_by_dynamic("timestamp", every=interval_to_timedelta(interval)).agg(
    #     pl.col("open").first(),
    #     pl.col("high").max(),
    #     pl.col("low").min(),
    #     pl.col("close").last(),
    #     pl.col("volume").sum(),
    # )
    df = df.group_by_dynamic("timestamp", every=interval_to_timedelta(interval)).agg(pl.col("price").last())
    return df


def floor_trim_df(df, base_interval: Interval, agg_interval: Interval):
    """
    This function takes a dataframe, and trims off rows
    from the beginning so that the timestamp of the first row is a multiple of agg_interval
    """
    val, _ = expand_interval(base_interval)

    y = None

    def f(x):
        nonlocal y
        if y is None:
            y = x
        r = x.date() != y.date()
        y = x
        return r

    if agg_interval == Interval.MIN_5:
        g = lambda x: (x.minute - val) % 5 == 0
    elif agg_interval == Interval.MIN_15:
        g = lambda x: (x.minute - val) % 15 == 0
    elif agg_interval == Interval.MIN_30:
        g = lambda x: (x.minute - val) % 30 == 0
    elif agg_interval == Interval.HR_1:
        g = lambda x: (x.minute - val) % 60 == 0
    elif agg_interval == Interval.DAY_1:
        g = f
    else:
        raise Exception("Unsupported interval")

    # Get the index of the first row that satisfies the condition g
    for i in range(len(df)):
        if g(df.index[i]):
            return df.index[i]
    return df.index[0]


# ========== Misc. utils ==========
def mark_up(x: float) -> float:
    return round(x * 1.05, 2)


def mark_down(x: float) -> float:
    return round(x * 0.95, 2)


def is_crypto(symbol: str) -> bool:
    return symbol_type(symbol) == "CRYPTO"


############ Functions used for testing #################


def gen_data(symbol: str, points: int = 50) -> pd.DataFrame:
    n = utc_current_time()
    index = [n - dt.timedelta(minutes=1) * i for i in range(points)][::-1]
    df = pd.DataFrame(index=index, columns=["low", "high", "close", "open", "volume"])
    df.index.rename("timestamp", inplace=True)
    df["low"] = [random.random() for _ in range(points)]
    df["high"] = [random.random() for _ in range(points)]
    df["close"] = [random.random() for _ in range(points)]
    df["open"] = [random.random() for _ in range(points)]
    df["volume"] = [random.random() for _ in range(points)]
    # df.index = normalize_pandas_dt_index(df)
    df.columns = pd.MultiIndex.from_product([[symbol], df.columns])

    return df


def generate_ticker_frame(
    symbol: str,
    interval: Interval,
    count: int = 50,
    start: dt.datetime | None = None,
) -> TickerFrame:
    if start is None:
        start = dt.datetime(1970, 1, 1)

    delta_param = {}
    if interval.unit == IntervalUnit.MIN:
        delta_param["minutes"] = interval.interval_value
    elif interval.unit == IntervalUnit.HR:
        delta_param["hours"] = interval.interval_value
    elif interval.unit == IntervalUnit.DAY:
        delta_param["days"] = interval.interval_value

    df = pl.DataFrame(
        {
            "timestamp": [start + dt.timedelta(**delta_param) * i for i in range(count)],
            "symbol": [symbol] * count,
            "interval": [str(interval)] * count,
            "open": [random.random() for _ in range(count)],
            "high": [random.random() for _ in range(count)],
            "low": [random.random() for _ in range(count)],
            "close": [random.random() for _ in range(count)],
            "volume": [random.random() for _ in range(count)],
        }
    )

    return TickerFrame(df)
