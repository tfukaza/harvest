import datetime as dt
import functools
import os

from harvest.algo import BaseAlgo
from harvest.trader.trader import BrokerHub

"""
For testing purposes, assume:
- Current day is September 15th, 2008
- Current time is 10:00 AM
- Current timezone is US/Eastern
"""


def mock_get_local_timezone():
    """
    Return the US/Eastern timezone
    """
    return dt.timezone(dt.timedelta(hours=-4))


def mock_utc_current_time():
    """
    Return the current time in UTC timezone
    """
    d = dt.datetime(2008, 9, 15, 10, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=-4)))
    return d.astimezone(dt.timezone.utc)


def create_trader_and_api(
    streamer=None,
    broker=None,
    interval=None,
    symbols=None,
    init_algos=None,
):
    # Empty algo for testing purposes
    class EmptyAlgo(BaseAlgo):
        pass

    bh = BrokerHub(data_broker=streamer, trade_broker=broker, debug=True)
    bh.set_symbol(symbols)
    if init_algos:
        for a in init_algos:
            bh.add_algo(a)
    else:
        bh.add_algo(EmptyAlgo())
    bh.start_data_broker = False
    bh.skip_init = True

    bh._init_param_streamer_broker(interval, [])
    stream = bh.data_broker_ref
    broker = bh.trade_broker_ref
    bh.start(sync=False)

    return bh, stream, broker


# Wrapper to delete save files after test
def delete_save_files(path):
    def wrapper_outer(func):
        @functools.wraps(func)
        def wrapper_inner(*args, **kwargs):
            save_path = os.path.join(path, "save")
            if os.path.exists(save_path):
                os.remove(save_path)
            r = func(*args, **kwargs)
            if os.path.exists(save_path):
                os.remove(save_path)
            return r

        return wrapper_inner

    return wrapper_outer
