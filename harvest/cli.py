import os
import sys
import inspect
import argparse
import importlib.util

from os import listdir
from os.path import isfile, join

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
    default="yahoo",
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

# Directory with algos that you want to run, default is the current working directory.
start_parser.add_argument(
    "-d",
    "--directory",
    default=".",
    help="directory where algorithms are located",
)
start_parser.add_argument(
    "--debug", default=False, action=argparse.BooleanOptionalAction
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
    broker = streamer if args.streamer == args.broker else _get_broker(args.broker)
    debug = args.debug
    trader = LiveTrader(streamer=streamer, broker=broker, storage=storage, debug=debug)

    # Get the directories.
    directory = args.directory
    print(f"Searching directory {directory}")
    files = [fi for fi in listdir(directory) if isfile(join(directory, fi))]
    print(f"Found files {files}")
    # For each file in the directory...
    for f in files:
        names = f.split(".")
        # Filter out non-python files.
        if len(names) <= 1 or names[-1] != "py":
            continue
        name = "".join(names[:-1])

        # ...open it...
        with open(join(directory, f), "r") as algo_file:
            firstline = algo_file.readline()
            if firstline.find("HARVEST_SKIP") != -1:
                print(f"Skipping {f}")
                continue

        # ...load in the entire file and add the algo to the trader.
        algo_path = os.path.realpath(join(directory, f))
        spec = importlib.util.spec_from_file_location(name, algo_path)
        algo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(algo)
        # Iterate though the variables and if a variable is a subclass of BaseAlgo instantiate it and added to the trader.
        for algo_cls in inspect.getmembers(algo):
            k, v = algo_cls[0], algo_cls[1]
            if inspect.isclass(v) and v != BaseAlgo and issubclass(v, BaseAlgo):
                print(f"Found algo {k} in {f}, adding to trader")
                trader.add_algo(v())

    if not test:
        trader.start()


def visualize(args: argparse.Namespace):
    """
    Read a csv or pickle file created by Harvest with ohlc data and graph the data.
    :args: A Namespace object containing parsed user arguments.
    """
    import re
    import pandas as pd
    import mplfinance as mpf

    # Open the file using the appropriate parser.
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
        sys.exit(2)

    path = os.path.basename(args.path)
    # File names are asset {ticker name}@{interval}.{file format}
    file_search = re.search("^(@?[\w]+)@([\w]+).(csv|pickle)$", path)
    symbol, interval = file_search.group(1), file_search.group(2)
    open_price = df.iloc[0]["open"]
    close_price = df.iloc[-1]["close"]
    high_price = df["high"].max()
    low_price = df["low"].min()
    price_delta = close_price - open_price
    price_delta_precent = 100 % (price_delta / open_price)
    volume = df["volume"].sum()

    print(f"{symbol} at {interval}")
    print(f"open\t{open_price}")
    print(f"high\t{high_price}")
    print(f"low\t{low_price}")
    print(f"close\t{close_price}")
    print(f"price change\t{price_delta}")
    print(f"price change percentage\t{price_delta_precent}%")
    print(f"volume\t{volume}")
    mpf.plot(
        df,
        type="candle",
        style="charles",
        volume=True,
        show_nontrading=True,
        title=path,
    )


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
