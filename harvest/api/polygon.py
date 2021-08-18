# Builtins
import json
import yaml
import datetime as dt
import urllib.request
from logging import critical, error, info, warning, debug
from typing import Any, Dict, List, Tuple

# External libraries
import pandas as pd

# Submodule imports
from harvest.api._base import API
from harvest.utils import *

class PolygonStreamer(API):

    def __init__(self, path: str=None, is_basic_account: bool=False):
        super().__init__(path)
        self.basic = is_basic_account

    def no_secret(self, path: str) -> bool:
        return self.create_secret(path)

    def setup(self, watch: List[str], interval: str, trader=None, trader_main=None):
        self.watch_stock = []
        self.watch_crypto = []

        for s in watch:
            if is_crypto(s):
                self.watch_crypto.append(s)
            else:
                self.watch_stock.append(s)

        self.option_cache = {}
        super().setup(watch, interval, interval, trader, trader_main)

    def exit(self):
        self.option_cache = {}

    def main(self):
        df_dict = {}
        combo = self.watch_stock + self.watch_crypto
        if self.basic and len(combo) > 5:
            error("Basic accounts only allow for 5 API calls per minute, trying to get data for more than 5 assets! Aborting.")
            return

        for s in combo:
            df = self.get_data_from_polygon(s, 1, 'day', now() - dt.timedelta(days=1), now())
            df_dict[s] = df
            print(df)            
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
            start = now() - dt.timedelta(days=365 * 2)
        if end is None:
            end = now()

        if start >= end:
            return pd.DataFrame()
        
        val, unit = expand_interval(interval)
        df = self.get_data_from_polygon(symbol, val, unit, start, end)

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
        df = df.rename(columns={"t": "timestamp", "o": "open", "c": "close", "h" : "high", "l" : "low", "v" : "volume"})
        df = df[["timestamp", "open", "high", "low", "close", "volume"]].astype(float)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        # Timestamps are in US/Eastern and then converted UTC
        df.index = pd.DatetimeIndex(df['timestamp'], tz=pytz.timezone('US/Eastern')).tz_convert(tz=pytz.utc)
        df.drop(columns=['timestamp'], inplace=True)
        
        df.columns = pd.MultiIndex.from_product([[symbol], df.columns])

        return df.dropna()

    def create_secret(self, path: str) -> bool:
        import harvest.wizard as wizard

        w = wizard.Wizard()

        w.println("Hmm, looks like you haven't set up an api key for Polygon.")
        should_setup = w.get_bool("Do you want to set it up now?", default='y')

        if not should_setup:
            w.println("You can't use Polygon without an API key.")
            w.println("You can set up the credentials manually, or use other streamers.")
            return False

        w.println("Alright! Let's get started")

        have_account = w.get_bool("Do you have a Polygon account?", default='y')
        if not have_account:
            w.println("In that case you'll first need to make an account. I'll wait here, so hit Enter or Return when you've done that.")
            w.wait_for_input()

        api_key = w.get_string("Enter your API key")
        
        w.println(f"All steps are complete now 🎉. Generating {path}...")

        d = {
            'api_key':      f"{api_key}",
        }

        with open(path, 'w') as file:
            yml = yaml.dump(d, file)
        
        w.println(f"{path} has been created! Make sure you keep this file somewhere secure and never share it with other people.")
        
        return True 

    def get_data_from_polygon(self, symbol: str, multipler: int, timespan: str, start: dt.datetime, end: dt.datetime) -> pd.DataFrame:
        if self.basic and start < now() - dt.timedelta(days=365 * 2):
            warning("Start time is over two years old! Only data from the past two years will be returned for basic accounts.")

        if timespan == 'MIN':
            timespan = 'minute'
        elif timespan == 'HR':
            timespan = 'hour'
        elif timespan == 'DAY':
            timespan = 'day'

        start_str = start.strftime('%Y-%m-%d')
        end_str = end.strftime('%Y-%m-%d')

        crypto = False
        if is_crypto(symbol):
            symbol = "X:" + symbol[1:] + "-USD"
            crypto = True

        request_form = "https://api.polygon.io/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{start}/{end}?adjusted=true&sort=asc&apiKey={api_key}"
        request = request_form.format(symbol=symbol, multiplier=multipler, timespan=timespan, start=start_str, end=end_str, api_key=self.config['api_key'])
        response = json.load(urllib.request.urlopen(request))

        if response['status'] != 'ERROR':
            df = pd.DataFrame(response['results'])
        else:
            error(f"Request error! Returning empty dataframe. \n {response}")
            return pd.DataFrame()

        if crypto:
            symbol = '@' + symbol[2:-4]
        df = self._format_df(df, symbol)
        df = df.loc[start:end]
        return df