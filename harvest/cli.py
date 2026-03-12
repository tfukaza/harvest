"""CLI entrypoint for Harvest."""

from __future__ import annotations

import argparse
import os
import re
import sys

from harvest.util.helper import debugger

parser = argparse.ArgumentParser(description="Harvest CLI")
subparsers = parser.add_subparsers(dest="command")

# Parser for starting Harvest.
start_parser = subparsers.add_parser("start")
start_parser.add_argument(
    "--config",
    default=None,
    help="reserved path for a future orchestrator configuration entrypoint",
)


# Parser for visualizing data.
visualize_parser = subparsers.add_parser("visualize")
visualize_parser.add_argument("path", help="path to harvest generated data file")


def main() -> None:
    """Parse command-line arguments and dispatch to subcommands."""
    args = parser.parse_args()

    if args.command == "start":
        start(args)
    elif args.command == "visualize":
        visualize(args)
    else:
        parser.print_help(sys.stderr)
        sys.exit(1)


def start(args: argparse.Namespace, test: bool = False) -> None:
    """Report that the legacy runtime-backed start flow has been removed.

    Args:
        args: Parsed command-line arguments.
        test: When true, raise a runtime error instead of exiting so tests can
            assert the current placeholder behavior.
    """

    message = (
        "The legacy 'harvest start' flow has been removed during the runtime refactor. "
        "Use the orchestrator path directly for now, for example 'uv run python examples/orchestrator_example.py'."
    )
    if args.config:
        message = f"{message} Config path received: {args.config}."

    if test:
        raise RuntimeError(message)

    print(message, file=sys.stderr)
    sys.exit(2)


def visualize(args: argparse.Namespace) -> None:
    """Read a Harvest data file and render a chart."""

    import mplfinance as mpf
    import pandas as pd

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
    file_search = re.search("^(@?[]+)@([]+).(csv|pickle)$", path)  # Temporary fix
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
if __name__ == "__main__":
    main()
