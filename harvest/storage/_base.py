import datetime as dt
import sqlite3

import pandas as pd
import polars as pl
import sqlalchemy
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.schema import UniqueConstraint

from harvest.definitions import OrderSide, RuntimeData, TickerFrame, TimeDelta, TimeSpan, Transaction, TransactionFrame
from harvest.enum import Interval
from harvest.util.helper import debugger

"""
This module serves as a basic storage system for pandas dataframes in memory.
It is made to be a simplistic interface for the trader class to store various data,
such as stock price history and transaction history of the algorithm.

All implementations of Storage class must store the following data:
- Stock price history: Database of stock prices
    - Symbol: Stock symbol
    - Interval: Interval of the stock price
    - Date: Date of the price, adjusted to UTC timezone
    - Open: Opening price
    - High: Highest price
    - Low: Lowest price
    - Close: Closing price
- Transaction history: Database of orders
    - Symbol: Symbol of the stock
    - Timestamp: Date of the transaction, adjusted to UTC timezone
    - Algorithm name: Name of the algorithm that made the transaction
    - Side: Buy or sell
    - Quantity: Number of shares
    - Price: Price per share
    - event: "ORDER" or "FILL"
- Account Performance History: Database of account equity history,
    for the following intervals:
    - 1 day, at 5 minute intervals
    - 1 week, at 1 hour intervals
    - 1 month, at 1 day intervals
    - 3 months, at 1 day intervals
    - 1 year, at 1 day intervals
    - all time, at variable intervals
    As for 'all time', the interval will be adjusted as the
    duration increases.
- Algorithm Performance History: Same as account performance history, but for individual algorithms.

The exact implementation of these databases is up to the classes that inherit from BaseStorage,
as long as they implement the API properly.
"""


class Base(DeclarativeBase):
    pass


class PriceHistory(Base):
    __tablename__ = "price_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[dt.datetime]
    symbol: Mapped[str]
    interval: Mapped[str]
    open: Mapped[float]
    high: Mapped[float]
    low: Mapped[float]
    close: Mapped[float]
    volume: Mapped[float]

    __table_args__ = (UniqueConstraint("timestamp", "symbol", "interval"),)


class TransactionHistory(Base):
    __tablename__ = "transaction_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[dt.datetime]
    symbol: Mapped[str]
    side: Mapped[str]
    quantity: Mapped[float]
    price: Mapped[float]
    event: Mapped[str]
    algorithm_name: Mapped[str]


# class AccountPerformanceHistory(Base):
#     __tablename__ = "account_performance_history"
#     id: Mapped[int] = mapped_column(primary_key=True)
#     timestamp: Mapped[dt.datetime]
#     algorithm_name: Mapped[str]
#     return_percentage: Mapped[float]
#     return_price: Mapped[float]
#     equity: Mapped[float]


class Storage:
    """
    A basic storage that stores data in memory.
    """

    connection: sqlite3.Connection

    def __init__(
        self,
        db_path: str | None = None,
        price_storage_limit: dict[Interval, TimeDelta] | None = None,
        transaction_storage_limit: TimeDelta | None = None,
        # performance_storage_limit: int = -1,
    ) -> None:
        """
        price_storage_limit: The maximum number of data points to store for asset price history.
        transaction_storage_limit: The maximum number of data points to store for transaction history.
        performance_storage_limit: The maximum number of data points to store for performance history.
        """

        if db_path:
            self.db_engine = sqlalchemy.create_engine(db_path)
        else:
            self.db_engine = sqlalchemy.create_engine("sqlite:///:memory:")

        # self.session = sessionmaker(bind=self.db_engine)

        default_price_storage_limit = {
            Interval.MIN_1: TimeDelta(TimeSpan.DAY, 1),
            Interval.MIN_5: TimeDelta(TimeSpan.DAY, 7),
            Interval.MIN_15: TimeDelta(TimeSpan.DAY, 14),
            Interval.MIN_30: TimeDelta(TimeSpan.DAY, 30),
            Interval.HR_1: TimeDelta(TimeSpan.DAY, 60),
            Interval.DAY_1: TimeDelta(TimeSpan.DAY, 365),
        }

        if not price_storage_limit:
            self.price_storage_limit = default_price_storage_limit
        else:
            self.price_storage_limit = default_price_storage_limit | price_storage_limit

        self.price_history_oldest_timestamp: dict[str, dict[Interval, dt.datetime]] = {}

        if not transaction_storage_limit:
            self.transaction_storage_limit = TimeDelta(TimeSpan.DAY, 14)
        else:
            self.transaction_storage_limit = transaction_storage_limit

        self.transaction_history_oldest_timestamp: dict[str, dt.datetime] = {}

        # self.transaction_storage_limit = transaction_storage_limit
        # self.performance_storage_limit = performance_storage_limit

        # BaseStorage uses a python dictionary to store the data,
        # where key is asset symbol and value is a pandas dataframe.

        # price_history_schema = pl.DataFrame(
        #     schema={
        #         "timestamp": pl.Datetime,
        #         "symbol": pl.String,
        #         "interval": pl.String,
        #         "open": pl.Float64,
        #         "high": pl.Float64,
        #         "low": pl.Float64,
        #         "close": pl.Float64,
        #         "volume": pl.Float64,
        #     }
        # )
        # price_history_schema.write_database(
        #     table_name="price_history",
        #     connection=self.db_engine,
        # )
        Base.metadata.drop_all(self.db_engine)
        Base.metadata.create_all(self.db_engine)
        # self.price_history_oldest_timestamp: dt.datetime | None = None
        # self.transaction_history_oldest_timestamp: dt.datetime | None = None
        # transaction_history_schema = pl.DataFrame(
        #     schema={
        #         "symbol": pl.String,
        #         "timestamp": pl.Datetime,
        #         "event": pl.String,
        #         "algorithm_name": pl.String,
        #         "side": pl.String,
        #         "quantity": pl.Float64,
        #         "price": pl.Float64,
        #     }
        # )

        # transaction_history_schema.write_database(
        #     table_name="transaction_history",
        #     connection=self.db_engine,
        # )

        # # self.storage_daytrade = pd.DataFrame(columns=["timestamp", "symbol"])
        # # self.storage_calendar = pd.DataFrame(columns=["is_open", "open_at", "close_at"], index=[])

        # account_performance_history_schema = pl.DataFrame(
        #     schema={
        #         "timestamp": pl.Datetime,
        #         "algorithm_name": pl.String,
        #         "profit": pl.Float64,
        #     }
        # )

        # account_performance_history_schema.write_database(
        #     table_name="account_performance_history",
        #     connection=self.db_engine,
        # )

        # algorithm_performance_history_schema = pl.DataFrame(
        #     schema={
        #         "timestamp": pl.Datetime,
        #         "algorithm_name": pl.String,
        #         "profit": pl.Float64,
        #     }
        # )

        # algorithm_performance_history_schema.write_database(
        #     table_name="algorithm_performance_history",
        #     connection=self.db_engine,
        # )

    def setup(self, stats: RuntimeData) -> None:
        self.stats = stats

    # def _sqlite_timestamp_to_datetime(self, timestamp: str) -> dt.datetime:
    #     return dt.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S%.f")

    def insert_price_history(self, data: TickerFrame) -> None:
        """
        Stores the stock data in the storage dictionary.
        """

        df: pl.DataFrame = data.df

        interval = df.head(1)["interval"].item()
        interval = Interval.from_str(interval)
        symbol = df.head(1)["symbol"].item()
        latest_timestamp = df.tail(1)["timestamp"].item()

        if self.price_storage_limit:
            new_oldest_timestamp = latest_timestamp - self.price_storage_limit[interval].delta_datetime
            if (
                symbol in self.price_history_oldest_timestamp
                and interval in self.price_history_oldest_timestamp[symbol]
                and latest_timestamp - self.price_history_oldest_timestamp[symbol][interval]
                > self.price_storage_limit[interval].delta_datetime
            ):
                with Session(self.db_engine) as session:
                    session.query(PriceHistory).filter(
                        PriceHistory.timestamp <= new_oldest_timestamp, PriceHistory.symbol == symbol
                    ).delete()
                    session.commit()
            elif symbol not in self.price_history_oldest_timestamp:
                self.price_history_oldest_timestamp[symbol] = {}

            self.price_history_oldest_timestamp[symbol][interval] = new_oldest_timestamp

        stmt = insert(PriceHistory).values(df.to_dicts())
        stmt = stmt.on_conflict_do_update(
            index_elements=["timestamp", "symbol", "interval"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
            },
        )
        with Session(self.db_engine) as session:
            session.execute(stmt)
            session.commit()

        # df.write_database(
        #     table_name="price_history",
        #     connection=self.db_engine,
        #     if_table_exists="append",
        # )

    def get_price_history(
        self,
        symbol: str,
        interval: Interval | None = None,
        start: dt.datetime | None = None,
        end: dt.datetime | None = None,
    ) -> TickerFrame:
        """
        Loads the stock data given the symbol and interval. May return only
        a subset of the data if start and end are given.

        If the specified interval does not exist, it will attempt to generate it by
        aggregating data.
        :symbol: a stock or crypto
        :interval: the interval between each data point, must be at least MIN_1
        :start: Datetime object specifying the start of the time range, inclusive. Set to None to return all data
        :end: Datetime object specifying the end of the time range, inclusive
        """
        # frame = pl.read_database(
        #     query=f"SELECT * FROM price_history WHERE symbol = '{symbol}'",
        #     connection=self.db_engine,
        # )

        filters = [
            PriceHistory.symbol == symbol,
            PriceHistory.interval == str(interval),
        ]
        if start:
            filters.append(PriceHistory.timestamp >= start)
        if end:
            filters.append(PriceHistory.timestamp <= end)

        # with Session(self.db_engine) as session:
        #     frame = session.query(PriceHistory).filter(*filters).all()

        # frame = {
        #     "timestamp": [row.timestamp for row in frame],
        #     "symbol": [row.symbol for row in frame],
        #     "interval": [row.interval for row in frame],
        #     "low": [row.low for row in frame],
        #     "high": [row.high for row in frame],
        #     "close": [row.close for row in frame],
        #     "open": [row.open for row in frame],
        #     "volume": [row.volume for row in frame],
        # }
        # print(frame)
        # Convert to polars dataframe
        # frame = pl.DataFrame(frame)
        # SQLite saves dates as strings, so we need to convert them to datetime objects
        # frame = frame.with_columns(pl.col("timestamp").str.to_datetime("%Y-%m-%d %H:%M:%S%.f"))

        # df = df.filter(pl.col("timestamp").is_between(start, end))
        with Session(self.db_engine) as session:
            assert session.bind is not None
            db_query = session.query(PriceHistory).filter(*filters)
            db_query_str = str(
                db_query.statement.compile(
                    dialect=session.bind.dialect,
                    compile_kwargs={"literal_binds": True},
                )
            )
        # with Session(self.db_engine) as session:
        frame = pl.read_database(
            query=db_query_str,
            connection=self.db_engine,
        )

        frame = frame.with_columns(pl.col("timestamp").str.to_datetime("%Y-%m-%d %H:%M:%S%.f"))
        # remove the "id" column
        frame = frame.drop("id")

        return TickerFrame(frame)

    # def add_calendar_data(self, data: Dict[str, Any]) -> None:
    #     timestamp = self.stats.timestamp.date()
    #     is_open = data["is_open"]
    #     open_at = data["open_at"]
    #     close_at = data["close_at"]
    #     df = pd.DataFrame(
    #         [[is_open, open_at, close_at]],
    #         columns=["is_open", "open_at", "close_at"],
    #         index=[timestamp],
    #     )
    #     self._append(self.storage_calendar, df, remove_duplicate=True)

    def insert_transaction(
        self,
        transaction: Transaction,
    ) -> None:
        df = pl.DataFrame(
            {
                "timestamp": transaction.timestamp,
                "symbol": transaction.symbol,
                "event": transaction.event,
                "algorithm_name": transaction.algorithm_name,
                "side": transaction.side.value,
                "quantity": transaction.quantity,
                "price": transaction.price,
            }
        )

        symbol = df.head(1)["symbol"].item()
        latest_timestamp = df.tail(1)["timestamp"].item()

        if self.transaction_storage_limit:
            new_oldest_timestamp = latest_timestamp - self.transaction_storage_limit.delta_datetime
            if (
                symbol in self.transaction_history_oldest_timestamp
                and latest_timestamp - self.transaction_history_oldest_timestamp[symbol]
                > self.transaction_storage_limit.delta_datetime
            ):
                with Session(self.db_engine) as session:
                    session.query(TransactionHistory).filter(
                        TransactionHistory.timestamp <= new_oldest_timestamp,
                        TransactionHistory.symbol == symbol,
                    ).delete()
                    session.commit()

            self.transaction_history_oldest_timestamp[symbol] = new_oldest_timestamp

        df.write_database(
            table_name="transaction_history",
            connection=self.db_engine,
            if_table_exists="append",
        )

    def get_transaction_history(
        self,
        symbol: str,
        side: OrderSide | None = None,
        algorithm_name: str | None = None,
        start: dt.datetime | None = None,
        end: dt.datetime | None = None,
    ) -> TransactionFrame:
        filters = [
            TransactionHistory.symbol == symbol,
        ]
        if side:
            filters.append(TransactionHistory.side == side.value)
        if algorithm_name:
            filters.append(TransactionHistory.algorithm_name == algorithm_name)
        if start:
            filters.append(TransactionHistory.timestamp >= start)
        if end:
            filters.append(TransactionHistory.timestamp <= end)

        with Session(self.db_engine) as session:
            assert session.bind is not None
            db_query = session.query(TransactionHistory).filter(*filters)
            db_query_str = str(
                db_query.statement.compile(
                    dialect=session.bind.dialect,
                    compile_kwargs={"literal_binds": True},
                )
            )
        frame = pl.read_database(
            query=db_query_str,
            connection=self.db_engine,
        )

        frame = pl.DataFrame(frame)
        frame = frame.with_columns(pl.col("timestamp").str.to_datetime("%Y-%m-%d %H:%M:%S%.f"))
        # remove the "id" column
        frame = frame.drop("id")

        return TransactionFrame(frame)

    # def load_daytrade(self) -> pd.DataFrame:
    #     return self.storage_daytrade

    # def load_calendar(self) -> pd.DataFrame:
    #     return self.storage_calendar

    # def reset(self, symbol: str, interval: Interval) -> None:
    #     """
    #     Resets to an empty dataframe
    #     """
    #     self.storage_lock.acquire()
    #     self.price_history = pd.DataFrame()
    #     self.storage_lock.release()

    def _append(
        self,
        current_data: pd.DataFrame,
        new_data: pd.DataFrame,
        remove_duplicate: bool = True,
    ) -> pd.DataFrame:
        """
        Appends the data as best it can with gaps in the data for weekends
        and time when no data is collected.
        :current_data: the current data that we have on the stock for
            the interval
        :new_data: data coming from the the broker's API call
        """

        new_df = pd.concat([current_data, new_data])
        if remove_duplicate:
            new_df = new_df[~new_df.index.duplicated(keep="last")].sort_index()
        return new_df

    # def aggregate(
    #     self,
    #     symbol: str,
    #     base: Interval,
    #     target: Interval,
    #     remove_duplicate: bool = True,
    # ) -> None:
    #     """
    #     Aggregates the stock data from the interval specified in 'from' to 'to'.
    #     """
    #     self.storage_lock.acquire()
    #     data = self.storage_price[symbol][base]
    #     self.storage_price[symbol][target] = self._append(
    #         self.storage_price[symbol][target],
    #         aggregate_df(data, target),
    #         remove_duplicate,
    #     )
    #     cur_len = len(self.storage_price[symbol][target])
    #     if self.price_storage_limit and cur_len > self.price_storage_size:
    #         self.storage_price[symbol][target] = self.storage_price[symbol][target].iloc[-self.price_storage_size :]
    #     self.storage_lock.release()

    # def init_performance_data(self, equity: float, timestamp: dt.datetime) -> None:
    #     for interval, _ in self.performance_history_intervals:
    #         self.storage_performance[interval] = pd.DataFrame({"equity": [equity]}, index=[timestamp])

    def add_performance_data(self, equity: float, timestamp: dt.datetime) -> None:
        """
        Adds the performance data to the storage.

        This function is called every time main() is called in trader.
        It takes the current equity and adds it to each interval.


        :param equity: Current equity of the account.
        """

        # Performance history range up until '3 MONTHS' have the
        # same interval as the polling interval of the trader.
        # for interval, days in self.performance_history_intervals[0:3]:
        #     df = self.storage_performance[interval]
        #     cutoff = timestamp - dt.timedelta(days=days)
        #     if df.index[0] < cutoff:
        #         df = df.loc[df.index >= cutoff]
        #     df = pd.concat([df, pd.DataFrame({"equity": [equity]}, index=[timestamp])])
        #     self.storage_performance[interval] = df

        # # Performance history intervals after '3 MONTHS' are populated
        # # only for each day.
        # for interval, days in self.performance_history_intervals[3:5]:
        #     df = self.storage_performance[interval]
        #     if df.index[-1].date() == timestamp.date():
        #         df = df.iloc[:-1]
        #         df = pd.concat([df, pd.DataFrame({"equity": [equity]}, index=[timestamp])])
        #     else:
        #         df = pd.concat([df, pd.DataFrame({"equity": [equity]}, index=[timestamp])])
        #         cutoff = timestamp - dt.timedelta(days=days)
        #         if df.index[0] < cutoff:
        #             df = df.loc[df.index >= cutoff]
        #     self.storage_performance[interval] = df

        # df = self.storage_performance["ALL"]
        # if df.index[-1].date() == timestamp.date():
        #     df = df.iloc[:-1]
        # df = pd.concat([df, pd.DataFrame({"equity": [equity]}, index=[timestamp])])
        # self.storage_performance["ALL"] = df

        self.account_performance_history = pd.concat(
            [self.account_performance_history, pd.DataFrame({"equity": [equity]}, index=[timestamp])]
        )

        debugger.debug("Performance data added")
