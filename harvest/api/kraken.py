# Builtins
import yaml
import datetime as dt
from logging import critical, error, info, warning, debug
from typing import Any, Dict, List, Tuple

# External libraries
import krakenex
import pandas as pd


# Submodule imports
from harvest.api._base import API
from harvest.utils import *

class Kraken(API):

    interval_list = ['1MIN', '5MIN', '15MIN', '30MIN', '1HR', '4HR', '1DAY', '7DAY', '15DAY']

    def __init__(self, path: str=None):
        super().__init__(path)
        self.api = krakenex.API(self.config['api_key'])


    def no_secret(self, path: str) -> bool:
        return self.create_secret(path)

    def setup(self, watch: List[str], interval: str, trader=None, trader_main=None):
        self.watch_stock = []
        self.watch_crypto = []
        cryptos = []

        for s in watch:
            if is_crypto(s):
                self.watch_crypto.append(s)
                cryptos.append(s[1:])
            else:
                self.watch_stock.append(s)

        self.stream.on_bar(*(self.watch_stock + cryptos))(self.update_data)
        threading.Thread(target=self.capture_data, daemon=True).start()

        self.option_cache = {}
        super().setup(watch, interval, interval, trader, trader_main)

    def exit(self):
        self.option_cache = {}

    def main(self):
        df_dict = {}
        df_dict.update(self.fetch_latest_stock_price())
        df_dict.update(self.fetch_latest_crypto_price())
      
        self.trader_main(df_dict)    

    @API._exception_handler
    def fetch_latest_stock_price(self):
        self.data_lock.acquire()
        df = self.data['stocks']
        self.data_lock.release()        
        return df        

    @API._exception_handler
    def fetch_latest_crypto_price(self):
        self.data_lock.acquire()
        df = self.data['cryptos']
        self.data_lock.release()        
        return df            

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
            start = now() - dt.timedelta(days=365 * 5)
        if end is None:
            end = now()

        if start >= end:
            return pd.DataFrame()
        
        val, unit = expand_interval(interval)
        df = self.get_data_from_kraken(symbol, val, unit, start, end)

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
        raise Exception("Kraken does not support stocks.")

    @API._exception_handler
    def fetch_option_positions(self):
        raise Exception("Not implemented")
    
    @API._exception_handler
    def fetch_crypto_positions(self, key=None):
        return [pos.__dict__['_raw'] for pos in self.api.list_positions() if pos.asset_class == 'crypto']
    
    @API._exception_handler
    def update_option_positions(self, positions: List[Any]):
        raise Exception("Alpaca does not support options.")

    @API._exception_handler
    def fetch_account(self):
        return self.api.get_account().__dict__['_raw']

    @API._exception_handler
    def fetch_stock_order_status(self, order_id: str):
        return self.api.get_order(order_id).__dict__['_raw']
    
    @API._exception_handler
    def fetch_option_order_status(self, id):
        raise Exception("Alpaca does not support options.")
    
    @API._exception_handler
    def fetch_crypto_order_status(self, id):
        if self.basic:
            error("Basic accounts can't access crypto. Returning None")
            return None
            
        return self.api.get_order(order_id).__dict__['_raw']
    
    @API._exception_handler
    def fetch_order_queue(self):
        return [pos.__dict__['_raw'] for pos in api.list_positions()]

    def order_limit(self, 
        side: str, 
        symbol: str,
        quantity: float, 
        limit_price: float, 
        in_force: str='gtc', 
        extended: bool=False):
            if self.basic and is_crypto(symbol):
                error("Basic accounts can't buy/sell crypto. Returning None")
                return None

            if is_crypto(symbol):
                symbol = symbol[1:]

            return self.api.submit_order(symbol, quantity, side=side, type="limit", limit_price=limit_price, time_in_force=in_force, extended_hours=extended)
    
    def order_option_limit(self, side: str, symbol: str, quantity: int, limit_price: float, option_type, exp_date: dt.datetime, strike, in_force: str='gtc'):
        raise Exception("Alpaca does not support options.")
    
    # ------------- Helper methods ------------- #

    def get_data_from_kraken(self, symbol: str, multipler: int, timespan: str, start: dt.datetime, end: dt.datetime) -> pd.DataFrame:
        if timespan == 'MIN':
            multipler *= 1
        elif timespan == 'HR':
            timespan *= 60
        elif timespan == 'DAY':
            timespan *= 1440

        temp_symbol = symbol[1:] if is_crypto(symbol) else symbol
        bars = self.api.query_public('OHLC', {'pair': temp_symbol, 'interval': timespan, 'since': end.timestamp})['result'][temp_symbol]
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'vwap', 'volume', 'count'])
        df = self._format_df(df, symbol)
        df = df.loc[start:end]
        return df

    def _format_df(self, df: pd.DataFrame, symbol: str):
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].astype(float)
        df.index = pd.to_datetime(df['timestamp'], unit='s')
        df.index = pd.DatetimeIndex(df.index)
        df.columns = pd.MultiIndex.from_product([[symbol], df.columns])

        return df.dropna()

    def create_secret(self, path: str) -> bool:
        import harvest.wizard as wizard

        w = wizard.Wizard()

        w.println("Hmm, looks like you haven't set up an api key for Kraken.")
        should_setup = w.get_bool("Do you want to set it up now?", default='y')

        if not should_setup:
            w.println("You can't use Kraken without an API key.")
            w.println("You can set up the credentials manually, or use other streamers.")
            return False

        w.println("Alright! Let's get started")

        have_account = w.get_bool("Do you have an Kraken account?", default='y')
        if not have_account:
            w.println("In that case you'll first need to make an account. This takes a few steps.")
            w.println("First visit: https://www.kraken.com/sign-up and sign up. Hit Enter or Return for the next step.")
            w.wait_for_input()


        api_key_id = w.get_string("Enter your API key ID")
        secret_key = w.get_password("Enter your API secret key")
        
        w.println(f"All steps are complete now 🎉. Generating {path}...")

        d = {
            'api_key':         f"{api_key_id}",
            'secret_key':      f"{secret_key}"
        }

        with open(path, 'w') as file:
            yml = yaml.dump(d, file)
        
        w.println(f"{path} has been created! Make sure you keep this file somewhere secure and never share it with other people.")
        
        return True 