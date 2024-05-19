import os
import sys
import inspect
import argparse
from importlib.util import spec_from_file_location, module_from_spec
from importlib import import_module

from os import listdir
from os.path import isfile, join
from typing import Callable


# Lambda functions cannot raise exceptions so using higher order functions.
def _raise(e) -> Callable:
    def raise_helper():
        raise e

    return raise_helper


from harvest.utils import debugger
from harvest.util.factory import storages, streamers, brokers
from harvest.algo import BaseAlgo

parser = argparse.ArgumentParser(description="Harvest CLI")
subparsers = parser.add_subparsers(dest="command")

# Parser for starting harvest
start_parser = subparsers.add_parser("start")
start_parser.add_argument(
    "-o",
    "--storage",
    default="base",
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
    default="streamer",
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

from rich.console import Console
from rich.tree import Tree
from rich.padding import Padding


def main() -> None:
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


def start(args: argparse.Namespace, test: bool = False) -> None:
    """
    Starts the Harvest LiveTrader with the given storage, streamer, broker, and algos specified.
    :args: A Namespace object containing parsed user arguments.
    :test: True if we are testing so that we can exit this function cleanly.
    """
    storage = args.storage
    streamer = args.streamer
    broker = args.broker
    debug = args.debug

    from harvest.trader import BrokerHub

    trader = BrokerHub(streamer=streamer, broker=broker, storage=storage, debug=debug)

    console = Console()
    console.print(f"> [bold green]Welcome to Harvest[/bold green]")

    with console.status("[bold green] Loading... [/bold green]") as status:

        # Get the directories.
        directory = args.directory
        console.print(f"- Searching directory [bold cyan]{directory}[/bold cyan] 🔎")
        dir_tree = Tree(f"🗂️  {directory}")
        files = [fi for fi in listdir(directory) if isfile(join(directory, fi))]
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
                    dir_tree.add(f"⏩ {f} (Skipped)")
                    continue
            py_file = dir_tree.add(f"📄 {f}")

            # ...load in the entire file and add the algo to the trader.
            algo_path = os.path.realpath(join(directory, f))
            spec = spec_from_file_location(name, algo_path)
            algo = module_from_spec(spec)
            spec.loader.exec_module(algo)
            # Iterate though the variables and if a variable is a subclass of BaseAlgo instantiate it and added to the trader.
            for algo_cls in inspect.getmembers(algo):
                k, v = algo_cls[0], algo_cls[1]
                if inspect.isclass(v) and v != BaseAlgo and issubclass(v, BaseAlgo):
                    py_file.add(f"[green]{k}[/green]")
                    trader.add_algo(v())
        algo_count = len(trader.algo)
        if algo_count == 0:
            console.print("⛔ No algorithms found!")
            sys.exit(1)

        dir_pad = Padding(dir_tree, (0, 4))
        console.print(dir_pad)
        console.print(
            f"- Found {len(trader.algo)} algo{'' if algo_count == 1 else 's'} 🎉"
        )
        # status.stop()
    console.print(f"> [bold green]Finished loading algorithms[/bold green]")

    if not test:
        # console.print(f"Starting trader")
        trader.start()


def visualize(args: argparse.Namespace) -> None:
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
        debugger.error("⛔ Invalid file extension, expecting .csv or .pickle.")
        sys.exit(1)

    if df.empty:
        debugger.error(f"⛔ No data found in {args.path}.")
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

    debugger.info(f"{symbol} at {interval}")
    debugger.info(f"open\t{open_price}")
    debugger.info(f"high\t{high_price}")
    debugger.info(f"low\t{low_price}")
    debugger.info(f"close\t{close_price}")
    debugger.info(f"price change\t{price_delta}")
    debugger.info(f"price change percentage\t{price_delta_precent}%")
    debugger.info(f"volume\t{volume}")
    mpf.plot(
        df,
        type="candle",
        style="charles",
        volume=True,
        show_nontrading=True,
        title=path,
    )


def string_to_class(class_string: str) -> type:
    return getattr(sys.modules[__name__], class_string, None)


# def _get_storage(storage: str) -> str:
#     """
#     Returns the storage instance specified by the user.
#     :storage: The type of storage to be instantiated.
#     """
#     return storage


# def _get_streamer(streamer: str) -> str:
#     """
#     Returns the streamer instance specified by the user.
#     :streamer: The type of streamer to be instantiated.
#     """
#     return streamer


# def _get_broker(broker: str, streamer: str, streamer_cls: str) -> str:
#     """
#     Returns the broker instance specified by the user.
#     :broker: The type of broker to be instantiated.
#     """
#     return broker


if __name__ == "__main__":
    main()
