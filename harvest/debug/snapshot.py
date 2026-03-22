"""Snapshot dataclasses for the debug monitor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AgentInfo:
    """Read-only snapshot of one agent in a sandbox."""

    agent_id: str
    agent_type: str
    thread_alive: bool
    policy_summary: dict[str, Any] | None
    status: str = "idle"


@dataclass(slots=True)
class ChannelInfo:
    """Read-only snapshot of one channel in a sandbox."""

    channel_id: str
    channel_type: str
    title: str
    member_ids: list[str] = field(default_factory=list)
    publisher_ids: list[str] = field(default_factory=list)
    subscriber_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MessageInfo:
    """Read-only snapshot of one chat message."""

    message_id: str
    channel_id: str
    sender_id: str
    content: str
    timestamp: str
    reply_to: str = ""


@dataclass(slots=True)
class SandboxSnapshot:
    """Complete read-only snapshot of one sandbox's observable state."""

    sandbox_id: str
    display_name: str
    agents: list[AgentInfo] = field(default_factory=list)
    channels: list[ChannelInfo] = field(default_factory=list)
    recent_messages: list[MessageInfo] = field(default_factory=list)
    typing: dict[str, list[str]] = field(default_factory=dict)
    snapshot_timestamp: str = ""
