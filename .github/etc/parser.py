from harvest.algo import BaseAlgo as a
from harvest.trader import LiveTrader as t
from harvest.trader import BackTester as b
from docstring_parser import parse
import json

PATH = "./tmp"

a_func = [
    a.config,
    a.setup,
    a.main,
    a.buy,
    a.sell,
    a.get_option_market_data,
    a.get_option_chain,
    a.get_option_chain_info,
    a.ema,
    a.rsi,
    a.sma,
    a.bbands,
    a.get_account_buying_power,
    a.get_account_equity,
    a.get_asset_current_candle,
    a.get_asset_candle_list,
    a.get_asset_avg_cost,
    a.get_date,
    a.get_datetime,
    a.get_asset_current_price,
    a.get_asset_price_list,
    a.get_asset_quantity,
    a.get_asset_profit_percent,
    a.get_time,
    a.get_account_stock_positions,
    a.get_account_crypto_positions,
    a.get_account_option_positions,
    a.get_watchlist
]

t_func = [
    t.start,
    t.set_symbol,
    t.set_algo,
]

b_func = [
    b.start,
]


def generate_json(class_name, functions):
    data = []
    for func in functions:

        doc = parse(func.__doc__)

        arg_names = ["self"]
        arg_names.extend([p.arg_name for p in doc.params])
        data.append(
            {
                "function": func.__name__ + "(" + ", ".join(arg_names) + ")",
                "index": func.__name__,
                "short_description": doc.short_description,
                "long_description": doc.long_description,
                "params": [
                    {
                        "name": par.arg_name,
                        "type": par.type_name,
                        "desc": par.description[0 : par.description.find("defaults")],
                        "default": par.default,
                        "optional": par.is_optional,
                    }
                    for par in doc.params
                ],
                "returns": doc.returns.description if not doc.returns == None else "",
                "raises": [
                    {
                        "type": par.type_name,
                        "desc": par.description,
                    }
                    for par in doc.raises
                ],
            }
        )

    with open(f"{PATH}/{class_name}.json", "w") as f:
        json.dump(data, f)


generate_json(a.__name__, a_func)
generate_json(t.__name__, t_func)
generate_json(b.__name__, b_func)
