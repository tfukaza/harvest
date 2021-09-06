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
    crypto_ticker_to_kraken_names = {
        'BTC': 'XXBT',     'ETH': 'XETH',      'ADA': 'ADA',
        'USDT': 'USDT',    'XRP': 'XXRP',      'SOL': 'SOL',
        'DOGE': 'XDG',    'DOT': 'DOT',       'USDC': 'USDC',
        'UNI': 'UNI',      'LTC': 'XLTC',      'LINK': 'LINK',
        'BCH': 'BCH',      'FIL': 'FIL',       'MATIC': 'MATIC',
        'WBTC': 'WBTC',    'ETC': 'XETC',      'XLM': 'XXLM',
        'TRX': 'TRX',      'DAI': 'DAI',       'EOS': 'EOS',
        'ATOM': 'ATOM',    'AAVE': 'AAVE',     'XMR': 'XXMR',
        'AXS': 'AXS',      'GRT': 'GRT',       'XTZ': 'XXTZ',
        'ALGO': 'ALGO',    'MKR': 'MKR',       'KSM': 'KSM',
        'WAVE': 'WAVE',    'COMP': 'COMP',     'DASH': 'DASH',
        'CHZ': 'CHZ',      'ZEC': 'XZEC',      'MANA': 'MANA',
        'ENJ': 'ENJ',      'SUSHI': 'SUSHI',   'YFI': 'YFI',
        'QTUM': 'QTUM',    'FLOW': 'FLOW',     'SNX': 'SNX',
        'BAT': 'BAT',      'SC': 'SC',         'ICX': 'ICX',
        'PERP': 'PERP',    'BNT': 'BNT',       'OMG': 'OMG',
        'CRV': 'CRV',      'ZRX': 'ZRX',       'NANO': 'NANO',
        'ANKR': 'ANKR',    'SAND': 'SAND',     'REN': 'REN',
        'KAVA': 'KAVA',    'MINA': 'MINA',     '1INCH': '1INCH',
        'GHST': 'GHST',    'ANT': 'ANT',       'REP': 'XREP',
        'REPV2': 'XREPV2', 'BADGER': 'BADGER', 'BAL': 'BAL',
        'BAND': 'BAND',    'CTSI': 'CTSI',     'CQT': 'CQT',
        'EWT': 'EWT',      'MLN': 'XMLN',      'ETH2': 'ETH2',
        'GNO': 'GNO',      'INJ': 'INJ',       'KAR': 'KAR',
        'KEEP': 'KEEP',    'KNC': 'KNC',       'LSK': 'LSK',
        'LTP': 'LTP',      'LRC': 'LRC',       'MIR': 'MIR',
        'OCEAN': 'OCEAN',  'PAXG': 'PAXG',     'RARI': 'RARI',
        'REN': 'REN',      'XRP': 'XXRP',      'SRM': 'SRM',
        'STORJ': 'STORJ',  'TBTC': 'TBTC',     'OGN': 'OGN',
        'OXT': 'OXT'
    }


    def __init__(self, path: str=None):
        super().__init__(path)
        self.api = krakenex.API(self.config['api_key'], self.config['secret_key'])

    def no_secret(self, path: str) -> bool:
        return self.create_secret(path)

    def setup(self, watch: List[str], interval: str, trader=None, trader_main=None):
        self.watch_crypto = []
        if is_crypto(s):
            self.watch_crypto.append(s)
        else:
            warning("Kraken does not support stocks!")

        self.option_cache = {}
        super().setup(watch, interval, interval, trader, trader_main)

    def exit(self):
        self.option_cache = {}

    def main(self):
        df_dict = {}
        df_dict.update(self.fetch_latest_crypto_price())

        self.trader_main(df_dict)

    @API._exception_handler
    def fetch_latest_crypto_price(self):
        dfs = {}
        for symbol in self.watch_cryptos:
            dfs[symbol] = self.fetch_price_history(symbol, self.interval, now() - dt.timedelta(days=7), now()).iloc[[0]]
        return dfs

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

        if interval not in self.interval_list:
            raise Exception(f"Interval {interval} not in interval list. Possible options are: {self.interval_list}")
        val, unit = expand_interval(interval)
        df = self.get_data_from_kraken(symbol, val, unit, start, end)

        return df

    @API._exception_handler
    def fetch_chain_info(self, symbol: str):
        return {
            "id": "n/a",
            "exp_dates": [str_to_date(s) for s in self.watch_ticker[symbol].options],
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
        raise Exception("Kraken does not support options")

    # ------------- Broker methods ------------- #

    @API._exception_handler
    def fetch_stock_positions(self):
        raise Exception("Kraken does not support stocks.")

    @API._exception_handler
    def fetch_option_positions(self):
        raise Exception("Kraken does not support options")

    @API._exception_handler
    def fetch_crypto_positions(self, key=None):
        return [pos.__dict__['_raw'] for pos in self.api.list_positions() if pos.asset_class == 'crypto']

    @API._exception_handler
    def update_option_positions(self, positions: List[Any]):
        raise Exception("Kraken does not support options.")

    @API._exception_handler
    def fetch_account(self):
        return self.api.query_private('Balance')['results']

    @API._exception_handler
    def fetch_stock_order_status(self, order_id: str):
        return self.api.get_order(order_id).__dict__['_raw']

    @API._exception_handler
    def fetch_option_order_status(self, id):
        raise Exception("Kraken dies not support options.")

    @API._exception_handler
    def fetch_crypto_order_status(self, id: str):
        closed_orders = self.get_result(self.api.query_private('ClosedOrders'))
        orders = closed_orders['closed'] + self.fetch_order_queue()
        if id in orders.keys():
            return orders.get(id)
        raise Exception(f"{id} not found in your orders.")


    @API._exception_handler
    def fetch_order_queue(self):
        open_orders = self.get_result(self.api.query_private('OpenOrders'))
        return open_orders['open']

    def order_limit(self,
        side: str,
        symbol: str,
        quantity: float,
        limit_price: float,
        in_force: str='gtc',
        extended: bool=False):
            if is_crypto(symbol):
                symbol = ticker_to_kraken(symbol)
            else:
                error("Kraken does not support stocks.")
                return

            order = self.get_result(self.api.query_private('AddOrder', {'ordertype': 'limit', 'type': side, 'volume': quantity, 'pair': symbol}))
            return order

    def order_option_limit(self, side: str, symbol: str, quantity: int, limit_price: float, option_type, exp_date: dt.datetime, strike, in_force: str='gtc'):
        raise Exception("Kraken does not support options.")

    # ------------- Helper methods ------------- #

    def get_data_from_kraken(self, symbol: str, multiplier: int, timespan: str, start: dt.datetime, end: dt.datetime) -> pd.DataFrame:
        if timespan == 'MIN':
            multiplier *= 1
        elif timespan == 'HR':
            multiplier *= 60
        elif timespan == 'DAY':
            multiplier *= 1440

        if is_crypto(symbol):
            temp_symbol = self.ticker_to_kraken(symbol)
        else:
            raise Exception("Kraken does not support stocks.")
        bars = self.get_results(self.api.query_public('OHLC', {'pair': temp_symbol, 'interval': multiplier, 'since': end.timestamp}))
        df = pd.DataFrame(bars[temp_symbol], columns=['timestamp', 'open', 'high', 'low', 'close', 'vwap', 'volume', 'count'])
        df = self._format_df(df, symbol)
        df = df.loc[start:end]
        return df

    def _format_df(self, df: pd.DataFrame, symbol: str):
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].astype(float)
        df.index = pd.to_datetime(df['timestamp'], unit='s', utc=True)
        df = df.drop(columns=['timestamp'])
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
            w.println("Create an account, go to your account dropdown > Security > API and create an API key.")
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

    def ticker_to_kraken(self, ticker: str):
        if not is_crypto(ticker):
            raise Exception("Kraken does not support stocks.")

        if ticker[1:] in self.crypto_ticker_to_kraken_names:
            # Currently Harvest supports trades for USD and not other currencies.
            kraken_ticker = self.crypto_ticker_to_kraken_names.get(ticker[1:]) + 'USD'
            asset_pairs = self.get_result(self.api.query_public('AssetPairs')).keys():
            if kraken_ticker in asset_pairs:
                return kraken_ticker
            else:
                raise Exception(f"{kraken_ticker} is not a valid asset pair.")
        else:
            raise Exception(f"Kraken does not support ticker {ticker}.")

    def get_result(self, response: Dict[str, Any]):
        """Given a kraken response from an endpoint, either raise an error if an
        error exists or return the data in the results key.
        """
        if len(response['error']) > 0:
            raise Exception('\n'.join(response['error']))
        return response['result']
