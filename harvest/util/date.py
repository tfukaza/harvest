import datetime as dt
from datetime import timezone as tz
from typing import Union
from zoneinfo import ZoneInfo

import polars as pl

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


def get_local_timezone() -> ZoneInfo:
    """
    Returns a datetime timezone instance for the user's current timezone using their system time.
    """
    return dt.datetime.now(None).astimezone().tzinfo


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


def str_to_datetime(date: str, timezone: ZoneInfo = None) -> dt.datetime:
    """
    Returns a datetime object from a string.
    If timezone is not specified, the timezone is assumed to be UTC-0.
    :date: A string in the format YYYY-MM-DD hh:mm
    """
    if len(date) <= 10:
        ret = dt.datetime.strptime(date, "%Y-%m-%d")
    else:
        ret = dt.datetime.strptime(date, "%Y-%m-%d %H:%M")

    if timezone is None:
        timezone = tz.utc

    ret = ret.replace(tzinfo=timezone)
    return ret


def convert_input_to_datetime(datetime: Union[str, dt.datetime], timezone: ZoneInfo = None, no_tz=False) -> dt.datetime:
    """
    Converts the input to a datetime object with a UTC timezone.
    If the datetime object does not have a timezone, sets the
    datetime object's timezone to the given timezone and then
    covert it to UTC. If timezone is None then the system's local
    timezone is used.
    """

    if timezone is None:
        timezone = get_local_timezone()

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
        datetime = datetime.replace(tzinfo=timezone)

    datetime = datetime.astimezone(tz.utc)
    return datetime


def has_timezone(date: dt.datetime) -> bool:
    return date.tzinfo is not None and date.tzinfo.utcoffset(date) is not None


def pandas_timestamp_to_local(df: pl.DataFrame, timezone: ZoneInfo) -> pl.DataFrame:
    """
    Converts the timestamp column of a polars DataFrame to a timezone naive DateTime object in local time.
    """
    return df.with_columns(
        pl.col("timestamp").dt.convert_time_zone(str(timezone)).dt.replace_time_zone(None)
    )


def pandas_datetime_to_utc(df: pl.DataFrame, timezone: ZoneInfo) -> pl.DataFrame:
    """
    Converts timezone naive datetime column of polars dataframes to a timezone aware datetime column
    adjusted to UTC timezone.
    """
    return df.with_columns(
        pl.col("timestamp").dt.replace_time_zone(str(timezone)).dt.convert_time_zone("UTC")
    )


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
