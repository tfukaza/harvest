"""HTTP client helpers for interacting with an EventBusServer.

Uses the ``requests`` library (already a project dependency) so that
callers do not need an async runtime.
"""

from __future__ import annotations

import json
from typing import Any, Iterator

import requests


def publish_event(url: str, event_type: str, data: dict[str, Any]) -> dict[str, Any]:
    """Publish an event to the event bus server.

    Args:
        url: Base URL of the event bus server (e.g. ``http://127.0.0.1:8000``).
        event_type: The event type string.
        data: JSON-serialisable event payload.

    Returns:
        Parsed JSON response from the server.
    """
    resp = requests.post(
        f"{url.rstrip('/')}/api/events/publish",
        json={"event_type": event_type, "data": data},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def poll_events(url: str, event_type: str, client_id: str) -> list[dict[str, Any]]:
    """Poll queued events from the event bus server.

    Args:
        url: Base URL of the event bus server.
        event_type: The event type to poll.
        client_id: Unique identifier for this listener.

    Returns:
        List of event records.
    """
    resp = requests.get(
        f"{url.rstrip('/')}/api/events/listen",
        params={"event_type": event_type, "client_id": client_id},
        timeout=10,
    )
    resp.raise_for_status()
    body = resp.json()
    return body.get("events", [])


def stream_events(url: str, event_type: str) -> Iterator[dict[str, Any]]:
    """Connect to the SSE stream and yield events as they arrive.

    This is a blocking generator -- it will run until the connection is
    closed or the caller stops iterating.

    Args:
        url: Base URL of the event bus server.
        event_type: The event type to stream.

    Yields:
        Parsed event records.
    """
    resp = requests.get(
        f"{url.rstrip('/')}/api/events/stream",
        params={"event_type": event_type},
        stream=True,
        timeout=None,
    )
    resp.raise_for_status()

    for line in resp.iter_lines(decode_unicode=True):
        if line and line.startswith("data: "):
            payload = line[len("data: "):]
            try:
                yield json.loads(payload)
            except json.JSONDecodeError:
                continue
