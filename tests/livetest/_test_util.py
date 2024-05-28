import datetime as dt

"""
For testing purposes, assume:
- Current day is September 15th, 2008
- Current time is 10:00 AM
- Current timezone is US/Eastern
"""


def mock_get_local_timezone():
    """
    Return the US/Eastern timezone
    """
    return dt.timezone(dt.timedelta(hours=-4))


def mock_utc_current_time():
    """
    Return the current time in UTC timezone
    """
    d = dt.datetime(2008, 9, 15, 10, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=-4)))
    return d.astimezone(dt.timezone.utc)
