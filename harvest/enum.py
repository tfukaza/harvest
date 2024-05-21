import datetime as dt
from enum import Enum, IntEnum, auto

from harvest.util.date import str_to_datetime


class Interval(IntEnum):
    SEC_15 = auto()
    MIN_1 = auto()
    MIN_5 = auto()
    MIN_15 = auto()
    MIN_30 = auto()
    HR_1 = auto()
    DAY_1 = auto()


class EnumList(Enum):
    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class DataBrokerType(EnumList):
    DUMMY = "dummy"
    YAHOO = "yahoo"
    POLYGON = "polygon"
    ROBINHOOD = "robinhood"
    ALPACA = "alpaca"
    WEBULL = "webull"


class TradeBrokerType(EnumList):
    PAPER = "paper"
    ROBINHOOD = "robinhood"
    ALPACA = "alpaca"
    WEBULL = "webull"


class BrokerType(EnumList):
    # Combine both DataBrokerType and TradeBrokerType
    DUMMY = "dummy"
    YAHOO = "yahoo"
    POLYGON = "polygon"
    ROBINHOOD = "robinhood"
    ALPACA = "alpaca"
    WEBULL = "webull"
    PAPER = "paper"
    BASE_STREAMER = "base_streamer"


class StorageType(EnumList):
    BASE = "base"
    CSV = "csv"
    PICKLE = "pickle"
    DB = "db"


class Timestamp:
    """
    A class that represents a timestamp. It can be initialized with a string or a datetime object.
    If using a string, it must be in the format "YYYY-MM-DD hh:mm".
    If using a datetime object either:
    - Pass in a datetime object
    - Pass in a series of integers that represent the year, month, day, hour, minute, second, and microsecond.
    """

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
        return TimeRange(self.timestamp - other.timestamp)


class TimeRange:
    """
    A wrapper around a timedelta object that represents a range of time.
    It can be initialized with a timedelta object or a series of integers that represent the number of days, hours, and minutes.
    """

    def __init__(self, *args) -> None:
        if len(args) == 1:
            timerange = args[1]
            if isinstance(timerange, dt.timedelta):
                self.timerange = timerange
            else:
                raise ValueError(f"Invalid timestamp type {type(timerange)}")
        elif len(args) > 1:
            range_list = ["days", "hours", "minutes"]
            range_dict = {range_list[i]: arg for i, arg in enumerate(args)}
            self.timerange = dt.timedelta(**range_dict)
