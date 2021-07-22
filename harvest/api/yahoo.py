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
        self.watch_crypto = []
        self.watch_ticker = {}

        if interval not in self.interval_list:
            raise Exception(f'Invalid interval {interval}')
        for s in watch:
            if is_crypto(s):
                self.watch_crypto.append(s[1:]+"-USD")
                self.watch_ticker[s] = yf.Ticker(s[1:]+"-USD")
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
        combo = self.watch_stock + self.watch_crypto
        if len(combo) == 1:
            s = combo[0]
            df = yf.download(s, period='1d', interval=self.interval_fmt, prepost=True)
            if s[-4:] == '-USD':
                    s = '@'+s[:-4]
            df = self._format_df(df, s)
            df_dict[s] = df
        else:
            names = ' '.join(self.watch_stock + self.watch_crypto)
            df = yf.download(names, period='1d', interval=self.interval_fmt, prepost=True)
            for s in combo:
                df_tmp = df.iloc[:, df.columns.get_level_values(1)==s]
                df_tmp.columns = df_tmp.columns.droplevel(1)
                if s[-4:] == '-USD':
                    s = '@'+s[:-4]
                df_tmp = self._format_df(df_tmp, s)
                df_dict[s] = df_tmp
                print(df_tmp)
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
            start = epoch_zero()
        if end is None:
            end = now()

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
        
        crypto = False
        if is_crypto(symbol):
            symbol = symbol[1:]+"-USD"
            crypto = True
        
        df = yf.download(symbol, period=period, interval=get_fmt, prepost=True)
        if crypto:
            symbol = '@'+symbol[:-4]
        df = self._format_df(df, symbol)
        df = df.loc[start:end]
        return df
    
    @API._exception_handler
    def fetch_chain_info(self, symbol: str):
        return {
            "id": "n/a", 
            "exp_dates": [ str_to_date(s) for s in self.watch_ticker[symbol].options],
            "multiplier": 100
        }    

    @API._exception_handler
    def fetch_chain_data(self, symbol: str, date: dt.datetime):

        if bool(self.option_cache) and symbol in self.option_cache and date in self.option_cache[symbol]:
            return self.option_cache[symbol][date]
        
        df = pd.DataFrame(columns=["contractSymbol", "exp_date", "strike", "type"])
        
        chain = self.watch_ticker[symbol].option_chain(date_to_str(date))
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

        if not symbol in self.option_cache:
            self.option_cache[symbol] = {}
        self.option_cache[symbol][date] = df

        return df
    
    @API._exception_handler
    def fetch_option_market_data(self, occ_symbol: str):
        occ_symbol = occ_symbol.replace(' ', '')
        symbol, date, typ, _ = self.occ_to_data(occ_symbol)
        chain = self.watch_ticker[symbol].option_chain(date_to_str(date))
        if typ == 'call':
            chain = chain.calls
        else:
            chain = chain.puts
        df = chain[chain['contractSymbol'] == occ_symbol]
        print(occ_symbol, df)
        return {
                'price': float(df['lastPrice'].iloc[0]),
                'ask':   float(df['ask'].iloc[0]),
                'bid':   float(df['bid'].iloc[0])
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

        return df.dropna()
