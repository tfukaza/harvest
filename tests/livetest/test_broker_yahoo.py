import datetime as dt
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd
from _test_util import mock_utc_current_time

from harvest.broker.yahoo import YahooBroker
from harvest.util.helper import data_to_occ
from tests.livetest.test_broker_base import TestBroker


def _mock_yf_download(symbol, period, interval, **_):
    delta = None
    if period == "1d":
        delta = dt.timedelta(days=1)
    elif period == "5d":
        delta = dt.timedelta(days=5)
    elif period == "1mo":
        delta = dt.timedelta(days=30)
    elif period == "3mo":
        delta = dt.timedelta(days=90)
    elif period == "1y":
        delta = dt.timedelta(days=365)
    elif period == "5y":
        delta = dt.timedelta(days=365 * 5)
    elif period == "max":
        delta = dt.timedelta(days=365 * 10)

    end = mock_utc_current_time()
    start = end - delta

    if interval == "1m":
        freq = "min"
        delta = (end - start).total_seconds() / 60
    elif interval == "5m":
        freq = "5min"
        delta = (end - start).total_seconds() / 60 / 5
    elif interval == "15m":
        freq = "15min"
        delta = (end - start).total_seconds() / 60 / 15
    elif interval == "30m":
        freq = "30min"
        delta = (end - start).total_seconds() / 60 / 30
    elif interval == "1h":
        freq = "H"
        delta = (end - start).total_seconds() / 60 / 60
    elif interval == "1d":
        freq = "D"
        delta = (end - start).days
    else:
        raise ValueError(f"Invalid interval: {interval}")

    delta = int(delta) + 1

    data_range = pd.date_range(start, periods=delta, freq=freq)

    symbols = symbol.split(" ")

    if len(symbols) > 1:
        df_columns = {
            "Price": ["Open"] * len(symbols)
            + ["High"] * len(symbols)
            + ["Low"] * len(symbols)
            + ["Close"] * len(symbols)
            + ["Adj Close"] * len(symbols)
            + ["Volume"] * len(symbols),
            "Ticker": symbols * 6,
            # "Date": [0] * len(symbols) * 6,
        }

        dummy_df = pd.DataFrame(df_columns)
        dummy_df.set_index(["Price", "Ticker"], inplace=True)
        dummy_df = dummy_df.T
        dummy_df["Date"] = data_range
        dummy_df.set_index("Date", inplace=True)
        dummy_df.index = data_range

        # TODO: Populate each column with dummy data
        return dummy_df

    else:
        dummy_df = pd.DataFrame(
            {
                "Open": [1.0] * delta,
                "High": [2.0] * delta,
                "Low": [0.5] * delta,
                "Close": [1.5] * delta,
                "Adj Close": [1.5] * delta,
                "Volume": [1000] * delta,
            }
        )
        dummy_df.index = data_range
        return dummy_df


def mock_yf_options():
    return ("2008-09-15", "2008-10-15")


def mock_yf_option_chain(date):
    """
        contractSymbol          lastTradeDate               strike      lastPrice   bid     ask     change  percentChange   volume  openInterest    impliedVolatility   inTheMoney  contractSize    currency
    0   SPY240614P00220000     2024-05-13 13:55:14+00:00   220.0       0.02        ...     ...     ...     ...             ...     ...             0.937501            False       REGULAR         USD
    """
    date = pd.to_datetime(date)
    dummy_df = pd.DataFrame(
        {
            "contractSymbol": [data_to_occ("SPY", date, "P", 220.0)],
            "lastTradeDate": [date],
            "strike": [220.0],
            "lastPrice": [0.02],
            "bid": [0.01],
            "ask": [0.03],
            "change": [0.01],
            "percentChange": [0.5],
            "volume": [100],
            "openInterest": [1000],
            "impliedVolatility": [0.937501],
            "inTheMoney": [False],
            "contractSize": ["REGULAR"],
            "currency": ["USD"],
        }
    )

    # Repeat the same row 10 times
    dummy_df = pd.concat([dummy_df] * 10, ignore_index=True)

    return dummy_df


class TestYahooBroker(TestBroker, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self._define_patch("yfinance.download", _mock_yf_download)

    def test_fetch_stock_price(self):
        """
        Test fetching stock price history
        The returned DataFrame should be in the format:
                    [Ticker]
                    open  high   low  close  volume
        timestamp

        Where timestamp is a pandas datetime object in UTC timezone,
        and open, high, low, close, and volume are float values.
        """

        super().test_fetch_stock_price(YahooBroker)

    def test_fetch_stock_price_timezone(self):
        """
        Test that the price history returned
        correctly adjusts the input to utc timezone.
        """

        super().test_fetch_stock_price_timezone(YahooBroker)

    def test_fetch_stock_price_str_input(self):
        """
        Test fetching stock price history using Yahoo Broker
        with string input for start and end dates.
        As with datetime objects, time is converted from local timezone to UTC.
        """

        super().test_fetch_stock_price_str_input(YahooBroker)

    def test_setup(self):
        """
        Test that the broker is correctly set up with the stats and account objects.
        """

        super().test_setup(YahooBroker)

    def test_main(self):
        """
        Test that the main function is called with the correct security data.
        """

        super().test_main(YahooBroker)

    @patch("yfinance.Ticker")
    def test_chain_info(self, mock_ticker):
        """
        Test that the broker can fetch option chain information.
        """
        instance = mock_ticker.return_value
        instance.options = mock_yf_options()

        super().test_chain_info(YahooBroker)

    @patch("yfinance.Ticker")
    def test_chain_data(self, mock_ticker):
        """
        Test that the broker can fetch option chain data.
        """
        instance = mock_ticker.return_value
        instance.options = mock_yf_options()

        """
        Mock the "Option" class that yFiance returns when fetching option chain data.
        """

        def return_option_chain(date):
            mock_option_class = MagicMock()
            mock_option_class.calls = mock_yf_option_chain(date)
            mock_option_class.puts = mock_yf_option_chain(date)
            return mock_option_class

        instance.option_chain = return_option_chain

        super().test_chain_data(YahooBroker)


if __name__ == "__main__":
    unittest.main()
