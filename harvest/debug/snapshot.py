"""Snapshot dataclasses for the debug monitor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ActivityEntry:
    """One entry in an agent's reasoning activity log."""

    type: str  # "thinking", "tool_call", "tool_result", "text", "summary"
    timestamp: str
    content: str = ""
    tool_name: str = ""
    tool_args: str = ""
    tool_call_id: str = ""
    tokens_before: int = 0
    tokens_after: int = 0


@dataclass(slots=True)
class AgentInfo:
    """Read-only snapshot of one agent in a sandbox."""

    agent_id: str
    agent_type: str
    thread_alive: bool
    policy_summary: dict[str, Any] | None
    status: str = "idle"
    activity: list[ActivityEntry] = field(default_factory=list)
    memories: list[dict[str, str]] = field(default_factory=list)
    todos: list[dict[str, Any]] = field(default_factory=list)
    cognitive_tools: list[str] = field(default_factory=list)
    context_tokens: int = 0
    context_limit: int = 0
    compaction_threshold: float = 0.0


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
