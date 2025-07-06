import datetime as dt
from enum import Enum, StrEnum

from harvest.util.date import str_to_datetime


class IntervalUnit(StrEnum):
    SEC = "SEC"
    MIN = "MIN"
    HR = "HR"
    DAY = "DAY"


class Interval(int, Enum):
    unit: IntervalUnit
    interval_value: int

    def __new__(cls, value, unit, interval_value):
        obj = int.__new__(cls)
        obj._value_ = value
        obj.unit = unit
        obj.interval_value = interval_value
        return obj

    def __str__(self) -> str:
        return f"{self.unit.name}_{self.interval_value}"

    def __hash__(self) -> int:
        return hash(self._value_)

    def __eq__(self, other) -> bool:
        return self._value_ == other._value_

    def __ne__(self, other) -> bool:
        return not self.__eq__(other)

    def __lt__(self, other) -> bool:
        return self._value_ < other._value_

    def __le__(self, other) -> bool:
        return self._value_ <= other._value_

    def __gt__(self, other) -> bool:
        return self._value_ > other._value_

    def __ge__(self, other) -> bool:
        return self._value_ >= other._value_

    @staticmethod
    def from_str(interval: str) -> "Interval":
        # value, interval_value, unit = interval.split("_")
        # return Interval(int(value), IntervalUnit(unit), int(interval_value))
        match interval:
            case "SEC_15":
                return Interval.SEC_15
            case "MIN_1":
                return Interval.MIN_1
            case "MIN_5":
                return Interval.MIN_5
            case "MIN_15":
                return Interval.MIN_15
            case "MIN_30":
                return Interval.MIN_30
            case "HR_1":
                return Interval.HR_1
            case "DAY_1":
                return Interval.DAY_1
            case _:
                raise ValueError(f"Invalid interval {interval}")

    SEC_15 = (0, IntervalUnit.SEC, 15)
    MIN_1 = (1, IntervalUnit.MIN, 1)
    MIN_5 = (2, IntervalUnit.MIN, 5)
    MIN_15 = (3, IntervalUnit.MIN, 15)
    MIN_30 = (4, IntervalUnit.MIN, 30)
    HR_1 = (5, IntervalUnit.HR, 1)
    DAY_1 = (6, IntervalUnit.DAY, 1)


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
