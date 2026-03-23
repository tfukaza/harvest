"""Admin message queue for human-injected messages.

Provides a thread-safe FIFO queue that allows human operators to inject
messages into sandbox channels through the debug monitor WebSocket.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class AdminMessage:
    """A message queued by the admin for injection into a channel."""

    sandbox_id: str
    channel_id: str
    content: str
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex)


class AdminMessageQueue:
    """Thread-safe FIFO queue for admin-injected messages.

    The debug server enqueues messages; the sandbox drains the queue
    by calling ``drain()`` on each tick or on demand.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: list[AdminMessage] = []
        self._listeners: list[Callable[[AdminMessage], None]] = []

    def enqueue(self, msg: AdminMessage) -> None:
        """Add a message to the queue and notify listeners."""
        with self._lock:
            self._items.append(msg)
            listeners = list(self._listeners)
        for cb in listeners:
            try:
                cb(msg)
            except Exception:
                pass

    def drain(self) -> list[AdminMessage]:
        """Remove and return all queued messages."""
        with self._lock:
            items = list(self._items)
            self._items.clear()
        return items

    def on_enqueue(self, callback: Callable[[AdminMessage], None]) -> None:
        """Register a callback invoked whenever a message is enqueued."""
        with self._lock:
            self._listeners.append(callback)

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)
