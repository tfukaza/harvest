import pandas as pd
import datetime as dt
from threading import Lock

from harvest.utils import interval_to_timedelta, normalize_pands_dt_index

class BaseStorage:

    def __init__(self):
        self.storage_lock = Lock()
        self.storage = {}

    def store(self, symbol: str, interval: str, data: pd.DataFrame) -> None:
        data.index = normalize_pands_dt_index(data)

        if symbol in self.storage:
            intervals = self.storage[symbol]
            if interval in intervals:
                try:
                    self.storage_lock.acquire()
                    intervals[interval] = self._append(intervals[interval], data, interval)
                    self.storage_lock.release()
                except:
                    self.storage_lock.release()
                    raise Exception('Append Failure, case not found!')
            else:
                intervals[interval] = data
        else:
            self.storage_lock.acquire()

            self.storage[symbol] = {
                interval: data,
            }

            self.storage_lock.release()

        print('Store', data.shape)

    def load(self, symbol: str, interval: str='', start: dt.datetime=None, end: dt.datetime=None) -> pd.DataFrame:
        self.storage_lock.acquire()

        if symbol not in self.storage:
            self.storage_lock.release()
            return None 

        self.storage_lock.release()

        if interval == '':
            intervals = [(interval, interval_to_timedelta(interval)) for interval in self.storage[symbol].keys()]
            intervals.sort(key=lambda interval_timedelta: interval_timedelta[1])
            for interval_timedelta in intervals:
                data = self.load(symbol, interval_timedelta[0], start, end)
                if not data is None:
                    return data 
            return None

        dt_interval = interval_to_timedelta(interval)
        self.storage_lock.acquire()
        data = self.storage[symbol][interval]
        self.storage_lock.release()
        data_start = data.index[0] - dt_interval
        data_end = data.index[-1] + dt_interval

        if start is None:
            start = data_start
        else:
            start = start.replace(second=0, microsecond=0)

        if end is None:
            end = data_end
        else:
            end = end.replace(second=0, microsecond=0)

        if data_start <= start and end <= data_end:
            return data.loc[start:end]

        print('Fail')
        return None 

    def data_range(self, symbol: str, interval: str):
        data = self.load(symbol, interval)
        if data is None:
            return None, None

        dt_interval = interval_to_timedelta(interval)
        return data.index[0], data.index[-1]


    def _append(self, current_data: pd.DataFrame, new_data: pd.DataFrame, interval: str) -> pd.DataFrame:
        """
        Appends the data as best it can with no gaps in the data. If there are date times with no
        data then 0s will replace the data.
        """

        dt_interval = interval_to_timedelta(interval)

        cur_data_start = current_data.index[0]
        cur_data_end   = current_data.index[-1]
        new_data_start = new_data.index[0]
        new_data_end   = new_data.index[-1]

        # If the current data covers the new data
        if cur_data_start <= new_data_start and new_data_end <= cur_data_end:
            current_data.loc[new_data_start:new_data_end] = new_data
            return current_data

        # If the new data covers the old data
        elif new_data_start <= cur_data_start and cur_data_end <= new_data_end:
            return new_data

        # If the new data starts before and end in the middle of the current data
        elif new_data_start <= cur_data_start and cur_data_start <= new_data_end and new_data_end <= cur_data_end:
            current_data.loc[:new_data_end] = new_data.loc[cur_data_start:]
            return new_data.append(current_data.loc[new_data_end + dt_interval:])

        # If the new data starts in the middle of the current data and ends after it
        elif cur_data_start <= new_data_start and new_data_start <= cur_data_end and cur_data_end <= new_data_end:
            current_data.loc[new_data_start:] = new_data[:cur_data_end]
            return current_data.append(new_data[cur_data_end + dt_interval:]) 

        # If the new data ends before the current data starts
        elif new_data_end <= cur_data_start:
            num_new_points = int((cur_data_start - new_data_end).total_seconds() // dt_interval.total_seconds())

            if num_new_points > 0:
                gap_index = [new_data_end + dt_interval * i for i in range(1, num_new_points)]
                gap_data = pd.DataFrame(index=gap_index, columns=new_data.columns).fillna(0)
                new_data.append(gap_data)
            return new_data.append(cur_data)

        # If the new data starts before the current data ends
        elif cur_data_end <= new_data_start:  
            num_new_points = int((new_data_start - cur_data_end).total_seconds() // dt_interval.total_seconds())

            if num_new_points > 0:
                gap_index = [cur_data_end + dt_interval * i for i in range(1, num_new_points)]
                gap_data = pd.DataFrame(index=gap_index, columns=new_data.columns).fillna(0)
                current_data.append(gap_data)
            return current_data.append(new_data) 

        else:
            raise Exception("Storage - Invalid indices")