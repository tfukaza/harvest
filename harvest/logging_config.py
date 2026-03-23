"""Structured logging configuration for Harvest.

Provides:
- JSONFormatter: formats log records as JSON lines for machine-readable output
- log_event: helper to emit structured events with sandbox/agent context
- setup_logging: configures dual-output logging (JSON file + human console)
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import sys
from typing import Any


class JSONFormatter(logging.Formatter):
    """Formats log records as newline-delimited JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": dt.datetime.fromtimestamp(
                record.created, tz=dt.timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("event", "sandbox_id", "agent_id", "data"):
            val = getattr(record, key, None)
            if val is not None:
                payload[key] = val
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def log_event(
    logger: logging.Logger,
    event: str,
    *,
    level: int = logging.INFO,
    sandbox_id: str | None = None,
    agent_id: str | None = None,
    data: dict[str, Any] | None = None,
) -> None:
    """Emit a structured log event with optional sandbox/agent context.

    Args:
        logger: Logger to emit to.
        event: Event name from the taxonomy (e.g. "agent.step.start").
        level: Log level (default INFO).
        sandbox_id: Sandbox identifier, if applicable.
        agent_id: Agent identifier, if applicable.
        data: Additional structured data payload.
    """
    extra: dict[str, Any] = {"event": event}
    if sandbox_id is not None:
        extra["sandbox_id"] = sandbox_id
    if agent_id is not None:
        extra["agent_id"] = agent_id
    if data is not None:
        extra["data"] = data
    logger.log(level, event, extra=extra)


def setup_logging(
    log_file: str = "harvest.jsonl",
    *,
    level: int = logging.INFO,
    json_file: bool = True,
    console: bool = True,
) -> None:
    """Configure dual-output logging: JSON .jsonl file + human-readable console.

    Replaces any existing handlers on the "harvest" logger.

    Args:
        log_file: Path for the JSON log file.
        level: Minimum log level.
        json_file: Whether to write structured JSON to file.
        console: Whether to write human-readable output to stdout.
    """
    root = logging.getLogger("harvest")
    root.setLevel(level)
    root.handlers.clear()

    if json_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(JSONFormatter())
        root.addHandler(fh)

    if console:
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(
            logging.Formatter(
                "%(asctime)s : %(name)s : %(levelname)s : %(message)s",
                datefmt="%m/%d/%Y %I:%M:%S %p",
            )
        )
        root.addHandler(ch)
