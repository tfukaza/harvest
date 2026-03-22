"""Process-global registry of active BasicSandbox instances."""

from __future__ import annotations

import datetime as dt
import threading
from collections import deque
from typing import Any

from harvest.debug.snapshot import (
    AgentInfo,
    ChannelInfo,
    MessageInfo,
    SandboxSnapshot,
)


class SandboxRegistry:
    """Thread-safe registry that tracks active sandboxes and produces snapshots.

    Sandboxes register themselves (or are registered by their creator) when they
    start, and unregister when they stop.
    """

    def __init__(self, message_buffer_size: int = 500) -> None:
        self._lock = threading.Lock()
        self._sandboxes: dict[str, Any] = {}  # sandbox_id -> BasicSandbox
        self._message_buffers: dict[str, deque[MessageInfo]] = {}
        self._buffer_size = message_buffer_size
        self._typing_state: dict[str, dict[str, set[str]]] = {}  # sandbox_id -> channel_id -> {agent_ids}
        self._typing_callbacks: list[Any] = []  # external listeners for typing events
        self._status_callbacks: list[Any] = []  # external listeners for agent status changes

    def register(self, sandbox_id: str, sandbox: Any) -> None:
        """Register a sandbox for observation.

        Args:
            sandbox_id: Unique identifier.
            sandbox: A BasicSandbox instance.

        Raises:
            ValueError: If sandbox_id is already registered.
        """
        with self._lock:
            if sandbox_id in self._sandboxes:
                raise ValueError(f"Sandbox already registered: {sandbox_id}")
            self._sandboxes[sandbox_id] = sandbox
            self._message_buffers[sandbox_id] = deque(maxlen=self._buffer_size)

        # Subscribe to message notifications on the sandbox's ChatRouter
        buf = self._message_buffers[sandbox_id]

        def _on_delivered(
            channel_id: str,
            sender_id: str,
            recipient_ids: list[str],
            message_id: str,
            channel_type: str,
            content: str = "",
            reply_to: str = "",
        ) -> None:
            msg = MessageInfo(
                message_id=message_id,
                channel_id=channel_id,
                sender_id=sender_id,
                content=content,
                timestamp=dt.datetime.now(dt.UTC).isoformat(),
                reply_to=reply_to,
            )
            buf.append(msg)

        if hasattr(sandbox, "chat_router"):
            sandbox.chat_router.on_new_message(_on_delivered)

        # Subscribe to typing indicator changes
        self._typing_state[sandbox_id] = {}

        def _on_typing(channel_id: str, agent_id: str, is_typing: bool) -> None:
            with self._lock:
                channels = self._typing_state.get(sandbox_id, {})
                if is_typing:
                    channels.setdefault(channel_id, set()).add(agent_id)
                else:
                    agents = channels.get(channel_id, set())
                    agents.discard(agent_id)
                    if not agents:
                        channels.pop(channel_id, None)
            for cb in self._typing_callbacks:
                try:
                    cb(sandbox_id, channel_id, agent_id, is_typing)
                except Exception:
                    pass

        if hasattr(sandbox, "chat_router"):
            sandbox.chat_router.on_typing_changed(_on_typing)

        # Subscribe to agent status changes
        def _on_status(agent_id: str, status: Any) -> None:
            for cb in self._status_callbacks:
                try:
                    cb(sandbox_id, agent_id, status.value if hasattr(status, "value") else str(status))
                except Exception:
                    pass

        if hasattr(sandbox, "on_status_changed"):
            sandbox.on_status_changed(_on_status)

    def unregister(self, sandbox_id: str) -> None:
        """Remove a sandbox from the registry.

        Args:
            sandbox_id: Sandbox to remove.

        Raises:
            KeyError: If not found.
        """
        with self._lock:
            del self._sandboxes[sandbox_id]
            del self._message_buffers[sandbox_id]
            self._typing_state.pop(sandbox_id, None)

    def on_typing(self, callback: Any) -> None:
        """Register a callback for typing indicator changes.

        Args:
            callback: Called with (sandbox_id, channel_id, agent_id, is_typing).
        """
        self._typing_callbacks.append(callback)

    def on_status_changed(self, callback: Any) -> None:
        """Register a callback for agent status changes.

        Args:
            callback: Called with (sandbox_id, agent_id, status_str).
        """
        self._status_callbacks.append(callback)

    def list_sandbox_ids(self) -> list[str]:
        """Return IDs of all registered sandboxes."""
        with self._lock:
            return list(self._sandboxes.keys())

    def get_sandbox(self, sandbox_id: str) -> Any:
        """Get a sandbox by ID.

        Raises:
            KeyError: If not found.
        """
        with self._lock:
            return self._sandboxes[sandbox_id]

    def get_message_buffer(self, sandbox_id: str) -> deque[MessageInfo]:
        """Get the message buffer for a sandbox."""
        with self._lock:
            return self._message_buffers[sandbox_id]

    def snapshot(self, sandbox_id: str) -> SandboxSnapshot:
        """Build a snapshot for a single sandbox."""
        with self._lock:
            sandbox = self._sandboxes[sandbox_id]
            buf = self._message_buffers[sandbox_id]

        # Agents
        agents: list[AgentInfo] = []
        for aid in sandbox.list_agents():
            handle = sandbox.get_agent_handle(aid)
            policy_summary = None
            if handle.policy is not None:
                policy_summary = {
                    "can_send_messages": handle.policy.can_send_messages,
                    "can_create_channel": handle.policy.can_create_channel,
                    "can_create_agents": handle.policy.can_create_agents,
                }
            agents.append(AgentInfo(
                agent_id=aid,
                agent_type=handle.agent.__class__.__name__,
                thread_alive=handle.thread.is_alive() if handle.thread else False,
                policy_summary=policy_summary,
                status=handle.status.value if hasattr(handle, "status") else "idle",
            ))

        # Channels
        channels: list[ChannelInfo] = []
        for ch in sandbox.chat_router.list_channels():
            member_ids = getattr(ch, "member_ids", [])
            publisher_ids = getattr(ch, "publisher_ids", [])
            subscriber_ids = getattr(ch, "subscriber_ids", [])
            channels.append(ChannelInfo(
                channel_id=ch.channel_id,
                channel_type=ch.channel_type.value,
                title=ch.title,
                member_ids=list(member_ids),
                publisher_ids=list(publisher_ids),
                subscriber_ids=list(subscriber_ids),
            ))

        # Typing state
        with self._lock:
            raw_typing = self._typing_state.get(sandbox_id, {})
            typing = {ch: list(agents) for ch, agents in raw_typing.items() if agents}

        return SandboxSnapshot(
            sandbox_id=sandbox_id,
            display_name=sandbox.config.display_name,
            agents=agents,
            channels=channels,
            recent_messages=list(buf),
            typing=typing,
            snapshot_timestamp=dt.datetime.now(dt.UTC).isoformat(),
        )

    def snapshot_all(self) -> list[SandboxSnapshot]:
        """Build snapshots for all registered sandboxes."""
        with self._lock:
            ids = list(self._sandboxes.keys())
        return [self.snapshot(sid) for sid in ids]
