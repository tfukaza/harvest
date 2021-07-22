# Builtins
import datetime as dt
from typing import Any, Dict, List, Tuple
from logging import critical, error, info, warning, debug

# External libraries
import pandas as pd
import yaml

# Submodule imports
from harvest.api._base import API
from harvest.utils import *

class PaperBroker(API):
    """DummyBroker, as its name implies, is a dummy broker class that can 
    be useful for testing algorithms. When used as a streamer, it will return
    randomly generated prices. When used as a broker, it paper trades.
    """

    interval_list = ['1MIN', '5MIN', '15MIN', '30MIN', '1DAY']

    def __init__(self, account_path: str=None):
        
        self.stocks = []
        self.options = []
        self.cryptos = []
        self.orders = []

        self.equity = 1000000.0
        self.cash = 1000000.0
        self.buying_power = 1000000.0
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
        super().setup(watch, interval, interval, trader, trader_main)

    # -------------- Streamer methods -------------- #

    def fetch_price_history(self,
        symbol: str,
        interval: str,
        start: dt.datetime=None, 
        end: dt.datetime=None
        ) -> pd.DataFrame:
        raise Exception("Not implemented")
    
    def fetch_chain_info(self, symbol: str):
        raise Exception("Not implemented")
    
    def fetch_chain_data(self, symbol: str):
        raise Exception("Not implemented")
    
    def fetch_option_market_data(self, symbol: str):
        raise Exception("Not implemented")
    
    # ------------- Broker methods ------------- #

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
            price = self.streamer.fetch_price_history(sym, self.interval, dt.datetime.now() - dt.timedelta(days=7), dt.datetime.now())[sym]['close'][-1]
        else:
            price = self.trader.storage.load(sym, self.interval)[sym]['close'][-1]

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
        """
        Calculates the total worth of the broker by adding together the 
        worth of all stocks, cryptos, options and cash in the broker.
        """
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
            price = self.streamer.fetch_option_market_data(occ_sym)['price']
        else:
            price = self.trader.streamer.fetch_option_market_data(occ_sym)['price']
            
        qty = ret['quantity']
       
        # If order has been filled, simulate asset buy/sell
        if ret['status'] == 'filled':
            pos = next((r for r in self.options if r['occ_symbol'] == occ_sym), None)
            if ret['side'] == 'buy':
                # If asset already exists, buy more. If not, add a new entry
                if pos == None:
                    sym, date, option_type, strike = self.occ_to_data(occ_sym)
                    self.options.append({
                        'symbol': sym,
                        'occ_symbol': ret['occ_symbol'],
                        'avg_price': price,
                        'quantity': ret['quantity'],
                        "multiplier": 100,
                        "exp_date": date,
                        "strike_price": strike,
                        "type": option_type
                    })
                else:
                    pos['avg_price'] = (pos['avg_price']*pos['quantity'] + price*qty)/(qty+pos['quantity'])
                    pos['quantity'] = pos['quantity'] + qty 
        
                self.cash -= price * qty * 100
                self.buying_power -= price * qty * 100
                print(f"After BUY: {self.buying_power}")
            else:
                if pos == None:
                    raise Exception(f"Cannot sell {sym}, is not owned")
                pos['quantity'] = pos['quantity'] - qty
                print(f"current:{self.buying_power}")
                self.cash += price*qty*100
                self.buying_power += price*qty*100
                print(f"Made {sym} {occ_sym} {qty} {price}: {self.buying_power}")
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
    
    # --------------- Methods for Trading --------------- #

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


