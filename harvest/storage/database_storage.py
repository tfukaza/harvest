import re
import pandas as pd
import datetime as dt
from typing import Tuple

from sqlalchemy import create_engine, select
from sqlalchemy import Column, Integer, String, DateTime, Float, String
from sqlalchemy.orm import declarative_base

from harvest.storage import BaseStorage

"""
This module serves as a storage system for pandas dataframes in with csv files.
"""

class Asset(Base):
    __tablename__ = 'Assets'
    
    symbol = Column('symbol', String, primary_key=True)
    interval = Column('interval', String, primary_key=True)
    timestamp = Column('timestamp', DateTime, primary_key=True)
    open_ = Column('open', Float)
    close = Column('close', Float)
    high = Column('high', Float)
    low = Column('low', Float)
    volume = Column('volume', Float)
        
    
    def __repr__(self):
        return f"""Asset: {self.timestamp} \t {self.symbol} \t {self.interval} \n 
        open: {self.open_} \t high: {self.high} \t low: {self.low} \t close: {self.close} \t volume: {self.volume}"""

class DBStorage(BaseStorage):
    """
    An extension of the basic storage that saves data in csv files.
    """

    def __init__(self, db_path: str='foo.db'):
        super().__init__()
        """
        Adds a directory to save data to. Loads any data that is currently in the
        directory.
        """
        self.engine = create_engine(f'sqlite:///{db_path}')

        Base = declarative_base()
        Base.metadata.create_all(engine)
        Session = sessionmaker(engine)


        with Session.begin() as session:
            results = session.execute(select(Asset.symbol, Asset.interval).distinct())
            results = tuple(results)
            for symbol, interval in results:
                data = session.execute(select(Asset.timestamp, Asset.open_, Asset.close, Asset.high, Asset.low, Asset.volume).where(Asset.symbol == symbol and Asset.interval == interval))
                df = pd.DataFrame(data, columns=['timestamp', 'open_', 'close', 'high', 'low', 'volume'])
                df.set_index('timestamp', inplace=True)
                df.rename(columns={'open_': 'open'})
                df.columns = pd.MultiIndex.from_product([[symbol], data.columns])
                super().store(symbol, interval, df)

    def store(self, symbol: str, interval: str, data: pd.DataFrame, remove_duplicate: bool=True) -> None:
        """
        Stores the stock data in the storage dictionary and as a csv file.
        :symbol: a stock or crypto
        :interval: the interval between each data point, must be atleast
             1 minute
        :data: a pandas dataframe that has stock data and has a datetime 
            index
        """
        super().store(symbol, interval, data, remove_duplicate)

        if not data.empty:
            self.storage_lock.acquire()

            df = self.storage[symbol][interval]
            df.columns = [column[1] for column in df.columns]
            df.rename(columns={'open': 'open_'}, inplace=True)
            df['timestamp'] = df.index 
            df['symbol'] = symbol
            df['interval'] = interval
            data = df.to_dict(records)

            with Session.begin() as session:
                session.add_all([Asset(**d) for d in data])
                session.commit()

            self.storage_lock.release()