"""CLI entrypoint for Harvest."""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Callable
from typing import Any, TextIO

from harvest.harvest_agent import HarvestAgent, HarvestAgentConfig, DEFAULT_SYSTEM_PROMPT
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


agent_parser = subparsers.add_parser("agent")
agent_parser.add_argument(
    "--model",
    default=None,
    help="LiteLLM model name (e.g. anthropic/claude-sonnet-4-20250514, openai/gpt-4o)",
)
agent_parser.add_argument(
    "--system-prompt",
    default=DEFAULT_SYSTEM_PROMPT,
    help="system prompt used for the conversation",
)
agent_parser.add_argument(
    "--message",
    default=None,
    help="optional one-shot message instead of interactive chat mode",
)
agent_parser.add_argument(
    "--session",
    default=None,
    help="session name for conversation persistence logging",
)
agent_parser.add_argument(
    "--no-persist",
    action="store_true",
    default=False,
    help="skip conversation persistence entirely",
)
agent_parser.add_argument(
    "--context-limit",
    type=int,
    default=None,
    help="model context window size in tokens (default: 128000)",
)
agent_parser.add_argument(
    "--compaction-threshold",
    type=float,
    default=None,
    help="trigger compaction at this fraction of context_limit (0.0–1.0, default: 0.75)",
)
agent_parser.add_argument(
    "--no-compaction",
    action="store_true",
    default=False,
    help="disable conversation compaction entirely",
)


# Parser for event-server command.
event_server_parser = subparsers.add_parser("event-server")
event_server_parser.add_argument(
    "--host",
    default="127.0.0.1",
    help="host address to bind the event bus server (default: 127.0.0.1)",
)
event_server_parser.add_argument(
    "--port",
    type=int,
    default=8000,
    help="port to bind the event bus server (default: 8000)",
)

# Parser for event-client command with sub-subcommands.
event_client_parser = subparsers.add_parser("event-client")
event_client_subparsers = event_client_parser.add_subparsers(dest="event_client_command")

# event-client send
event_client_send_parser = event_client_subparsers.add_parser("send")
event_client_send_parser.add_argument(
    "--url",
    default="http://127.0.0.1:8000",
    help="event bus server URL (default: http://127.0.0.1:8000)",
)
event_client_send_parser.add_argument(
    "--event-type",
    required=True,
    help="event type to publish",
)
event_client_send_parser.add_argument(
    "--payload",
    default="{}",
    help="JSON payload string (default: {})",
)

# event-client listen
event_client_listen_parser = event_client_subparsers.add_parser("listen")
event_client_listen_parser.add_argument(
    "--url",
    default="http://127.0.0.1:8000",
    help="event bus server URL (default: http://127.0.0.1:8000)",
)
event_client_listen_parser.add_argument(
    "--event-type",
    required=True,
    help="event type to listen for",
)
event_client_listen_parser.add_argument(
    "--client-id",
    required=True,
    help="unique client identifier for polling",
)

# event-client stream
event_client_stream_parser = event_client_subparsers.add_parser("stream")
event_client_stream_parser.add_argument(
    "--url",
    default="http://127.0.0.1:8000",
    help="event bus server URL (default: http://127.0.0.1:8000)",
)
event_client_stream_parser.add_argument(
    "--event-type",
    required=True,
    help="event type to stream",
)


def main() -> None:
    """Parse command-line arguments and dispatch to subcommands."""
    args = parser.parse_args()

    if args.command == "start":
        start(args)
    elif args.command == "agent":
        run_agent(args)
    elif args.command == "visualize":
        visualize(args)
    elif args.command == "event-server":
        run_event_server(args)
    elif args.command == "event-client":
        run_event_client(args)
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


def build_harvest_agent(args: argparse.Namespace) -> HarvestAgent:
    """Construct the Harvest agent from CLI args."""

    conversation_store = None
    if not getattr(args, "no_persist", False):
        from harvest.storage.schema.agent import ConversationStore

        conversation_store = ConversationStore()

    extra_kwargs: dict[str, Any] = {}
    context_limit = getattr(args, "context_limit", None)
    if context_limit is not None:
        extra_kwargs["context_limit"] = context_limit

    compaction_threshold = getattr(args, "compaction_threshold", None)
    if compaction_threshold is not None:
        extra_kwargs["compaction_threshold"] = compaction_threshold

    # --no-compaction effectively sets threshold to an unreachable value
    if getattr(args, "no_compaction", False):
        extra_kwargs["compaction_threshold"] = float("inf")

    config = HarvestAgentConfig.from_env(
        model=args.model,
        system_prompt=args.system_prompt,
        session_id=getattr(args, "session", None),
        **extra_kwargs,
    )
    return HarvestAgent(
        config=config,
        conversation_store=conversation_store,
    )


def run_agent(
    args: argparse.Namespace,
    input_func: Callable[[str], str] = input,
    output_stream: TextIO = sys.stdout,
    error_stream: TextIO = sys.stderr,
    test: bool = False,
) -> None:
    """Run the proof-of-concept single-agent CLI flow.

    Args:
        args: Parsed command-line arguments.
        input_func: Input function used for interactive chat mode.
        output_stream: Stream for normal output.
        error_stream: Stream for error output.
        test: When true, raise runtime errors instead of exiting.
    """

    try:
        agent = build_harvest_agent(args)
    except (ValueError, Exception) as exc:
        if test:
            raise RuntimeError(str(exc)) from exc

        print(str(exc), file=error_stream)
        sys.exit(2)

    if args.message:
        _emit_agent_reply(agent=agent, message=args.message, output_stream=output_stream)
        return

    print("Harvest agent ready. Type 'exit' or 'quit' to end the session.", file=output_stream)
    while True:
        try:
            user_message = input_func("You: ")
        except EOFError:
            print(file=output_stream)
            return

        normalized_message = user_message.strip()
        if not normalized_message:
            continue

        if normalized_message.lower() in {"exit", "quit"}:
            print("Ending agent session.", file=output_stream)
            return

        _emit_agent_reply(agent=agent, message=normalized_message, output_stream=output_stream)


def _emit_agent_reply(agent: HarvestAgent, message: str, output_stream: TextIO) -> None:
    """Send a user message to the agent and print the assistant reply."""

    reply = agent.step(message)
    print(f"Assistant: {reply}", file=output_stream)


def run_event_server(args: argparse.Namespace) -> None:
    """Start the event bus HTTP server."""
    from harvest.event_server import run_server

    run_server(host=args.host, port=args.port)


def run_event_client(args: argparse.Namespace) -> None:
    """Dispatch event-client sub-commands (send, listen, stream)."""
    import json as _json

    from harvest.event_client import poll_events, publish_event, stream_events

    sub = getattr(args, "event_client_command", None)

    if sub == "send":
        try:
            payload = _json.loads(args.payload)
        except _json.JSONDecodeError as exc:
            print(f"Invalid JSON payload: {exc}", file=sys.stderr)
            sys.exit(1)
        result = publish_event(args.url, args.event_type, payload)
        print(_json.dumps(result, indent=2))

    elif sub == "listen":
        events = poll_events(args.url, args.event_type, args.client_id)
        print(_json.dumps(events, indent=2))

    elif sub == "stream":
        try:
            for event in stream_events(args.url, args.event_type):
                print(_json.dumps(event, indent=2), flush=True)
        except KeyboardInterrupt:
            pass

    else:
        event_client_parser.print_help(sys.stderr)
        sys.exit(1)


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
