# Builtins
import os
import datetime as dt

# External libraries
import pandas as pd

# Script to collect hourly stock price data
DB_PATH="./db"

class Load:
    """
    Load class provides an interface between the broker and the database
    used to store the stock price. By default, data is saved as a pandas file 
    in a local directory. There are future plans to extend the class and provide 
    interface with other databases like PostgreSQL.    
    """

    def __init__(self):
        # if the data dir does not exists, create it
        os.makedirs(DB_PATH, exist_ok=True)

    # get a datetime of last time database update was performed
    def get_timestamp(self, symbol, interval):
        path = f"{DB_PATH}/{symbol}/lastSave-{interval}"
        if not os.path.exists(path):
            return dt.datetime(1970, 1, 1)
        ts = open(path)
        ts_text = ts.read()
        date = dt.datetime.strptime(ts_text, '%Y-%m-%d %H:%M')
        return date

    def set_timestamp(self, symbol, date, interval):
        path = f"{DB_PATH}/{symbol}/lastSave-{interval}"
        ts = open(path, 'w')
        ts.seek(0)
        date_str = date.strftime('%Y-%m-%d %H:%M')
        ts.write(date_str)

    def append_entry(self, symbol, interval, df, remove_dup=True):
        save_path = f"{DB_PATH}/{symbol}/data-{interval}" 
        save_dir = f"{DB_PATH}/{symbol}"
        if not os.path.isdir(save_dir):
            os.mkdir(save_dir)
        data = self.get_entry(symbol, interval)
        data = data.append(df) if not data.empty else df
        if remove_dup:
            data = data[~data.index.duplicated(keep='last')]
        data.to_pickle(save_path)

    def get_entry(self, symbol, interval):
        path = f"{DB_PATH}/{symbol}/data-{interval}" 
        save_dir = f"{DB_PATH}/{symbol}"
        if not os.path.isdir(save_dir):
            os.mkdir(save_dir)
        if not os.path.exists(path):
            data = pd.DataFrame()
            return data
        return pd.read_pickle(path)
    