# Builtins
import re
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

    def __init__(self, account_path: str=None, commission_fee=0):
        """
        :commission_fee: When this is a number it is assumed to be a flat price
            on all buys and sells of assets. When this is a string formatted as
            'XX%' then it is assumed that commission fees are that percent of the
            original cost of the buy or sell. When commission fee is a dictionary
            with the keys 'buy' and 'sell' you can specify different commission 
            fees when buying and selling assets. The values must be numbers or 
            strings formatted as 'XX%'.
        """
        
        self.stocks = []
        self.options = []
        self.cryptos = []
        self.orders = []

        self.equity = 1000000.0
        self.cash = 1000000.0
        self.buying_power = 1000000.0
        self.multiplier = 1
        self.commission_fee = commission_fee
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
        original_price = price * qty
        # If order is open, simulate asset buy/sell if possible
        if ret['status'] == 'open':
            if is_crypto(ret['symbol']): 
                lst = self.cryptos
            else:
                lst = self.stocks

            pos = next((r for r in lst if r['symbol'] == sym), None)
            if ret['side'] == 'buy':
                # Check to see if user has enough funds to buy the stock
                actual_price = self.apply_commission(original_price, self.commission_fee, 'sell')
                if self.buying_power < actual_price:
                    warning(f"""Not enough buying power.\n Total price ({actual_worth}) exceeds buying power {self.buy_power}.\n Reduce purchase quantity or increase buying power.""")
                # Check to see the price does not exceed the limit price
                elif ret['limit_price'] < price:
                    limit_price = ret['limit_price']
                    info(f'Limit price for {sym} is less than current price ({limit_price} < {price}).')
                else:
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
            
                    self.cash -= actual_price
                    self.buying_power -= actual_price
                    ret_1 = ret.copy()
                    self.orders.remove(ret)
                    ret = ret_1
                    ret['status'] = 'filled'
            else:
                if pos == None:
                    raise Exception(f"Cannot sell {sym}, is not owned")

                pos['quantity'] = pos['quantity'] - qty
                if pos['quantity'] < 1e-8:
                    lst.remove(pos)
                actual_worth = self.apply_commission(original_price, self.commission_fee, 'sell')
                self.cash += actual_worth
                self.buying_power += actual_worth
                ret_1 = ret.copy()
                self.orders.remove(ret)
                ret = ret_1
                ret['status'] = 'filled'
            
            self.equity = self._calc_equity() 

        debug(f"Returning status: {ret}")
        debug(f"Positions:\n{self.stocks}\n=========\n{self.cryptos}")
        debug(f"Equity:{self._calc_equity()}")

        return ret

    def fetch_option_order_status(self, id: int) -> Dict[str, Any]:
        ret = next(r for r in self.orders if r['id'] == id)
        sym = ret['symbol']
        occ_sym = ret['occ_symbol']

        if self.trader is None:
            price = self.streamer.fetch_option_market_data(occ_sym)['price']
        else:
            price = self.trader.streamer.fetch_option_market_data(occ_sym)['price']
            
        qty = ret['quantity']
        original_price = price * qty
        # If order has been opened, simulate asset buy/sell
        if ret['status'] == 'open':
            pos = next((r for r in self.options if r['occ_symbol'] == occ_sym), None)
            if ret['side'] == 'buy':
                # Check to see if user has enough funds to buy the stock
                actual_price = self.apply_commission(original_price, self.commission_fee, 'buy')
                if self.buying_power < actual_price:
                    warning(f"""Not enough buying power.\n Total price ({actual_price}) exceeds buying power {self.buy_power}.\n Reduce purchase quantity or increase buying power.""")
                elif ret['limit_price'] < price:
                    limit_price = ret['limit_price']
                    info(f'Limit price for {sym} is less than current price ({limit_price} < {price}).')
                else:
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

                    self.cash -= actual_price
                    self.buying_power -= actual_price
                    ret['status'] = 'filled'
                    debug(f"After BUY: {self.buying_power}")
                    ret_1 = ret.copy()
                    self.orders.remove(ret)
                    ret = ret_1
            else:
                if pos == None:
                    raise Exception(f"Cannot sell {sym}, is not owned")
                pos['quantity'] = pos['quantity'] - qty
                debug(f"current:{self.buying_power}")
                actual_price = self.apply_commission(original_price, self.commission_fee, 'sell')
                self.cash += actual_price
                self.buying_power += actual_price
                debug(f"Made {sym} {occ_sym} {qty} {price}: {self.buying_power}")
                if pos['quantity'] < 1e-8:
                    self.options.remove(pos)
                ret['status'] = 'filled'
                ret_1 = ret.copy()
                self.orders.remove(ret)
                ret = ret_1
                
            
            self.equity = self._calc_equity()

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

        if not is_crypto(symbol):
            data = {
                'type': 'STOCK',
                'symbol': symbol,
                'quantity': quantity,
                'filled_qty': quantity,
                'limit_price': limit_price,
                'id': self.id,
                'time_in_force': in_force,
                'status': 'open',
                'side': side
            }
        else:
            data = {
                'type': 'CRYPTO',
                'symbol': symbol,
                'quantity': quantity,
                'filled_qty': quantity,
                'limit_price': limit_price,
                'id': self.id,
                'time_in_force': in_force,
                'status': 'open',
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
            'status': 'open',
            'side': side,
            'limit_price': limit_price,
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

    # ------------- Helper methods ------------- #

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

    def apply_commission(self, inital_price: float, commission_fee, side: str) -> float:
        if side == 'buy':
            f = lambda a, b: a + b
        elif side == 'sell':
            f = lambda a, b: a - b

        if type(commission_fee) in (int, float):
            return f(inital_price, commission_fee)
        elif type(commission_fee) is str:
            pattern = r'([0-9]+\.?[0-9]*)\%'
            match = re.fullmatch(pattern, commission_fee)
            if match is not None:
                commission_fee = inital_price * 0.01 * float(match.group(1))
                return f(inital_price, commission_fee)
            raise Exception(f'`commission_fee` {commission_fee} not valid, must match this regex expression: {pattern}')
        elif type(commission_fee) is dict:
            return self.apply_commission(inital_price, commission_fee[side], side)