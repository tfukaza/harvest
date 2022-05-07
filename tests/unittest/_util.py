from harvest.trader.trader import LiveTrader


def create_trader_and_api(
    streamer=None,
    broker=None,
    interval=None,
    symbols=None,
):

    t = LiveTrader(streamer=streamer, broker=broker, debug=True)
    t.set_symbol(symbols)
    t.start_streamer = False
    t.skip_init = True

    t._init_param_streamer_broker("1MIN", [])
    stream = t.streamer
    broker = t.broker
    t.start(sync=False)

    return t, stream, broker
