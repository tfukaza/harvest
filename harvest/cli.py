import os
import sys
import inspect
import argparse
import importlib.util

# Lambda functions cannot raise exceptions so using higher order functions.
def _raise(e):
    def raise_helper():
        raise e

    return raise_helper


from harvest.storage.base_storage import BaseStorage
from harvest.storage.csv_storage import CSVStorage
from harvest.storage.pickle_storage import PickleStorage

# For imports that have extra dependencies, surpress the import error unless the user specifics that resource and does not have the depenedencies.
try:
    from harvest.storage.database_storage import DBStorage
except ModuleNotFoundError as e:
    DBStorage = _raise(e)

from harvest.api.dummy import DummyStreamer
from harvest.api.yahoo import YahooStreamer
from harvest.api.polygon import PolygonStreamer
from harvest.api.paper import PaperBroker

try:
    from harvest.api.robinhood import Robinhood
except ModuleNotFoundError as e:
    Robinhood = _raise(e)
try:
    from harvest.api.alpaca import Alpaca
except ModuleNotFoundError as e:
    Alpaca = _raise(e)
try:
    from harvest.api.kraken import Kraken
except ModuleNotFoundError as e:
    Kraken = _raise(e)
try:
    from harvest.api.webull import Webull
except ModuleNotFoundError as e:
    Webull = _raise(e)

from harvest.trader import LiveTrader
from harvest.algo import BaseAlgo

storages = {
    "memory": BaseStorage,
    "csv": CSVStorage,
    "pickle": PickleStorage,
    "db": DBStorage,
}

streamers = {
    "dummy": DummyStreamer,
    "yahoo": YahooStreamer,
    "polygon": PolygonStreamer,
    "robinhood": Robinhood,
    "alpaca": Alpaca,
    "kraken": Kraken,
    "webull": Webull,
}

brokers = {
    "paper": PaperBroker,
    "robinhood": Robinhood,
    "alpaca": Alpaca,
    "kraken": Kraken,
    "webull": Webull,
}

parser = argparse.ArgumentParser(description="Harvest CLI")
subparsers = parser.add_subparsers(dest="command")

# Parser for starting harvest
start_parser = subparsers.add_parser("start")
start_parser.add_argument(
    "-o",
    "--storage",
    default="memory",
    help="the way to store asset data",
    choices=list(storages.keys()),
)
start_parser.add_argument(
    "-s",
    "--streamer",
    default="dummy",
    help="fetches asset data",
    choices=list(streamers.keys()),
)
start_parser.add_argument(
    "-b",
    "--broker",
    default="paper",
    help="buys and sells assets on your behalf",
    choices=list(brokers.keys()),
)
start_parser.add_argument(
    "algos", nargs="+", help="paths to algorithms you want to run"
)


# Parser for visualing data
visualize_parser = subparsers.add_parser("visualize")
visualize_parser.add_argument("path", help="path to harvest generated data file")


def main():
    """
    Entrypoint which parses the command line arguments. Calls subcommands based on which subparser was used.
    :args: A Namespace object containing parsed user arguments.
    """
    args = parser.parse_args()

    # Handles the start command
    if args.command == "start":
        start(args)
    elif args.command == "visualize":
        visualize(args)
    # Show help if case not found
    else:
        parser.print_help(sys.stderr)
        sys.exit(1)


def start(args: argparse.Namespace, test: bool = False):
    """
    Starts the Harvest LiveTrader with the given storage, streamer, broker, and algos specified.
    :args: A Namespace object containing parsed user arguments.
    :test: True if we are testing so that we can exit this function cleanly.
    """
    storage = _get_storage(args.storage)
    streamer = _get_streamer(args.streamer)
    broker = _get_broker(args.broker)
    trader = LiveTrader(streamer=streamer, broker=broker, storage=storage)
    # algos is a list of paths to files that have user defined algos
    for algo_path in args.algos:
        # get the file name without the `.py`
        module = os.path.basename(algo_path)[:-3]
        # load in the entire file
        algo_path = os.path.realpath(algo_path)
        spec = importlib.util.spec_from_file_location(module, algo_path)
        algo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(algo)
        # iterate though the variables and if a variable is a subclass of BaseAlgo instantiate it and added to the trader
        for algo_cls in dir(algo):
            if inspect.isclass(algo_cls) and issubclass(algo_cls, BaseAlgo):
                trader.set_algo(algo_cls())

    if not test:
        trader.start()


def visualize(args: argparse.Namespace):
    import re
    import pandas as pd
    import mplfinance as mpf

    if args.path.endswith(".csv"):
        df = pd.read_csv(args.path)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df.set_index("timestamp", inplace=True)
    elif args.path.endswith(".pickle"):
        df = pd.read_pickle(args.path)
    else:
        print("Invalid file extension, expecting .csv or .pickle.")
        sys.exit(1)

    if df.empty:
        print(f"No data found in {args.path}.")

    path = os.path.basename(args.path)
    file_search = re.search("^(@?[\w]+)@([\w]+).(csv|pickle)$", path)
    symbol, interval = file_search.group(1), file_search.group(2)
    open_price = df.iloc[0]["open"]
    close_price = df.iloc[-1]["close"]
    high_price = df["high"].max()
    low_price = df["low"].min()

    print(f"{symbol} at {interval}")
    print("open", open_price)
    print("high", high_price)
    print("low", low_price)
    print("close", close_price)
    print("price change", close_price - open_price)
    mpf.plot(df, type="candle", volume=True, show_nontrading=True)


def _get_storage(storage: str):
    """
    Returns the storage instance specified by the user.
    :storage: The type of storage to be instantiated.
    """
    storage_cls = storages.get(storage)
    if storage_cls is None:
        raise ValueError(
            f"Invalid storage option: {storage}, valid options are {storages.keys()}"
        )
    return storage_cls()


def _get_streamer(streamer):
    """
    Returns the storage instance specified by the user.
    :streamer: The type of streamer to be instantiated.
    """
    streamer_cls = streamers.get(streamer)
    if streamer_cls is None:
        raise ValueError(
            f"Invalid streamer option: {streamer}, valid options are {streamers.keys()}"
        )
    return streamer_cls()


def _get_broker(broker):
    """
    Returns the storage instance specified by the user.
    :broker: The type of broker to be instantiated.
    """
    broker_cls = brokers.get(broker)
    if broker_cls is None:
        raise ValueError(
            f"Invalid broker option: {broker}, valid options are: {brokers.keys()}"
        )
    return broker_cls()


if __name__ == "__main__":
    main()
