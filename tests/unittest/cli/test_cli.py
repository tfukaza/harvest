"""Sanity tests for the surviving CLI surface."""

from __future__ import annotations

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
