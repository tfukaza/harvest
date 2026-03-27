"""Generic event source abstraction for the agent hibernation system.

When an agent's LLM call loop completes, it enters hibernation — a sleep-poll
loop that checks registered EventSources for pending events.  When events are
found they are wrapped as WakeEvents, formatted into a prompt, and fed back
into the agent's step() to restart the LLM call loop.
"""

from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class WakeEvent:
    """Uniform envelope for any event that should wake a hibernating agent."""

    source_type: str  # e.g. "inbox", "event_bus", "timer"
    agent_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))


class EventSource(ABC):
    """Pluggable event source that the hibernation loop polls."""

    @abstractmethod
    def poll(self, agent_id: str) -> list[WakeEvent]:
        """Check for pending events.

        Must be thread-safe and non-blocking.
        Returns an empty list when nothing is pending.
        """


class InboxEventSource(EventSource):
    """Polls ChatRouter.read_inbox() and wraps messages as WakeEvents."""

    def __init__(self, chat_router: Any) -> None:
        self._chat_router = chat_router

    def poll(self, agent_id: str) -> list[WakeEvent]:
        inbox = self._chat_router.read_inbox(agent_id)
        if not inbox:
            return []
        events: list[WakeEvent] = []
        for msg in inbox:
            # Failsafe: skip messages the agent sent itself to avoid
            # self-notification loops.
            if msg.sender.endpoint_id == agent_id:
                continue
            events.append(
                WakeEvent(
                    source_type="inbox",
                    agent_id=agent_id,
                    payload={
                        "sender_id": msg.sender.endpoint_id,
                        "channel_id": msg.recipient.endpoint_id,
                        "content": msg.content,
                        "message_id": msg.message_id,
                        "mention_type": msg.metadata.get("mention_type", "mention"),
                    },
                    timestamp=msg.created_at,
                )
            )
        return events


class SilenceDetectorSource(EventSource):
    """Fires a wake event if no messages have arrived for a given duration.

    Useful for moderators or orchestrators that need to re-engage when the
    conversation stalls.  The timer resets every time a message is observed
    via the ``notify()`` callback.
    """

    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self._timeout = timeout_seconds
        self._last_activity = dt.datetime.now(dt.UTC)

    def notify(self) -> None:
        """Call this whenever channel activity is observed to reset the timer."""
        self._last_activity = dt.datetime.now(dt.UTC)

    def poll(self, agent_id: str) -> list[WakeEvent]:
        elapsed = (dt.datetime.now(dt.UTC) - self._last_activity).total_seconds()
        if elapsed >= self._timeout:
            # Reset so we don't fire every poll cycle
            self._last_activity = dt.datetime.now(dt.UTC)
            return [
                WakeEvent(
                    source_type="silence",
                    agent_id=agent_id,
                    payload={"elapsed_seconds": round(elapsed, 1)},
                )
            ]
        return []
