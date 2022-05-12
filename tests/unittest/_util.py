from harvest.trader.trader import LiveTrader
import os
import functools

from harvest.algo import BaseAlgo


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

    t = LiveTrader(streamer=streamer, broker=broker, debug=True)
    t.set_symbol(symbols)
    if init_algos:
        for a in init_algos:
            t.add_algo(a)
    else:
        t.add_algo(EmptyAlgo())
    t.start_streamer = False
    t.skip_init = True

    t._init_param_streamer_broker(interval, [])
    stream = t.streamer
    broker = t.broker
    t.start(sync=False)

    return t, stream, broker


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
