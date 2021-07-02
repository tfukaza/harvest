from harvest.algo import BaseAlgo as a
from docstring_parser import parse

# Import every function in BaseAlgo
# I feel like there should be a better way to do this...
# but for now it will do.

functions = [
    a.add_symbol,
    a.algo_init,
    a.await_buy,
    a.await_sell,
    a.bbands,
    a.bbands_raw,
    a.buy,
    a.buy_option,
    a.ema,
    a.get_account_buying_power,
    a.get_account_equity,
    a.get_candle,
    a.get_candle_list,
    a.get_chain_data,
    a.get_chain_info,
    a.get_cost,
    a.get_date,
    a.get_datetime,
    a.get_option_market_data,
    a.get_price,
    a.get_price_list,
    a.get_quantity,
    a.get_returns,
    a.get_time,
    a.get_watch,
    a.remove_symbol,
    a.rsi,
    a.sell,
    a.sell_option,
    a.sma
]

for func in functions:
    doc = parse(func.__doc__)
    print([p.arg_name for p in doc.params])
