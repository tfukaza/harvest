import re
import random
import datetime as dt
from enum import IntEnum, auto

import pytz
import pandas as pd


class Interval(IntEnum):
    SEC_15 = auto()
    MIN_1 = auto()
    MIN_5 = auto()
    MIN_15 = auto()
    MIN_30 = auto()
    HR_1 = auto()
    DAY_1 = auto()


def interval_string_to_enum(str_interval):
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


def interval_enum_to_string(enum):
    try:
        name = enum.name
        unit, val = name.split("_")
        return val + unit
    except:
        return str(enum)


def is_freq(time, interval):
    """Helper function to determine if algorithm should be invoked for the
    current timestamp. For example, if interval is 30MIN,
    algorithm should be called when minutes are 0 and 30.
    """
    time = time.astimezone(pytz.timezone("UTC"))

    if interval == Interval.MIN_1:
        return True

    minutes = time.minute
    hours = time.hour
    if interval == Interval.DAY_1:
        # TODO: Use API to get real-time market hours
        return minutes == 50 and hours == 19
    elif interval == Interval.HR_1:
        return minutes == 0
    val, _ = expand_interval(interval)

    return minutes % val == 0


def expand_interval(interval: Interval):
    string = interval.name
    unit, value = string.split("_")
    return int(value), unit


def interval_to_timedelta(interval: Interval) -> dt.timedelta:
    expanded_units = {"DAY": "days", "HR": "hours", "MIN": "minutes"}
    value, unit = expand_interval(interval)
    params = {expanded_units[unit]: value}
    return dt.timedelta(**params)


def is_crypto(symbol: str) -> bool:
    return symbol[0] == "@"


def normalize_pandas_dt_index(df: pd.DataFrame) -> pd.Index:
    return df.index.floor("min")


def aggregate_df(df, interval: Interval) -> pd.DataFrame:
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
    if unit == "1HR":
        val = "H"
    elif unit == "MIN":
        val += "T"
    else:
        val = "D"
    df = df.resample(val).agg(op_dict)
    df.columns = pd.MultiIndex.from_product([[sym], df.columns])

    return df.dropna()


def now() -> dt.datetime:
    """
    Returns the current time precise to the minute in the UTC timezone
    """
    return pytz.utc.localize(dt.datetime.utcnow().replace(microsecond=0, second=0))


def epoch_zero() -> dt.datetime:
    """
    Returns a datetime object corresponding to midnight 1/1/1970 UTC
    """
    return pytz.utc.localize(dt.datetime(1970, 1, 1))


def date_to_str(day) -> str:
    return day.strftime("%Y-%m-%d")


def str_to_date(day) -> str:
    return dt.datetime.strptime(day, "%Y-%m-%d")


def mark_up(x):
    return round(x * 1.05, 2)


def mark_down(x):
    return round(x * 0.95, 2)


def has_timezone(date: dt.datetime) -> bool:
    return date.tzinfo is not None and date.tzinfo.utcoffset(date) is not None


############ Functions used for testing #################


def gen_data(symbol: str, points: int = 50) -> pd.DataFrame:
    n = now()
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
