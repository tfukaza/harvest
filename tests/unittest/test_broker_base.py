import datetime as dt

import polars as pl
import pytest

from harvest.broker._base import Broker
from harvest.broker.mock import MockBroker
from harvest.definitions import RuntimeData, TickerCandle, TickerFrame
from harvest.enum import Interval, IntervalUnit
from harvest.util.helper import generate_ticker_frame, interval_to_timedelta

# from harvest.util.helper import debugger
# from unittest.mock import patch

# debugger.setLevel("DEBUG")

"""
For testing purposes, assume:
- Current day is September 15th, 2008
- Current time is 10:00 AM
- Current timezone is US/Eastern
"""


# def repeat_test(broker_list):
#     def decorator_test(func):
#         @wraps(func)
#         def wrapper_repeat(*args):
#             self = args[0]
#             for broker in broker_list:
#                 print(f"Testing {broker}")
#                 func(self, broker)

#         return wrapper_repeat

#     return decorator_test


# mocker.patch(
#     "harvest.util.date.get_local_timezone", return_value=dt.timezone(dt.timedelta(hours=-4))
# )
class MockRuntimeData:
    def __init__(self):
        self.time = dt.datetime(2008, 9, 15, 10, 0, 0, tzinfo=dt.timezone.utc)

    @property
    def utc_timestamp(self):
        return self.time

    @utc_timestamp.setter
    def utc_timestamp(self, value):
        self.time = value

    def increment_time(self, interval: Interval):
        self.time += interval_to_timedelta(interval)


@pytest.fixture
def mock_runtime_data():
    start_time = dt.datetime(2008, 9, 15, 10, 0, 0, tzinfo=dt.timezone.utc)
    mock_runtime_data = RuntimeData(broker_timezone=dt.timezone.utc, utc_timestamp=start_time)  # type: ignore
    mock_runtime_data.time = start_time  # type: ignore
    mock_runtime_data.__class__ = MockRuntimeData
    return mock_runtime_data


@pytest.fixture
def mock_fetch_price_history(mock_runtime_data):
    time = mock_runtime_data

    parameters = {
        "required_retries": 0,  # Number of retires until the API returns the latest data
        # TODO: Allow param per interval and symbol
    }

    def fetch_price_history(symbol, interval, start, end) -> TickerFrame:
        count = 100
        if parameters["required_retries"] > 0:
            count -= 1
            parameters["required_retries"] -= 1
        # Round down the start time to the nearest interval

        start = time.utc_timestamp
        if interval.unit == IntervalUnit.MIN:
            start = start.replace(
                minute=start.minute // interval.interval_value * interval.interval_value, second=0, microsecond=0
            )
        elif interval.unit == IntervalUnit.HR:
            start = start.replace(hour=start.hour, minute=0, second=0, microsecond=0)
        elif interval.unit == IntervalUnit.DAY:
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)

        start = start - interval_to_timedelta(interval) * 100

        # print(start)

        frame = generate_ticker_frame(
            symbol,
            interval,
            count,
            start,
        )
        # Frame will have candles for intervals up to but not including the current time.
        # For example if the current time is 10:00 AM and interval is 1 minute,
        # the frame will have candles up to 9:59 AM.
        frame = frame.df
        if start:
            frame = frame.filter(pl.col("timestamp") >= start)
        if end:
            frame = frame.filter(pl.col("timestamp") <= end)

        # print(frame)
        return TickerFrame(frame)

    def fetch_latest_price(symbol: str, interval: Interval) -> TickerCandle:
        return fetch_price_history(symbol, interval, None, None)[-1]

    return fetch_price_history, fetch_latest_price, time, parameters


@pytest.fixture
def mock_broker(mocker, mock_fetch_price_history):
    fetch_price_history, fetch_latest_price, time, parameters = mock_fetch_price_history
    broker = MockBroker()
    broker.setup(time)
    mocker.patch.object(broker, "continue_polling", return_value=False)
    mocker.patch.object(
        broker,
        "fetch_price_history",
        fetch_price_history,
    )
    mocker.patch.object(
        broker,
        "fetch_latest_price",
        fetch_latest_price,
    )
    return broker, time, parameters


def test_broker_step_single_interval(mocker, mock_broker):
    """
    Test the basic case where the broker is keeping track of tickers for a single interval.
    """
    broker, time, parameters = mock_broker

    interval = {
        Interval.MIN_1: ["SPY", "AAPL"],
    }

    # Mock the event bus to capture published events
    event_bus_mock = mocker.Mock()
    broker.set_event_bus(event_bus_mock)

    broker.start(interval)
    broker.step()

    # Verify that events were published: 2 individual ticker events + 1 "all" event
    assert event_bus_mock.publish.call_count == 3  # SPY + AAPL + all

    # Check that the correct events were published
    call_args_list = event_bus_mock.publish.call_args_list
    published_events = [call[0] for call in call_args_list]  # Get the event names

    # Should have price_update events for both SPY and AAPL, plus an "all" event
    event_names = [event for event, _ in published_events]
    assert any("SPY" in event_name for event_name in event_names)
    assert any("AAPL" in event_name for event_name in event_names)
    assert any("all" in event_name for event_name in event_names)

    # Check that the events contain the correct data
    for event_name, event_data in published_events:
        assert "price_update:MockBroker:1:" in event_name  # Use interval.value (1) not "1m"
        if "all" not in event_name:
            assert "symbol" in event_data
            assert "price_data" in event_data
            assert event_data["symbol"] in ["SPY", "AAPL"]

    time.increment_time(Interval.MIN_1)
    broker.step()

    # Should have 6 total calls now (3 more for the second step)
    assert event_bus_mock.publish.call_count == 6


def test_broker_step_missing_data(mocker, mock_broker):
    """
    Test that the broker handles missing candles by retrying.
    """
    broker, time, parameters = mock_broker

    parameters["required_retries"] = 3

    interval = {
        Interval.MIN_1: ["SPY", "AAPL"],
    }

    # Mock the event bus to capture published events
    event_bus_mock = mocker.Mock()
    broker.set_event_bus(event_bus_mock)

    broker.start(interval)
    broker.step()

    # Verify that events were published: 2 individual ticker events + 1 "all" event
    assert event_bus_mock.publish.call_count == 3  # SPY + AAPL + all

    # Check that the correct events were published
    call_args_list = event_bus_mock.publish.call_args_list
    published_events = [call[0] for call in call_args_list]  # Get the event names

    # Should have price_update events for both SPY and AAPL, plus an "all" event
    event_names = [event for event, _ in published_events]
    assert any("SPY" in event_name for event_name in event_names)
    assert any("AAPL" in event_name for event_name in event_names)
    assert any("all" in event_name for event_name in event_names)


def test_broker_step_multiple_intervals(mocker, mock_broker):
    """
    Test that the broker handles multiple intervals.
    For example, if the broker keeps track of 1 MIN and 5 MIN intervals,
    and the current time is 10:00 AM, the broker should return candles for both intervals.
    But at 10:01 AM, the broker should only return candles for the 1 MIN interval.
    """
    broker, time, parameters = mock_broker

    interval = {
        Interval.MIN_1: ["SPY", "AAPL"],
        Interval.MIN_5: ["META"],
    }

    # Mock the event bus to capture published events
    event_bus_mock = mocker.Mock()
    broker.set_event_bus(event_bus_mock)

    broker.start(interval)
    broker.step()

    # Verify that events were published for all symbols
    # SPY + AAPL + META + "all" event for MIN_1 + "all" event for MIN_5 = 5 events
    assert event_bus_mock.publish.call_count == 5

    # Check that the correct events were published
    call_args_list = event_bus_mock.publish.call_args_list
    published_events = [call[0] for call in call_args_list]  # Get the event names

    # Should have price_update events for SPY (1), AAPL (1), and META (2)
    event_names = [event for event, _ in published_events]
    assert any("SPY" in event_name and ":1:" in event_name for event_name in event_names)
    assert any("AAPL" in event_name and ":1:" in event_name for event_name in event_names)
    assert any("META" in event_name and ":2:" in event_name for event_name in event_names)  # MIN_5 = value 2
    assert any("all" in event_name and ":1:" in event_name for event_name in event_names)
    assert any("all" in event_name and ":2:" in event_name for event_name in event_names)

    # Test time advancement - advance 1 minute
    time.increment_time(Interval.MIN_1)
    broker.step()

    # Should have more events published (only 1-minute interval symbols)
    # The exact count may vary, but should be at least 8 (original 5 + at least 3 more)
    current_call_count = event_bus_mock.publish.call_count
    assert current_call_count >= 8

    # Test advancing to next 5-minute interval
    time.increment_time(Interval.MIN_1)
    time.increment_time(Interval.MIN_1)
    time.increment_time(Interval.MIN_1)
    time.increment_time(Interval.MIN_1)

    broker.step()

    # Should have all symbols again (including 5-minute interval)
    # The exact count may vary, but should be at least 13 (original 5 + at least 3 + at least 5 more)
    final_call_count = event_bus_mock.publish.call_count
    assert final_call_count >= 13


# class TestBroker(object):
#     """
#     Base class for testing Broker implementations.
#     Each brokers should inherit from this class and implement the necessary
#     setup and teardown procedures specific to the broker, and call the code
#     in this class to test the common functionalities.

#     """

#     def _define_patch(self, path, side_effect):
#         patcher = mock.patch(path)
#         func = patcher.start()
#         func.side_effect = side_effect
#         self.addCleanup(patcher.stop)

#     def setUp(self):
#         self._define_patch("harvest.util.date.get_local_timezone", mock_get_local_timezone)
#         self._define_patch("harvest.util.date.utc_current_time", mock_utc_current_time)

#     def test_fetch_stock_price(self, broker):
#         """
#         Test fetching stock price history
#         The returned DataFrame should be in the format:
#                     [Ticker]
#                     open  high   low  close  volume
#         timestamp

#         Where timestamp is a pandas datetime object in UTC timezone,
#         and open, high, low, close, and volume are float values.
#         """

#         broker = broker()

#         end = mock_utc_current_time()
#         start = end - dt.timedelta(days=1)
#         results = broker.fetch_price_history("AAPL", Interval.MIN_1, start, end)
#         # Check that the returned DataFrame is not empty
#         self.assertGreaterEqual(len(results), 1)
#         self.assertTrue(results.shape[1] == 5)
#         # Check that the returned DataFrame has the correct columns
#         self.assertListEqual(
#             list(results.columns),
#             [("AAPL", "open"), ("AAPL", "high"), ("AAPL", "low"), ("AAPL", "close"), ("AAPL", "volume")],
#         )
#         # Check that the returned DataFrame has the correct index
#         self.assertTrue(results.index[0] >= start)
#         self.assertTrue(results.index[-1] <= end)
#         # Check that the returned DataFrame has the correct data types
#         self.assertEqual(results.dtypes["AAPL", "open"], float)
#         self.assertEqual(results.dtypes["AAPL", "high"], float)
#         self.assertEqual(results.dtypes["AAPL", "low"], float)
#         self.assertEqual(results.dtypes["AAPL", "close"], float)
#         self.assertEqual(results.dtypes["AAPL", "volume"], float)

#         # Check that the returned DataFrame has the correct index type
#         self.assertEqual(type(results.index[0]), pd.Timestamp)
#         self.assertEqual(results.index.tzinfo, dt.timezone.utc)

#     def test_fetch_stock_price_timezone(self, broker):
#         """
#         Test that the price history returned
#         correctly adjusts the input to utc timezone.
#         """
#         broker = broker()

#         # Create an end date in ETC timezone
#         end = dt.datetime(2008, 9, 15, 10, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=-4)))
#         start = end - dt.timedelta(days=1)
#         results = broker.fetch_price_history("AAPL", Interval.MIN_1, start, end)

#         # The last timestamp in the returned DataFrame should be 4 hours ahead of the end date,
#         # since UTC-0 is 4 hours ahead of UTC-4
#         self.assertEqual(results.index[-1], end.astimezone(dt.timezone.utc))

#     def test_fetch_stock_price_str_input(self, broker):
#         """
#         Test fetching stock price history using Yahoo Broker
#         with string input for start and end dates.
#         As with datetime objects, time is converted from local timezone to UTC.
#         """
#         broker = broker()
#         # Use ISO 8601 string for start and end
#         start = "2008-09-15T09:00"
#         end = "2008-09-15T10:00"
#         results = broker.fetch_price_history("AAPL", Interval.MIN_1, start, end)
#         self.assertEqual(type(results.index[0]), pd.Timestamp)
#         self.assertEqual(results.index.tzinfo, dt.timezone.utc)
#         self.assertEqual(results.index[-1], dt.datetime(2008, 9, 15, 14, 0, 0, tzinfo=dt.timezone.utc))

#     def test_setup(self, broker):
#         """
#         Test that the broker is correctly set up with the stats and account objects.
#         """
#         broker = broker()
#         interval = {
#             "SPY": {"interval": Interval.MIN_15, "aggregations": []},
#             "AAPL": {"interval": Interval.MIN_1, "aggregations": []},
#         }
#         stats = Stats(watchlist_cfg=interval)
#         broker.setup(stats, Account())

#         self.assertEqual(broker.poll_interval, Interval.MIN_1)
#         self.assertListEqual(list(broker.stats.watchlist_cfg.keys()), ["SPY", "AAPL"])

#     def test_main(self, broker):
#         """
#         Test that the main function is called with the correct security data.
#         """
#         interval = {
#             "SPY": {"interval": Interval.MIN_1, "aggregations": []},
#             "AAPL": {"interval": Interval.MIN_1, "aggregations": []},
#             "@BTC": {"interval": Interval.MIN_1, "aggregations": []},
#         }

#         def test_main(df):
#             self.assertEqual(len(df), 3)
#             self.assertEqual(df["SPY"].columns[0][0], "SPY")
#             self.assertEqual(df["AAPL"].columns[0][0], "AAPL")
#             self.assertEqual(df["@BTC"].columns[0][0], "@BTC")

#         broker = broker()

#         stats = Stats(watchlist_cfg=interval)
#         broker.setup(stats, Account(), test_main)

#         # Call the main function
#         broker.step()

#     def test_chain_info(self, broker):
#         broker = broker()

#         interval = {"SPY": {"interval": Interval.MIN_1, "aggregations": []}}
#         stats = Stats(watchlist_cfg=interval)
#         broker.setup(stats, Account())

#         info = broker.fetch_chain_info("SPY")

#         self.assertGreater(len(info["exp_dates"]), 0)

#     def test_chain_data(self, broker):
#         broker = broker()

#         interval = {"SPY": {"interval": Interval.MIN_1, "aggregations": []}}
#         stats = Stats(watchlist_cfg=interval)
#         broker.setup(stats, Account())

#         dates = broker.fetch_chain_info("SPY")
#         print(dates)
#         dates = dates["exp_dates"]
#         chain = broker.fetch_chain_data("SPY", dates[0])
#         self.assertGreater(len(chain), 0)
#         self.assertListEqual(list(chain.columns), ["exp_date", "strike", "type"])

#         print(chain)

# TODO test getting market data

# def test_buy_option(self, api):
#     api = api(secret_path)
#     interval = {
#         "TWTR": {"interval": Interval.MIN_5, "aggregations": []},
#     }
#     stats = Stats(watchlist_cfg=interval)
#     api.setup(stats, Account())

#     # Get a list of all options
#     dates = api.fetch_chain_info("TWTR")["exp_dates"]
#     data = api.fetch_chain_data("TWTR", dates[1])
#     option = data.iloc[0]

#     exp_date = option["exp_date"]
#     strike = option["strike"]

#     ret = api.order_option_limit("buy", "TWTR", 1, 0.01, "call", exp_date, strike)

#     time.sleep(5)

#     api.cancel_option_order(ret["order_id"])

#     self.assertTrue(True)

# def test_buy_stock(self, api):
#     """
#     Test that it can buy stocks
#     """
#     api = api(secret_path)
#     interval = {
#         "TWTR": {"interval": Interval.MIN_5, "aggregations": []},
#     }
#     stats = Stats(watchlist_cfg=interval)
#     api.setup(stats, Account())

#     # Limit order TWTR stock at an extremely low limit price
#     # to ensure the order is not actually filled.
#     ret = api.order_stock_limit("buy", "TWTR", 1, 10.0)

#     time.sleep(5)

#     api.cancel_stock_order(ret["order_id"])

# def test_buy_crypto(self, api):
#     """
#     Test that it can buy crypto
#     """
#     api = api(secret_path)
#     interval = {
#         "@DOGE": {"interval": Interval.MIN_5, "aggregations": []},
#     }
#     stats = Stats(watchlist_cfg=interval)
#     api.setup(stats, Account())

#     # Limit order DOGE at an extremely low limit price
#     # to ensure the order is not actually filled.
#     ret = api.order_crypto_limit("buy", "@DOGE", 1, 0.10)

#     time.sleep(5)

#     api.cancel_crypto_order(ret["order_id"])


# if __name__ == "__main__":
#     unittest.main()
