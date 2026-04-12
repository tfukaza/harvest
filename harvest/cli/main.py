"""CLI entrypoint for Harvest."""


import argparse
import os
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, TextIO

from harvest.harvest_agent import HarvestAgent, HarvestAgentConfig, DEFAULT_SYSTEM_PROMPT
from harvest.util.helper import debugger

parser = argparse.ArgumentParser(description="Harvest CLI")
parser.add_argument(
    "--debug",
    action="store_true",
    default=False,
    help="enable DEBUG-level logging (shows full agent context sent to LLM)",
)
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


# Parser for sandbox command.
sandbox_parser = subparsers.add_parser("sandbox", help="Run a multi-agent sandbox from a YAML manifest")
sandbox_parser.add_argument(
    "manifest",
    help="path to a sandbox YAML manifest file",
)
sandbox_parser.add_argument(
    "--topic",
    default=None,
    help="seed message to inject into the conversation channel",
)
sandbox_parser.add_argument(
    "--seed-channel",
    default=None,
    help="channel to inject the seed into (default: first group channel)",
)
sandbox_parser.add_argument(
    "--kickstart",
    default=None,
    help="agent ID to receive the seed message (default: all channel members)",
)
sandbox_parser.add_argument(
    "--no-monitor",
    action="store_true",
    default=False,
    help="disable the debug monitor server",
)
sandbox_parser.add_argument(
    "--host",
    default="127.0.0.1",
    help="debug monitor host (default: 127.0.0.1)",
)
sandbox_parser.add_argument(
    "--port",
    type=int,
    default=8100,
    help="debug monitor port (default: 8100)",
)


# Parser for admin command (send messages to a running sandbox).
admin_parser = subparsers.add_parser("admin", help="Send an admin message to a running sandbox via WebSocket")
admin_parser.add_argument(
    "channel",
    help="channel ID to send the message to",
)
admin_parser.add_argument(
    "message",
    help="message content to send",
)
admin_parser.add_argument(
    "--sandbox",
    default=None,
    help="sandbox ID (auto-detected from snapshot if omitted)",
)
admin_parser.add_argument(
    "--url",
    default="ws://localhost:8100/ws",
    help="WebSocket URL of the debug monitor (default: ws://localhost:8100/ws)",
)


# Parser for debug-server command.
debug_server_parser = subparsers.add_parser("debug-server")
debug_server_parser.add_argument(
    "--host",
    default="127.0.0.1",
    help="host address to bind the debug monitor server (default: 127.0.0.1)",
)
debug_server_parser.add_argument(
    "--port",
    type=int,
    default=8100,
    help="port to bind the debug monitor server (default: 8100)",
)
debug_server_parser.add_argument(
    "--static-dir",
    default=None,
    help="path to SvelteKit build output for static file serving",
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

    if args.debug:
        import logging
        logging.getLogger("harvest").setLevel(logging.DEBUG)

    if args.command == "start":
        start(args)
    elif args.command == "agent":
        run_agent(args)
    elif args.command == "sandbox":
        run_sandbox(args)
    elif args.command == "visualize":
        visualize(args)
    elif args.command == "debug-server":
        run_debug_server(args)
    elif args.command == "event-server":
        run_event_server(args)
    elif args.command == "admin":
        run_admin(args)
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


def run_sandbox(
    args: argparse.Namespace,
    output_stream: TextIO = sys.stdout,
) -> None:
    """Load a sandbox from a YAML manifest and run autonomously.

    Agents run via the hibernation loop — the CLI just starts the sandbox,
    injects an optional seed message, and blocks until Ctrl+C.

    Args:
        args: Parsed command-line arguments.
        output_stream: Stream for normal output.
    """
    import asyncio
    import logging

    from harvest.agent_sandbox.basic_sandbox import BasicSandbox
    from harvest.agent_sandbox.chat.channels import GroupChannel
    from harvest.storage.schema.chat import ChatStore

    # Suppress noisy library logs during sandbox runs
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
    logging.getLogger("litellm").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if not args.debug:
        logging.getLogger("harvest").setLevel(logging.WARNING)

    # Always write debug logs to a file for post-mortem analysis.
    # The logger level must be DEBUG so messages reach the file handler,
    # but we set the console handler level to WARNING (or DEBUG with --debug)
    # so the terminal stays clean.
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    import datetime as dt
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    manifest_stem = Path(args.manifest).stem
    log_file = log_dir / f"{manifest_stem}_{timestamp}.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-5s %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    ))

    harvest_logger = logging.getLogger("harvest")
    harvest_logger.addHandler(file_handler)
    # Logger must accept DEBUG so the file handler receives everything.
    harvest_logger.setLevel(logging.DEBUG)

    # Keep console quiet unless --debug. Set level on existing handlers
    # (typically the root logger's StreamHandler) rather than the logger itself.
    console_level = logging.DEBUG if args.debug else logging.WARNING
    root = logging.getLogger()
    for h in root.handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
            h.setLevel(console_level)

    print(f"Debug log: {log_file}", file=output_stream)

    manifest_path = args.manifest
    chat_store = ChatStore()

    try:
        sandbox = BasicSandbox.from_manifest(manifest_path, chat_store=chat_store)
    except Exception as exc:
        print(f"Failed to load manifest: {exc}", file=sys.stderr)
        sys.exit(2)

    agents = sandbox.list_agents()
    router = sandbox.chat_router

    # Determine seed channel
    seed_channel = args.seed_channel
    if seed_channel is None:
        group_channels = [
            ch for ch in router.list_channels()
            if isinstance(ch, GroupChannel)
        ]
        if group_channels:
            seed_channel = group_channels[0].channel_id

    # Start debug monitor (on by default, --no-monitor to disable)
    monitor = None
    if not args.no_monitor:
        from harvest.debug.registry import SandboxRegistry
        from harvest.debug.server import DebugMonitorServer

        registry = SandboxRegistry()
        registry.register(sandbox.config.display_name, sandbox)
        # Auto-detect GUI build directory
        gui_build = Path(__file__).resolve().parent.parent / "gui" / "build"
        static_dir = str(gui_build) if gui_build.is_dir() else None

        monitor = DebugMonitorServer(
            registry=registry,
            host=args.host,
            port=args.port,
            static_dir=static_dir,
        )
        monitor.start()
        print(
            f"Debug monitor running at http://{args.host}:{args.port}",
            file=output_stream,
        )

    async def _run() -> None:
        print(f"=== Sandbox: {sandbox.config.display_name} ===", file=output_stream)
        print(f"Agents: {', '.join(agents)}", file=output_stream)

        # Inject manifest-level seeds first
        from harvest.agent_sandbox.manifest import load_manifest as _load_manifest
        manifest = _load_manifest(manifest_path)
        for seed in manifest.seeds:
            target_label = ", ".join(seed.recipients) if seed.recipients else "all"
            print(f"[scenario-seed] → {seed.channel_id} ({target_label}): {seed.content}", file=output_stream)
            import uuid as _uuid
            router.send_message(
                sender_id="system",
                channel_id=seed.channel_id,
                content=seed.content,
                message_id=f"seed-{_uuid.uuid4().hex[:8]}",
            )

        # Inject CLI --topic seed (overrides / adds to manifest seeds)
        if args.topic and seed_channel:
            kickstart = [args.kickstart] if args.kickstart else None
            target_label = args.kickstart or "all"
            print(f"[scenario-seed] → {seed_channel} ({target_label}): {args.topic}", file=output_stream)
            router.send_message(
                sender_id="system",
                channel_id=seed_channel,
                content=args.topic,
                message_id=f"seed-{_uuid.uuid4().hex[:8]}",
            )

        print("Press Ctrl+C to stop.\n", file=output_stream)

        # Start the sandbox — agents run autonomously via hibernation loop
        await sandbox.start()

        # Block until interrupted
        stop = asyncio.Event()
        try:
            await stop.wait()
        except asyncio.CancelledError:
            pass

        await sandbox.stop()

        if monitor is not None:
            monitor.stop()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        print("\nShutting down.", file=output_stream)


def run_admin(args: argparse.Namespace) -> None:
    """Send an admin message to a running sandbox via WebSocket.

    Connects to the debug monitor, auto-detects the sandbox ID from
    the initial snapshot (unless --sandbox is given), sends the message,
    waits for the server acknowledgement, and exits.
    """
    import json as _json
    import time as _time

    from simple_websocket import Client as WsClient

    url = args.url
    channel = args.channel
    content = args.message
    sandbox_id = args.sandbox

    print(f"Connecting to {url} ...")
    try:
        ws = WsClient.connect(url)
    except Exception as exc:
        print(f"Failed to connect: {exc}", file=sys.stderr)
        sys.exit(1)

    # Read the initial snapshot to auto-detect sandbox_id
    if sandbox_id is None:
        try:
            raw = ws.receive(timeout=5)
            snap = _json.loads(raw)
            if snap.get("type") == "snapshot" and snap.get("sandboxes"):
                sandbox_id = snap["sandboxes"][0]["sandbox_id"]
                print(f"Auto-detected sandbox: {sandbox_id}")
            else:
                print("No sandboxes found in snapshot.", file=sys.stderr)
                ws.close()
                sys.exit(1)
        except Exception as exc:
            print(f"Failed to read snapshot: {exc}", file=sys.stderr)
            ws.close()
            sys.exit(1)

    payload = _json.dumps({
        "type": "admin_send",
        "sandbox_id": sandbox_id,
        "channel_id": channel,
        "content": content,
    })
    print(f"Sending to #{channel}: {content}")
    ws.send(payload)

    # Wait for ack (admin_queued or admin_blocked)
    deadline = _time.monotonic() + 5.0
    while _time.monotonic() < deadline:
        try:
            raw = ws.receive(timeout=2)
            msg = _json.loads(raw)
            if msg.get("type") == "admin_queued":
                print(f"Queued (message_id={msg.get('message_id', '?')})")
                ws.close()
                return
            elif msg.get("type") == "admin_blocked":
                print(f"Blocked: {msg.get('reason', 'unknown')}", file=sys.stderr)
                ws.close()
                sys.exit(1)
            # Ignore other messages (snapshots, deltas, typing)
        except Exception:
            break

    print("No acknowledgement received within timeout.", file=sys.stderr)
    ws.close()
    sys.exit(1)


def run_debug_server(args: argparse.Namespace) -> None:
    """Start the debug monitor server."""
    from harvest.debug.registry import SandboxRegistry
    from harvest.debug.server import DebugMonitorServer

    registry = SandboxRegistry()
    server = DebugMonitorServer(
        registry=registry,
        host=args.host,
        port=args.port,
        static_dir=getattr(args, "static_dir", None),
    )
    print(f"Debug monitor server starting on http://{args.host}:{args.port}")
    server.start()
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.stop()


def run_event_server(args: argparse.Namespace) -> None:
    """Start the event bus HTTP server."""
    from harvest.http.event_server import run_server

    run_server(host=args.host, port=args.port)


def run_event_client(args: argparse.Namespace) -> None:
    """Dispatch event-client sub-commands (send, listen, stream)."""
    import json as _json

    from harvest.http.event_client import poll_events, publish_event, stream_events

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
