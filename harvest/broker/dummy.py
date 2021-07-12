# Builtins
import datetime as dt
import random
import re
import queue
from typing import Any, Dict, List, Tuple
import logging
from logging import critical, error, info, warning, debug

# External libraries
import pandas as pd
import yaml
import pytz

# Submodule imports
import harvest.broker._base as base
from harvest.utils import is_crypto
from harvest.storage.base import BaseStorage

class DummyBroker(base.BaseBroker):
    """DummyBroker, as its name implies, is a dummy broker class that can 
    be useful for testing algorithms. When used as a streamer, it will return
    randomly generated prices. When used as a broker, it paper trades.
    """

    interval_list = ['1MIN', '5MIN', '15MIN', '30MIN', '1DAY']

    def __init__(self, account_path: str=None):
        super().__init__()

        self.stocks = []
        self.options = []
        self.cryptos = []
        self.orders = []

        self.equity = 100000.0
        self.cash = 100000.0
        self.buying_power = 100000.0
        self.multiplier = 1
        self.id = 0

        if account_path:
            with open(account_path, 'r') as f:
                account = yaml.safe_load(f) 
                self.equity = account['equity']
                self.cash = account['cash']
                self.buying_power = account['buying_power']
                self.multiplier = account['multiplier']

                for stock in account['stocks']:
                    self.stocks.append(stock)

                for crypto in account['cryptos']:
                    self.cryptos.append(crypto)


    def setup(self, watch: List[str], interval, trader=None, trader_main=None):
        if interval not in self.interval_list:
            raise Exception(f'Invalid interval {interval}')

        super().setup(watch, interval, interval, trader, trader_main)

    @base.BaseBroker.main_wrap
    def main(self):
        df_dict = {}
        df_dict.update(self.fetch_latest_stock_price())
        df_dict.update(self.fetch_latest_crypto_price())
      
        return df_dict

    def has_interval(self, interval: str):
        return True

    def _generate_fake_stock_data(self):
        open_s = random.uniform(2, 1000)
        volume = random.randint(1, 1e7)

        while True: 
            open_s = max(open_s + random.uniform(-1, 1), 0.001)
            close = open_s + random.uniform(-1, 1)
            low = max(min(open_s, close) - random.uniform(0.001, 1), 0)
            high = max(open_s, close) + random.uniform(0.001, 1)
            volume = max(volume + random.randint(-5, 5), 1)  
            yield open_s, high, low, close, volume


    def fetch_price_history(self,
        start: dt.datetime, 
        end: dt.datetime, 
        interval: str='1MIN',
        symbol: str = None) -> pd.DataFrame:

        interval_parsed = re.search('([0-9]*)([A-Z]*)', interval)
        if interval_parsed:
            value = interval_parsed.group(1)
            unit = interval_parsed.group(2)
            
            if unit == 'MIN':
                interval = dt.timedelta(minutes=int(value))
            elif unit == 'HR':
                interval = dt.timedelta(hours=int(value))
            elif unit == 'DAY':
                interval = dt.timedelta(days=int(value))
            else:
                print('Error')

        times = []
        current = start

        stock_gen = self._generate_fake_stock_data()
        open_s = []
        high = []
        low = []
        close = []
        volume = []

        # Fake the data 
        while current < end + interval:
            times.append(current.replace(tzinfo=None))
            current += interval

            o, h, l, c, v = next(stock_gen)
            open_s.append(o)
            high.append(h)
            low.append(l)
            close.append(c)
            volume.append(v)

        if not symbol:
            symbol = 'DUMMY'            

        d = {
            'date': times,
            'open': open_s,
            'high': high,
            'low': low, 
            'close': close,
            'volume': volume
        }

        results = pd.DataFrame(data=d).set_index('date')
        open_time = dt.time(hour=13, minute=30)
        close_time = dt.time(hour=20)

        results.index = times
        results.index.rename('date', inplace=True)

        results = results.loc[(open_time < results.index.time) & (results.index.time < close_time)]
        results = results[(results.index.dayofweek != 5) & (results.index.dayofweek != 6)]

        return results

    def fetch_latest_stock_price(self) -> Dict[str, pd.DataFrame]:
        results = {}
        last = dt.datetime.now() - dt.timedelta(days=7)
        today = dt.datetime.now()
        for symbol in self.watch:
            if not is_crypto(symbol):
                results[symbol] = self.fetch_price_history(last, today, self.interval, symbol).iloc[[-1]]
        return results
        
    def fetch_latest_crypto_price(self) -> Dict[str, pd.DataFrame]:
        results = {}
        last = dt.datetime.now() - dt.timedelta(days=7)
        today = dt.datetime.now()
        for symbol in self.watch:
            if is_crypto(symbol):
                results[symbol] = self.fetch_price_history(last, today, self.interval, symbol).iloc[[-1]]
        return results
    
    def fetch_stock_positions(self) -> List[Dict[str, Any]]:
        return self.stocks

    def fetch_option_positions(self) -> List[Dict[str, Any]]:
        return self.options

    def fetch_crypto_positions(self) -> List[Dict[str, Any]]:
        return self.cryptos
    
    def update_option_positions(self, positions) -> List[Dict[str, Any]]:
        for r in self.options:
            occ_sym = r['occ_symbol']

            if self.trader is None:
                price = self.fetch_option_market_data(occ_sym)['price']
            else:
                price = self.trader.streamer.fetch_option_market_data(occ_sym)['price']

            r["current_price"] = price
            r["market_value"] = price*r['quantity']*100
            r["cost_basis"] = r['avg_price']*r['quantity']*100

    def fetch_account(self) -> Dict[str, Any]:
        self.equity = self._calc_equity()
        return {
            'equity': self.equity,
            'cash': self.cash,
            'buying_power': self.buying_power,
            'multiplier': self.multiplier
        }
    
    def fetch_stock_order_status(self, id: int) -> Dict[str, Any]:
        ret = next(r for r in self.orders if r['id'] == id)
        sym = ret['symbol']

        if self.trader is None:
            price = self.fetch_price_history(dt.datetime.now() - dt.timedelta(days=7), dt.datetime.now(), self.interval, sym).iloc[-1]['close']
        else:
            price = self.trader.queue.get_last_symbol_interval_price(sym, self.interval, 'close')

        qty = ret['quantity']
       
        # If order has been filled, simulate asset buy/sell
        if ret['status'] == 'filled':
            if is_crypto(ret['symbol']): 
                lst = self.cryptos
            else:
                lst = self.stocks

            pos = next((r for r in lst if r['symbol'] == sym), None)
            if ret['side'] == 'buy':
                # If asset already exists, buy more. If not, add a new entry
                if pos == None:
                    lst.append({
                        'symbol': sym,
                        'avg_price': price,
                        'quantity': qty
                    })
                else:
                    pos['avg_price'] = (pos['avg_price']*pos['quantity'] + price*qty)/(qty+pos['quantity'])
                    pos['quantity'] = pos['quantity'] + qty 
        
                self.cash -= price * qty 
                self.buying_power -= price * qty 
            else:
                if pos == None:
                    raise Exception(f"Cannot sell {sym}, is not owned")

                pos['quantity'] = pos['quantity'] - qty
                if pos['quantity'] < 1e-8:
                    lst.remove(pos)
                self.cash += price * qty 
                self.buying_power += price * qty 
            
            self.equity = self._calc_equity()
            
            ret_1 = ret.copy()
            self.orders.remove(ret)
            ret = ret_1

        debug(f"Returning status: {ret}")
        debug(f"Positions:\n{self.stocks}\n=========\n{self.cryptos}")
        debug(f"Equity:{self._calc_equity()}")

        return ret

    def _calc_equity(self):
        e = 0
        for asset in self.stocks + self.cryptos + self.options:
            add = asset['avg_price'] * asset['quantity']
            if 'multiplier' in asset:
                add = add * asset['multiplier']
            e += add
        e += self.cash
        return e

    def fetch_option_order_status(self, id: int) -> Dict[str, Any]:
        ret = next(r for r in self.orders if r['id'] == id)
        sym = ret['symbol']
        occ_sym = ret['occ_symbol']

        if self.trader is None:
            price = self.fetch_option_market_data(occ_sym)['price']
        else:
            price = self.trader.streamer.fetch_option_market_data(occ_sym)['price']
            
        qty = ret['quantity']
       
        # If order has been filled, simulate asset buy/sell
        if ret['status'] == 'filled':
            pos = next((r for r in self.options if r['occ_symbol'] == occ_sym), None)
            if ret['side'] == 'buy':
                # If asset already exists, buy more. If not, add a new entry
                if pos == None:
                    sym, date, option_type, price = self.occ_to_data(occ_sym)
                    self.options.append({
                        'symbol': sym,
                        'occ_symbol': ret['occ_symbol'],
                        'avg_price': price,
                        'quantity': ret['quantity'],
                        "multiplier": 100,
                        "exp_date": date,
                        "strike_price": price,
                        "type": option_type
                    })
                else:
                    pos['avg_price'] = (pos['avg_price']*pos['quantity'] + price*qty)/(qty+pos['quantity'])
                    pos['quantity'] = pos['quantity'] + qty 
        
                self.cash -= price * qty * 100
                self.buying_power -= price * qty * 100
            else:
                if pos == None:
                    raise Exception(f"Cannot sell {sym}, is not owned")

                pos['quantity'] = pos['quantity'] - qty
                self.cash += price*qty*pos['multiplier'] 
                self.buying_power += price*qty*pos['multiplier'] 
                if pos['quantity'] < 1e-8:
                    self.options.remove(pos)
                
            
            self.equity = self._calc_equity()
            
            ret_1 = ret.copy()
            self.orders.remove(ret)
            ret = ret_1

        debug(f"Returning status: {ret}")
        debug(f"Positions:\n{self.stocks}\n=========\n{self.cryptos}")
        debug(f"Equity:{self._calc_equity()}")

        return ret
    
    def fetch_crypto_order_status(self, id: int) -> Dict[str, Any]:
        return self.fetch_stock_order_status(id)
    
    def fetch_order_queue(self) -> List[Dict[str, Any]]:
        return self.orders

    def fetch_chain_info(self, symbol: str):
        pass
    
    def fetch_chain_data(self, symbol: str):
        pass
    
    def fetch_option_market_data(self, symbol: str):
        price = random.uniform(2, 1000)

        return {
            'price': price,
            'ask': price, 
            'bid': price,
        }
    
    ########## Function for order operations ########### 

    def order_limit(self, 
        side: str, 
        symbol: str,
        quantity: float, 
        limit_price: float, 
        in_force: str='gtc', 
        extended: bool=False, 
        ):
        # In this broker, all orders are filled immediately. 
        if not is_crypto(symbol):
            data = {
                'type': 'STOCK',
                'symbol': symbol,
                'quantity': quantity,
                'filled_qty': quantity,
                'id': self.id,
                'time_in_force': in_force,
                'status': 'filled',
                'side': side
            }
        else:
            data = {
                'type': 'CRYPTO',
                'symbol': symbol,
                'quantity': quantity,
                'filled_qty': quantity,
                'id': self.id,
                'time_in_force': in_force,
                'status': 'filled',
                'side': side
            }

        self.orders.append(data)
        self.id += 1
        ret = {
            'type': data['type'],
            'id': data['id'],
            'symbol': data['symbol']
        }
        return ret
    
    def order_option_limit(self, side: str, symbol: str, quantity: float, limit_price: float, type: str, 
        exp_date: dt.datetime, strike: float, in_force: str='gtc'):
       
        data = {
            'type': 'OPTION',
            'symbol': symbol,
            'quantity': quantity,
            'filled_qty': 0,
            'id': self.id,
            'time_in_force': in_force,
            'status': 'filled',
            'side': side,

            'occ_symbol': self.data_to_occ(symbol, exp_date, type, strike)
        }
      
        self.orders.append(data)
        self.id += 1
        ret = {
            'type': data['type'],
            'id': data['id'],
            'symbol': data['symbol']
        }
        return ret


