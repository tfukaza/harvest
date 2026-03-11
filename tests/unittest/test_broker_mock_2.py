import datetime as dt
from zoneinfo import ZoneInfo

# import polars as pl
from harvest.broker.mock import MockBroker
from harvest.enum import Interval


def test_mock_broker_setup():
    """
    Test mock broker setup:
    - RuntimeData is set correctly to the specified current time
    - RuntimeData is set correctly to the specified timezone
    """
    broker = MockBroker(
        current_time=dt.datetime(2008, 9, 15, 0, 0, 0, tzinfo=dt.timezone.utc),
        epoch=dt.datetime(2007, 1, 1, 0, 0, 0, tzinfo=dt.timezone.utc),
    )
    assert broker.stats.utc_timestamp == dt.datetime(2008, 9, 15, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert broker.stats.broker_timezone == ZoneInfo("UTC")
    assert broker.epoch == dt.datetime(2007, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC"))


def test_mock_broker_mock_history_timestamp():
    """
    Test mock broker generate_price_history.
    This is a basic test to see of the price history is generated for the correct time period.
    """
    broker = MockBroker(
        epoch=dt.datetime(2008, 9, 14, 21, 25, 0, tzinfo=dt.timezone.utc),
        current_time=dt.datetime(2008, 9, 15, 10, 25, 0, tzinfo=dt.timezone.utc),
    )
    # Check that the correct interval is generated for 1 MIN interval
    df = broker.generate_history(
        symbol="SPY",
        interval=Interval.MIN_1,
    )

    assert df.columns[0] == "timestamp"
    assert df.columns[1] == "open"
    assert df.columns[2] == "high"
    assert df.columns[3] == "low"
    assert df.columns[4] == "close"
    assert df.columns[5] == "volume"

    # First timestamp is epoch
    assert df.select("timestamp").row(0)[0] == dt.datetime(2008, 9, 14, 21, 25, 0, tzinfo=dt.timezone.utc)
    # Last timestamp is 1 minute before current time
    assert df.select("timestamp").row(-1)[0] == dt.datetime(2008, 9, 15, 10, 24, 0, tzinfo=dt.timezone.utc)

    # test the 5 MIN interval
    df = broker.generate_history(
        symbol="SPY",
        interval=Interval.MIN_5,
    )

    assert df.select("timestamp").row(0)[0] == dt.datetime(2008, 9, 14, 21, 25, 0, tzinfo=dt.timezone.utc)
    assert df.select("timestamp").row(-1)[0] == dt.datetime(2008, 9, 15, 10, 20, 0, tzinfo=dt.timezone.utc)

    # test the 15MIN interval
    df = broker.generate_history(
        symbol="SPY",
        interval=Interval.MIN_15,
    )
    assert df.select("timestamp").row(0)[0] == dt.datetime(2008, 9, 14, 21, 30, 0, tzinfo=dt.timezone.utc)
    assert df.select("timestamp").row(-1)[0] == dt.datetime(2008, 9, 15, 10, 00, 0, tzinfo=dt.timezone.utc)

    # test the 30MIN interval
    df = broker.generate_history(
        symbol="SPY",
        interval=Interval.MIN_30,
    )
    assert df.select("timestamp").row(0)[0] == dt.datetime(2008, 9, 14, 21, 30, 0, tzinfo=dt.timezone.utc)
    assert df.select("timestamp").row(-1)[0] == dt.datetime(2008, 9, 15, 9, 30, 0, tzinfo=dt.timezone.utc)

    # test the 1 HOUR interval
    df = broker.generate_history(
        symbol="SPY",
        interval=Interval.HR_1,
    )
    assert df.select("timestamp").row(0)[0] == dt.datetime(2008, 9, 14, 22, 0, 0, tzinfo=dt.timezone.utc)
    assert df.select("timestamp").row(-1)[0] == dt.datetime(2008, 9, 15, 9, 0, 0, tzinfo=dt.timezone.utc)

    # test the 1 DAY interval
    broker = MockBroker(
        epoch=dt.datetime(2007, 9, 14, 21, 25, 0, tzinfo=dt.timezone.utc),
        current_time=dt.datetime(2008, 1, 15, 10, 25, 0, tzinfo=dt.timezone.utc),
    )
    df = broker.generate_history(
        symbol="SPY",
        interval=Interval.DAY_1,
    )
    assert df.select("timestamp").row(0)[0] == dt.datetime(2007, 9, 15, 0, 0, 0, tzinfo=dt.timezone.utc)
    assert df.select("timestamp").row(-1)[0] == dt.datetime(2008, 1, 14, 0, 0, 0, tzinfo=dt.timezone.utc)
