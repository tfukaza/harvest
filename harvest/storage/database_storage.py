import re
import pandas as pd
import datetime as dt
from typing import Tuple

from sqlalchemy import create_engine, select
from sqlalchemy import Column, Integer, String, DateTime, Float, String
from sqlalchemy.orm import declarative_base, sessionmaker

from harvest.storage import BaseStorage
from harvest.utils import *

"""
This module serves as a storage system for pandas dataframes in with SQL tables.
"""

Base = declarative_base()


class Asset(Base):
    """
    This class defines what is in each row in the Assets table.
    """

    __tablename__ = "asset"
    symbol = Column("symbol", String, primary_key=True)
    interval = Column("interval", String, primary_key=True)
    timestamp = Column("timestamp", DateTime, primary_key=True)
    open_ = Column("open", Float)
    close = Column("close", Float)
    high = Column("high", Float)
    low = Column("low", Float)
    volume = Column("volume", Float)

    def __repr__(self):
        return f"""Asset: {self.timestamp} \t {self.symbol} \t {self.interval} \n 
        open: {self.open_} \t high: {self.high} \t low: {self.low} \t close: {self.close} \t volume: {self.volume}"""


class DBStorage(BaseStorage):
    """
    An extension of the basic storage that saves data in SQL tables.
    """

    def __init__(self, db: str = "sqlite:///data.db"):
        """
        Adds a directory to save data to. Loads any data that is currently in the
        directory.
        """
        engine = create_engine(db)
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(engine)

    def store(
        self,
        symbol: str,
        interval: str,
        data: pd.DataFrame,
        remove_duplicate: bool = True,
    ) -> None:
        """
        Stores the stock data in the storage dictionary in SQL tables.
        :symbol: a stock or crypto
        :interval: the interval between each data point, must be atleast
             1 minute
        :data: a pandas dataframe that has stock data and has a datetime
            index
        """

        if not data.empty:
            data.index = normalize_pandas_dt_index(data)
            data.columns = [column[1] for column in data.columns]
            data.rename(columns={"open": "open_"}, inplace=True)
            data["timestamp"] = data.index
            data["symbol"] = symbol
            data["interval"] = interval
            data = data.to_dict("records")

            with self.Session.begin() as session:
                [session.merge(Asset(**d)) for d in data]
                session.commit()

    def aggregate(
        self, symbol: str, base: str, target: str, remove_duplicate: bool = True
    ):
        """
        Aggregates the stock data from the interval specified in 'from' to 'to'.
        """

        data = self.load(symbol, base)
        agg_data = self._append(
            self.load(symbol, target), aggregate_df(data, target), remove_duplicate
        )
        self.store(symbol, target, agg_data)

    def reset(self, symbol: str, interval: str):
        """
        Resets to an empty dataframe
        """

        with self.Session.begin() as session:
            session.execute(
                Asset.__table__.delete().where(
                    Asset.symbol == symbol and Asset.interval == interval
                )
            )
            session.commit()

    def load(
        self,
        symbol: str,
        interval: str = "",
        start: dt.datetime = None,
        end: dt.datetime = None,
    ) -> pd.DataFrame:
        """
        Loads the stock data given the symbol and interval. May return only
        a subset of the data if start and end are given and there is a gap
        between the last data point and the given end datetime.

        If the specified interval does not exist, it will attempt to generate it by
        aggregating data.
        :symbol: a stock or crypto
        :interval: the interval between each data point, must be at least
             1 minute
        :start: a datetime object
        """

        with self.Session.begin() as session:
            data = session.execute(
                select(
                    Asset.timestamp,
                    Asset.open_,
                    Asset.close,
                    Asset.high,
                    Asset.low,
                    Asset.volume,
                ).where(Asset.symbol == symbol and Asset.interval == interval)
            )
            data = pd.DataFrame(
                data, columns=["timestamp", "open_", "close", "high", "low", "volume"]
            )

            if data.empty:
                return None

            data.set_index("timestamp", inplace=True)
            data.index = data.index.tz_localize(tz="UTC")
            data.rename(columns={"open_": "open"}, inplace=True)
            data.columns = pd.MultiIndex.from_product([[symbol], data.columns])

        # If the start and end are not defined, then set them to the
        # beginning and end of the data.
        if start is None:
            start = data.index[0]
        if end is None:
            end = data.index[-1]

        return data.loc[(data.index >= start) & (data.index <= end)]

    def data_range(self, symbol: str, interval: str) -> Tuple[dt.datetime]:
        return super().data_range(symbol, interval)

    def _append(
        self,
        current_data: pd.DataFrame,
        new_data: pd.DataFrame,
        remove_duplicate: bool = True,
    ) -> pd.DataFrame:
        return super()._append(current_data, new_data, remove_duplicate)
