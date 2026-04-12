"""Sanity tests for the surviving CLI surface."""


import io
import pathlib

import pytest

from harvest import cli


def test_start_command_is_a_placeholder_for_future_runtime_entry() -> None:
    args = cli.parser.parse_args(["start", "--config", "orchestrator.yaml"])

    with pytest.raises(RuntimeError, match="legacy 'harvest start' flow has been removed"):
        cli.start(args, test=True)


def test_visualize_parser_retains_path_argument() -> None:
    args = cli.parser.parse_args(["visualize", "sample.csv"])

    assert args.command == "visualize"
    assert args.path == "sample.csv"


def test_agent_parser_accepts_one_shot_message() -> None:
    args = cli.parser.parse_args(["agent", "--message", "hello"])

    assert args.command == "agent"
    assert args.message == "hello"


def test_agent_parser_accepts_session_flag() -> None:
    args = cli.parser.parse_args(["agent", "--session", "my-session"])

    assert args.session == "my-session"


def test_agent_parser_accepts_no_persist_flag() -> None:
    args = cli.parser.parse_args(["agent", "--no-persist"])

    assert args.no_persist is True


def test_agent_parser_defaults() -> None:
    args = cli.parser.parse_args(["agent"])

    assert args.session is None
    assert args.no_persist is False
    assert args.model is None


def test_agent_command_runs_one_shot_message(monkeypatch: pytest.MonkeyPatch) -> None:
    output_stream = io.StringIO()

    class FakeAgent:
        def __init__(self) -> None:
            self.messages: list[str] = []

        def step(self, message: str) -> str:
            self.messages.append(message)
            return f"echo:{message}"

    fake_agent = FakeAgent()
    monkeypatch.setattr(cli, "build_harvest_agent", lambda args: fake_agent)
    args = cli.parser.parse_args(["agent", "--message", "hello"])

    cli.run_agent(args, output_stream=output_stream, test=True)

    assert fake_agent.messages == ["hello"]
    assert output_stream.getvalue().strip() == "Assistant: echo:hello"


def test_agent_command_runs_interactive_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    output_stream = io.StringIO()

    class FakeAgent:
        def step(self, message: str) -> str:
            return f"reply:{message}"

    inputs = iter(["hello", "exit"])
    monkeypatch.setattr(cli, "build_harvest_agent", lambda args: FakeAgent())
    args = cli.parser.parse_args(["agent"])

    cli.run_agent(
        args,
        input_func=lambda prompt: next(inputs),
        output_stream=output_stream,
        test=True,
    )

    output = output_stream.getvalue()
    assert "Harvest agent ready" in output
    assert "Assistant: reply:hello" in output
    assert "Ending agent session." in output


# ---------------------------------------------------------------------------
# event-server parser tests
# ---------------------------------------------------------------------------


def test_event_server_parser_defaults() -> None:
    args = cli.parser.parse_args(["event-server"])

    assert args.command == "event-server"
    assert args.host == "127.0.0.1"
    assert args.port == 8000


def test_event_server_parser_custom_host_port() -> None:
    args = cli.parser.parse_args(["event-server", "--host", "0.0.0.0", "--port", "9000"])

    assert args.host == "0.0.0.0"
    assert args.port == 9000


# ---------------------------------------------------------------------------
# event-client parser tests
# ---------------------------------------------------------------------------


def test_event_client_send_parser() -> None:
    args = cli.parser.parse_args([
        "event-client", "send",
        "--url", "http://localhost:9000",
        "--event-type", "price_update",
        "--payload", '{"symbol":"AAPL"}',
    ])

    assert args.command == "event-client"
    assert args.event_client_command == "send"
    assert args.url == "http://localhost:9000"
    assert args.event_type == "price_update"
    assert args.payload == '{"symbol":"AAPL"}'


def test_event_client_send_parser_defaults() -> None:
    args = cli.parser.parse_args([
        "event-client", "send",
        "--event-type", "test",
    ])

    assert args.url == "http://127.0.0.1:8000"
    assert args.payload == "{}"


def test_event_client_listen_parser() -> None:
    args = cli.parser.parse_args([
        "event-client", "listen",
        "--url", "http://localhost:9000",
        "--event-type", "price_update",
        "--client-id", "listener-a",
    ])

    assert args.command == "event-client"
    assert args.event_client_command == "listen"
    assert args.event_type == "price_update"
    assert args.client_id == "listener-a"


def test_event_client_stream_parser() -> None:
    args = cli.parser.parse_args([
        "event-client", "stream",
        "--url", "http://localhost:9000",
        "--event-type", "price_update",
    ])

    assert args.command == "event-client"
    assert args.event_client_command == "stream"
    assert args.event_type == "price_update"
