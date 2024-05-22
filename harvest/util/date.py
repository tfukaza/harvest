import datetime as dt
from datetime import timezone as tz
from typing import Union
from zoneinfo import ZoneInfo

import pandas as pd

# ========== Date utils ==========


def utc_current_time() -> dt.datetime:
    """
    Returns the current time precise to the minute in the UTC timezone
    """
    return dt.datetime.now(tz.utc).replace(microsecond=0, second=0)


def utc_epoch_zero() -> dt.datetime:
    """
    Returns a datetime object corresponding to midnight 1/1/1970 UTC
    """
    return dt.datetime(1970, 1, 1, tzinfo=tz.utc)


def date_to_str(day: dt.date) -> str:
    """
    Returns a string representation of the date in the format YYYY-MM-DD
    """
    return day.strftime("%Y-%m-%d")


def str_to_date(day: str) -> dt.date:
    """
    Returns a date object from a string.
    :day: A string in the format YYYY-MM-DD
    """
    return dt.datetime.strptime(day, "%Y-%m-%d")


def str_to_datetime(date: str) -> dt.datetime:
    """
    Returns a datetime object from a string.
    :date: A string in the format YYYY-MM-DD hh:mm
    """
    if len(date) <= 10:
        return dt.datetime.strptime(date, "%Y-%m-%d")
    return dt.datetime.strptime(date, "%Y-%m-%d %H:%M")


def get_local_timezone() -> ZoneInfo:
    """
    Returns a datetime timezone instance for the user's current timezone using their system time.
    """
    return dt.datetime.now(tz.utc).astimezone().tzinfo


def convert_input_to_datetime(datetime: Union[str, dt.datetime], timezone: ZoneInfo = None, no_tz=False) -> dt.datetime:
    """
    Converts the input to a datetime object with a UTC timezone.
    If the datetime object does not have a timezone, sets the
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

    if no_tz:
        if has_timezone(datetime):
            datetime = datetime.replace(tzinfo=None)
        return datetime

    if not has_timezone(datetime):
        if timezone is None:
            timezone = get_local_timezone()
        datetime = datetime.replace(tzinfo=timezone)

    datetime = datetime.astimezone(tz.utc)
    return datetime


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
