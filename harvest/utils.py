# Builtin Imports
import re
import sys
import time
import random
import logging
import datetime as dt
from typing import Any, Dict, List, Tuple, Union
from datetime import datetime, timezone as tz
from enum import IntEnum, auto
from zoneinfo import ZoneInfo

# External Imports
import pandas as pd

# Configure a logger used by all of Harvest.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s : %(name)s : %(levelname)s : %(message)s",
    datefmt="%m/%d/%Y %I:%M:%S %p",
    handlers=[logging.FileHandler("harvest.log"), logging.StreamHandler(sys.stdout)],
)
debugger = logging.getLogger("harvest")

# from rich.console import Console
# console = Console()

# # from rich.status import Status
# # status = Status()

class Timestamp:
    def __init__(self, *args) -> None:
        if len(args) == 1:
            timestamp = args[0]
            if isinstance(timestamp, str):
                self.timestamp = str_to_datetime(timestamp)
            elif isinstance(timestamp, dt.datetime):
                self.timestamp = timestamp
            else:
                raise ValueError(f"Invalid timestamp type {type(timestamp)}")
        elif len(args) > 1:
            self.timestamp = dt.datetime(*args)

    def __sub__(self, other):
        return Timerange(self.timestamp - other.timestamp)


class Timerange:
    def __init__(self, *args) -> None:
        if len(args) == 1:
            timerange = args[1]
            if isinstance(timerange, dt.timedelta):
                self.timerange = timerange
            else:
                raise ValueError(f"Invalid timestamp type {type(timerange)}")
        elif len(args) > 1:
            range_list = ["days", "hours", "minutes"]
            dict = {range_list[i]: arg for i, arg in enumerate(args)}
            self.timerange = dt.timedelta(**dict)


class Interval(IntEnum):
    SEC_15 = auto()
    MIN_1 = auto()
    MIN_5 = auto()
    MIN_15 = auto()
    MIN_30 = auto()
    HR_1 = auto()
    DAY_1 = auto()


def interval_string_to_enum(str_interval: str) -> Interval:
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
    try:
        name = enum.name
        unit, val = name.split("_")
        return val + unit
    except:
        return str(enum)


def is_freq(time: dt.datetime, interval: Interval):
    """Determine if algorithm should be invoked for the
    current time, given the interval. For example, if interval is 30MIN,
    algorithm should be called when minutes are 0 and 30, like 11:30 or 12:00.
    """
    time = time.astimezone(tz.utc)

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


def expand_interval(interval: Interval) -> Tuple[int, str]:
    """Given a IntEnum interval, returns the unit of time and the number of units."""
    string = interval.name
    unit, value = string.split("_")
    return int(value), unit


def expand_string_interval(interval: str) -> Tuple[int, str]:
    """Given a string interval, returns the unit of time and the number of units.
    For example, "3DAY" should return (3, "DAY")
    """
    num = [c for c in interval if c.isdigit()]
    value = int("".join(num))
    unit = interval[len(num) :]
    return value, unit


def interval_to_timedelta(interval: Interval) -> dt.timedelta:
    """Converts an IntEnum interval into a timedelta object of equal value."""
    expanded_units = {"DAY": "days", "HR": "hours", "MIN": "minutes"}
    value, unit = expand_interval(interval)
    params = {expanded_units[unit]: value}
    return dt.timedelta(**params)


def symbol_type(symbol: str) -> str:
    """Determines the type of the asset the symbol represents.
    This can be 'STOCK', 'CRYPTO', or 'OPTION'
    """
    if len(symbol) > 6:
        return "OPTION"
    elif symbol[0] == "@" or symbol[:2] == "c_":
        return "CRYPTO"
    else:
        return "STOCK"


def occ_to_data(symbol: str) -> Tuple[str, dt.datetime, str, float]:
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
        raise Exception(f"Error parsing OCC symbol: {original_symbol}, {e}")


def data_to_occ(symbol: str, date: dt.datetime, option_type: str, price: float) -> str:
    """
    Converts data into a OCC format string
    """
    occ = symbol  # + ((6 - len(symbol)) * " ")
    occ += date.strftime("%y%m%d")
    occ = occ + "C" if option_type == "call" else occ + "P"
    occ += f"{int(price*1000):08}"
    return occ


# =========== DataFrame utils ===========


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
    if unit == "HR":
        val = "H"
    elif unit == "MIN":
        val += "T"
    else:
        val = "D"
    df = df.resample(val).agg(op_dict)
    df.columns = pd.MultiIndex.from_product([[sym], df.columns])

    return df.dropna()


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


# ========== Date utils ==========
def now() -> dt.datetime:
    """
    Returns the current time precise to the minute in the UTC timezone
    """
    return dt.datetime.now(tz.utc).replace(microsecond=0, second=0)


def epoch_zero() -> dt.datetime:
    """
    Returns a datetime object corresponding to midnight 1/1/1970 UTC
    """
    return dt.datetime(1970, 1, 1, tzinfo=tz.utc)


def date_to_str(day: dt.date) -> str:
    return day.strftime("%Y-%m-%d")


def str_to_date(day: str) -> dt.date:
    return dt.datetime.strptime(day, "%Y-%m-%d")


def str_to_datetime(date: str) -> dt.datetime:
    """
    :date: A string in the format YYYY-MM-DD hh:mm
    """
    if len(date) <= 10:
        return dt.datetime.strptime(date, "%Y-%m-%d")
    return dt.datetime.strptime(date, "%Y-%m-%d %H:%M")


def get_local_timezone() -> ZoneInfo:
    """
    Returns a datetime timezone instance for the user's current timezone
    using their system time.
    """
    return dt.datetime.now(tz.utc).astimezone().tzinfo


def convert_input_to_datetime(
    datetime: Union[str, dt.datetime], timezone: ZoneInfo = None
) -> dt.datetime:
    """
    Converts the input to a datetime object with a UTC timezone.
    If the datetime object does not have a timezone sets the
    datetime object's timezone to the given timezone and then
    covert it to UTC. If timezone is None then the system's local
    timezone is used.
    """
    if datetime is None:
        return None
    elif isinstance(datetime, str):
        datetime = dt.datetime.fromisoformat(datetime)
    elif not isinstance(datetime, dt.datetime):
        raise ValueError(f"Cannot convert {datetime} to datetime.")

    if not has_timezone(datetime):
        if timezone is not None:
            timezone = get_local_timezone()
        datetime = datetime.replace(tzinfo=timezone)

    datetime = datetime.astimezone(tz.utc)
    return datetime


def convert_input_to_timedelta(
    period: Union[Timerange, str, dt.timedelta]
) -> dt.timedelta:
    """Converts period into a timedelta object.
    Period can be a string, timedelta object, or a Timerange object."""
    if period is None:
        return None
    elif isinstance(period, Timerange):
        return period.timerange
    elif isinstance(period, str):
        expanded_units = {"DAY": "days", "HR": "hours", "MIN": "minutes"}
        val, unit = expand_string_interval(period)
        return dt.timedelta(**{expanded_units[unit]: val})
    elif isinstance(period, dt.timedelta):
        return period
    else:
        raise ValueError(f"Cannot convert {period} to timedelta.")


def has_timezone(date: dt.datetime) -> bool:
    return date.tzinfo is not None and date.tzinfo.utcoffset(date) is not None


def pandas_timestamp_to_local(df: pd.DataFrame, timezone: ZoneInfo) -> pd.DataFrame:
    """
    Converts the timestamp of a Pandas dataframe to a timezone naive DateTime object in local time.
    """
    df.index = pd.DatetimeIndex(
        map(
            lambda x: x.astimezone(timezone).replace(tzinfo=None),
            df.index.to_pydatetime(),
        )
    )
    return df


def pandas_datetime_to_utc(df: pd.DataFrame, timezone: ZoneInfo) -> pd.DataFrame:
    """
    Converts timezone naive datetime index of dataframes to a timezone aware datetime index
    adjusted to UTC timezone.
    """
    df.index = df.index.map(lambda x: x.replace(tzinfo=timezone).astimezone(tz.utc))
    return df


def datetime_utc_to_local(date_time: dt.datetime, timezone: ZoneInfo) -> dt.datetime:
    """
    Converts a datetime object in UTC to local time, represented as a
    timezone naive datetime object.
    """
    # If date_time is a Dataframe timestamp, we must first convert to a normal Datetime object
    if not isinstance(date_time, dt.datetime):
        date_time = date_time.to_pydatetime()

    new_tz = date_time.astimezone(timezone)
    return new_tz.replace(tzinfo=None)


# ========== Misc. utils ==========
def mark_up(x: float) -> float:
    return round(x * 1.05, 2)


def mark_down(x: float) -> float:
    return round(x * 0.95, 2)


def is_crypto(symbol: str) -> bool:
    return symbol_type(symbol) == "CRYPTO"


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
