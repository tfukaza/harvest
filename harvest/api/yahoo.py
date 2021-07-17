# Builtins
import datetime as dt
from logging import critical, error, info, warning, debug
from typing import Any, Dict, List, Tuple

# External libraries
import pandas as pd
import yfinance as yf

# Submodule imports
from harvest.api._base import API
from harvest.utils import *

class YahooStreamer(API):

    interval_list = ['1MIN', '5MIN', '15MIN', '30MIN', '1HR']

    def __init__(self, path=None):
        pass

    def setup(self, watch: List[str], interval, trader=None, trader_main=None):
        self.watch_stock = []
        self.watch_ticker = {}

        if interval not in self.interval_list:
            raise Exception(f'Invalid interval {interval}')
        for s in watch:
            if is_crypto(s):
                raise Exception(f"Cannot stream {s}: Cryptocurrencies are not supported in YahooStreamer")
            else:
                self.watch_stock.append(s)
                self.watch_ticker[s] = yf.Ticker(s)
        
        val, unit = expand_interval(interval)
        if unit == 'MIN':
            self.interval_fmt = f'{val}m'
        elif unit == 'HR':
            self.interval_fmt = f'{val}h'

        self.option_cache = {}
        super().setup(watch, interval, interval, trader, trader_main)

    def exit(self):
        self.option_cache = {}

    def main(self):
        df_dict = {}
        for s in self.watch_stock:
            df = yf.download(s, period='1d', interval=self.interval_fmt, prepost=True)
            df = df.iloc[[-1]]
            df = self._format_df(df, s)
            df_dict[s] = df
        self.trader_main(df_dict)

    # -------------- Streamer methods -------------- #
    
    @API._exception_handler
    def fetch_price_history( self,  
        symbol: str,
        interval: str,
        start: dt.datetime = None, 
        end: dt.datetime = None, 
       ):

        debug(f"Fetching {symbol} {interval} price history")

        if start is None:  
            start = self.trader.epoch_zero()
        if end is None:
            end = self.trader.now()

        df = pd.DataFrame()

        if start >= end:
            return df
        
        val, unit = expand_interval(interval)
        if unit == 'MIN':
            get_fmt = f'{val}m'
        elif unit == 'HR':
            get_fmt = f'{val}h'      
        else:
            get_fmt = '1d'      
        
        if interval == '1MIN':
            period = '5d'
        elif interval in ['5MIN', '15MIN', '30MIN', '1HR']:
            period = '1mo'
        else:
            period='max'
        
        df = yf.download(symbol, period=period, interval=get_fmt, prepost=True)
        debug(df)
        df = self._format_df(df, symbol)
        df = df.loc[start:end]
        
        return df
    
    @API._exception_handler
    def fetch_chain_info(self, symbol: str):
        return {
            "id": "n/a", 
            "exp_dates": [ dt.datetime.strptime(s, "%Y-%m-%d") for s in self.watch_ticker[symbol].options],
            "multiplier": 100
        }    

    @API._exception_handler
    def fetch_chain_data(self, symbol: str):

        if bool(self.option_cache) and symbol in self.option_cache:
            return self.option_cache[symbol]
        
        df = pd.DataFrame(columns=["contractSymbol", "exp_date", "strike", "type"])
        
        dates = self.fetch_chain_info(symbol)['exp_dates']
        for d in dates:
            chain = self.watch_ticker[symbol].option_chain(d.strftime("%Y-%m-%d"))
            puts = chain.puts
            puts['type'] = 'put'
            calls = chain.calls
            calls['type'] = 'call'
            df = df.append(puts)
            df = df.append(calls)

        df = df.rename(columns={"contractSymbol": "occ_symbol"})
        df['exp_date'] = df.apply(lambda x: self.occ_to_data(x['occ_symbol'])[1], axis=1)
        df = df[["occ_symbol", "exp_date", "strike", "type"]]
        df.set_index('occ_symbol', inplace=True)

        self.option_cache[symbol] = df
        return df
    
    @API._exception_handler
    def fetch_option_market_data(self, symbol: str):
        _, date, _, _ = self.occ_to_data(symbol)
        chain = self.watch_ticker[symbol].option_chain(date)
        df = chain.loc[symbol]
        return {
                'price': df['lastPrice'][0],
                'ask': df['ask'][0],
                'bid': df['bid'][0]
            }

    # ------------- Broker methods ------------- #
    
    @API._exception_handler
    def fetch_stock_positions(self):
        raise Exception("Not implemented")

    @API._exception_handler
    def fetch_option_positions(self):
        raise Exception("Not implemented")
    
    @API._exception_handler
    def fetch_crypto_positions(self, key=None):
        raise Exception("Not implemented")
    
    @API._exception_handler
    def update_option_positions(self, positions: List[Any]):
        raise Exception("Not implemented")

    @API._exception_handler
    def fetch_account(self):
        raise Exception("Not implemented")

    @API._exception_handler
    def fetch_stock_order_status(self, id):
        raise Exception("Not implemented")
    
    @API._exception_handler
    def fetch_option_order_status(self, id):
        raise Exception("Not implemented")
    
    @API._exception_handler
    def fetch_crypto_order_status(self, id):
        raise Exception("Not implemented")
    
    @API._exception_handler
    def fetch_order_queue(self):
        raise Exception("Not implemented")

    def order_limit(self, 
        side: str, 
        symbol: str,
        quantity: float, 
        limit_price: float, 
        in_force: str='gtc', 
        extended: bool=False):
            raise Exception("Not implemented")
    
    def order_option_limit(self, side: str, symbol: str, quantity: int, limit_price: float, option_type, exp_date: dt.datetime, strike, in_force: str='gtc'):
        raise Exception("Not implemented")
    
    # ------------- Helper methods ------------- #

    def _format_df(self, df: pd.DataFrame, symbol: str):
        df.reset_index(inplace=True)
        ts_name = df.columns[0]
        df['timestamp'] = df[ts_name]
        df = df.set_index(['timestamp'])
        d = df.index[0]
        if d.tzinfo is None or d.tzinfo.utcoffset(d) is None:
            df = df.tz_localize('UTC')
        else:
            df = df.tz_convert(tz='UTC')
        df = df.drop([ts_name], axis=1)
        df = df.rename(columns={"Open": "open", "Close": "close", "High" : "high", "Low" : "low", "Volume" : "volume"})
        df = df[["open", "high", "low", "close", "volume"]].astype(float)
    
        df.columns = pd.MultiIndex.from_product([[symbol], df.columns])

        return df
