"""Chat router for the unified channel-based chat system.

One ChatRouter instance exists per agent sandbox. It manages all channels
within that sandbox and routes messages between agents.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
import threading
import time
from collections import defaultdict
from typing import Any

from harvest.agent_sandbox.aggregation_processor import AggregationProcessor
from harvest.agent_sandbox.channels import (
    AggregationProcessorChannel,
    ChannelDefinition,
    ChannelType,
    DMChannel,
    GatedProcessorChannel,
    GroupChannel,
    NotificationMode,
    ProcessorChannel,
)
from harvest.agent_sandbox.endpoints import EndpointAddress, EndpointKind
from harvest.agent_sandbox.gated_processor import GatedProcessor
from harvest.agent_sandbox.messages import SandboxMessage
from harvest.storage.schema.chat import ChatStore

logger = logging.getLogger(__name__)

STAKE_TIMEOUT_SECONDS = 30.0
STAKE_HOLD_SECONDS = 5.0


class ChatRouter:
    """Manages all channels within a sandbox and routes messages.

    Thread-safe — all mutable state is protected by a single lock.
    Sends are processed synchronously on the calling thread.
    """

    def __init__(self, store: ChatStore | None = None) -> None:
        """Initialize the chat router.

        Args:
            store: Optional ChatStore for message persistence.
        """
        self._agents: dict[str, EndpointAddress] = {}
        self._channels: dict[str, ChannelDefinition] = {}
        self._processors: dict[str, AggregationProcessor | GatedProcessor] = {}
        self._inboxes: dict[str, list[SandboxMessage]] = defaultdict(list)
        self._channel_counters: dict[str, int] = defaultdict(int)
        self._store = store
        self._lock = threading.Lock()
        self._on_message_delivered: list[Any] = []
        self._on_new_message: list[Any] = []

        # Channel staking (write locking) for group channels
        self._stake_lock = threading.Lock()
        self._channel_stakes: dict[str, tuple[str, float]] = {}  # channel_id → (holder_id, mono_time)
        self._stake_conditions: dict[str, threading.Condition] = {}
        self._stake_queues: dict[str, list[threading.Event]] = defaultdict(list)

        # Typing indicators: tracks agents currently trying to send
        self._typing: dict[str, set[str]] = defaultdict(set)  # channel_id → {agent_ids}
        self._on_typing_changed: list[Any] = []

    # -- Notification callbacks --

    def on_message_delivered(self, callback: Any) -> None:
        """Register a callback for message delivery ACKs.

        Args:
            callback: Called with (channel_id, message_id, sender_id, timestamp, error).
        """
        self._on_message_delivered.append(callback)

    def on_new_message(self, callback: Any) -> None:
        """Register a callback for new message notifications.

        Args:
            callback: Called with (channel_id, sender_id, recipient_ids, message_id, channel_type, content).
        """
        self._on_new_message.append(callback)

    def on_typing_changed(self, callback: Any) -> None:
        """Register a callback for typing indicator changes.

        Args:
            callback: Called with (channel_id, agent_id, is_typing).
        """
        self._on_typing_changed.append(callback)

    def _set_typing(self, channel_id: str, agent_id: str) -> None:
        """Mark an agent as typing on a channel."""
        added = agent_id not in self._typing[channel_id]
        self._typing[channel_id].add(agent_id)
        if added:
            for cb in self._on_typing_changed:
                try:
                    cb(channel_id, agent_id, True)
                except Exception:
                    logger.exception("Error in typing_changed callback")

    def _clear_typing(self, channel_id: str, agent_id: str) -> None:
        """Clear an agent's typing indicator on a channel."""
        removed = agent_id in self._typing.get(channel_id, set())
        self._typing.get(channel_id, set()).discard(agent_id)
        if removed:
            for cb in self._on_typing_changed:
                try:
                    cb(channel_id, agent_id, False)
                except Exception:
                    logger.exception("Error in typing_changed callback")

    def get_typing_state(self) -> dict[str, list[str]]:
        """Return current typing state: channel_id → list of typing agent_ids."""
        return {
            ch: list(agents)
            for ch, agents in self._typing.items()
            if agents
        }

    # -- Agent registration --

    def register_agent(self, agent_id: str) -> None:
        """Register an agent with the router.

        Args:
            agent_id: Unique identifier of the agent.
        """
        with self._lock:
            self._agents[agent_id] = EndpointAddress(
                endpoint_id=agent_id, kind=EndpointKind.AGENT
            )

    def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent and clean up empty channels.

        Args:
            agent_id: Identifier of the agent to remove.
        """
        with self._lock:
            self._agents.pop(agent_id, None)
            self._inboxes.pop(agent_id, None)

            channels_to_remove: list[str] = []
            for channel_id, channel in list(self._channels.items()):
                if isinstance(channel, (DMChannel, GroupChannel)):
                    if agent_id in channel.member_ids:
                        channel.member_ids.remove(agent_id)
                    if not channel.member_ids:
                        channels_to_remove.append(channel_id)
                elif isinstance(channel, ProcessorChannel):
                    if agent_id in channel.publisher_ids:
                        channel.publisher_ids.remove(agent_id)
                    if agent_id in channel.subscriber_ids:
                        channel.subscriber_ids.remove(agent_id)
                    if not channel.publisher_ids and not channel.subscriber_ids:
                        channels_to_remove.append(channel_id)

            for channel_id in channels_to_remove:
                self._remove_channel_internal(channel_id)

        # Release any stakes held by the departing agent
        self._cleanup_stakes_for_agent(agent_id)

    def list_agents(self) -> list[str]:
        """Return list of registered agent IDs."""
        with self._lock:
            return list(self._agents.keys())

    # -- Channel management --

    def create_channel(self, channel: ChannelDefinition) -> None:
        """Register a channel with the router.

        Args:
            channel: Channel definition to register.

        Raises:
            ValueError: If channel ID already exists.
        """
        with self._lock:
            if channel.channel_id in self._channels:
                raise ValueError(f"Channel already exists: {channel.channel_id}")

            self._channels[channel.channel_id] = channel

            if isinstance(channel, GatedProcessorChannel):
                self._processors[channel.channel_id] = GatedProcessor(
                    publisher_ids=channel.publisher_ids
                )
            elif isinstance(channel, AggregationProcessorChannel):
                self._processors[channel.channel_id] = AggregationProcessor(
                    batch_threshold=channel.batch_threshold
                )

    def remove_channel(self, channel_id: str) -> None:
        """Remove a channel from the router.

        Args:
            channel_id: ID of the channel to remove.
        """
        with self._lock:
            self._remove_channel_internal(channel_id)

    def _remove_channel_internal(self, channel_id: str) -> None:
        """Remove a channel (must hold lock)."""
        self._channels.pop(channel_id, None)
        self._processors.pop(channel_id, None)
        self._channel_counters.pop(channel_id, None)
        if self._store:
            self._store.delete_channel(channel_id)

    def get_channel(self, channel_id: str) -> ChannelDefinition:
        """Get a channel by ID.

        Args:
            channel_id: ID of the channel.

        Returns:
            The channel definition.

        Raises:
            KeyError: If channel not found.
        """
        with self._lock:
            return self._channels[channel_id]

    def list_channels(self) -> list[ChannelDefinition]:
        """Return all channels in the sandbox."""
        with self._lock:
            return list(self._channels.values())

    def list_channels_for_agent(self, agent_id: str) -> list[ChannelDefinition]:
        """Return only channels where agent_id is a member, publisher, or subscriber.

        Args:
            agent_id: The agent to filter for.

        Returns:
            List of channels the agent belongs to.
        """
        with self._lock:
            result: list[ChannelDefinition] = []
            for channel in self._channels.values():
                if isinstance(channel, (DMChannel, GroupChannel)):
                    if agent_id in channel.member_ids:
                        result.append(channel)
                elif isinstance(channel, ProcessorChannel):
                    if agent_id in channel.publisher_ids or agent_id in channel.subscriber_ids:
                        result.append(channel)
            return result

    # -- Sending messages --

    def send_message(
        self,
        sender_id: str,
        channel_id: str,
        content: str,
        message_id: str,
        reply_to: str = "",
    ) -> dict[str, Any]:
        """Send a message to a channel. Synchronous, thread-safe.

        For group channels, this method enforces write staking:
        - If the lock is free, the message is sent immediately.
        - If another agent holds the lock, the call blocks (FIFO queue)
          until the lock is available, then returns ``channel_updated``
          with the latest messages instead of sending. The agent now
          holds the lock and should call send_message again with an
          updated response.

        Args:
            sender_id: The sending agent's ID.
            channel_id: Target channel.
            content: Message text.
            message_id: Unique message identifier.

        Returns:
            Dict with 'status' and additional fields depending on outcome.
        """
        # --- Pre-flight validation (under main lock) ---
        with self._lock:
            channel = self._channels.get(channel_id)
            if channel is None:
                self._notify_delivered(channel_id, message_id, sender_id, error="Channel not found")
                return {"status": "error", "error": "Channel not found"}

            if not self._sender_allowed(sender_id, channel):
                self._notify_delivered(channel_id, message_id, sender_id, error="Permission denied")
                return {"status": "error", "error": "Permission denied"}

            is_group = isinstance(channel, GroupChannel)

        # --- Set typing indicator (agent intends to send) ---
        self._set_typing(channel_id, sender_id)

        # --- Staking for group channels (outside main lock to allow blocking) ---
        if is_group:
            logger.info("Agent %s acquiring stake on %s", sender_id, channel_id)
            try:
                waited = self._acquire_stake(channel_id, sender_id)
            except TimeoutError:
                logger.warning("Agent %s timed out waiting for stake on %s", sender_id, channel_id)
                return {"status": "error", "error": "Timed out waiting for channel lock"}

            if waited:
                # Agent was blocked — context has changed. Return new messages
                # instead of sending the stale content. Agent holds the lock now.
                logger.info(
                    "Agent %s was blocked on %s, returning channel_updated (now holds lock)",
                    sender_id, channel_id,
                )
                new_messages = self.load_channel_history(channel_id)
                return {
                    "status": "channel_updated",
                    "new_messages": new_messages,
                    "hint": (
                        "IMPORTANT: Your message was NOT sent. Another agent "
                        "posted while you were waiting. DISCARD your previous "
                        "message content entirely — do NOT resend it. Read the "
                        "new_messages below, then compose ONE fresh response "
                        "that addresses the current state of the conversation. "
                        "You have a brief exclusive window to write."
                    ),
                }
            logger.info("Agent %s acquired stake on %s immediately", sender_id, channel_id)

        # --- Send the message (under main lock) ---
        try:
            result = self._send_message_internal(
                sender_id, channel_id, content, message_id, reply_to=reply_to,
            )
            return result
        finally:
            if is_group:
                logger.info("Agent %s releasing stake on %s", sender_id, channel_id)
                self._release_stake(channel_id, sender_id)
            # Clear typing indicator — message sent successfully (or errored)
            self._clear_typing(channel_id, sender_id)

    def _send_message_internal(
        self,
        sender_id: str,
        channel_id: str,
        content: str,
        message_id: str,
        reply_to: str = "",
    ) -> dict[str, str]:
        """Internal send logic (called after staking is resolved)."""
        with self._lock:
            channel = self._channels.get(channel_id)
            if channel is None:
                return {"status": "error", "error": "Channel not found"}

            sender_addr = self._agents.get(sender_id)
            if sender_addr is None:
                sender_addr = EndpointAddress(
                    endpoint_id=sender_id, kind=EndpointKind.AGENT
                )
            recipient_addr = EndpointAddress(
                endpoint_id=channel_id, kind=EndpointKind.GROUP_CHAT
            )

            msg = SandboxMessage(
                message_id=message_id,
                sender=sender_addr,
                recipient=recipient_addr,
                content=content,
            )

            msg_index = self._channel_counters[channel_id]
            self._channel_counters[channel_id] += 1
            if self._store:
                self._store.append_message(
                    channel_id=channel_id,
                    message_index=msg_index,
                    sender_id=sender_id,
                    content=content,
                    timestamp=dt.datetime.now(dt.UTC).isoformat(),
                )

            delivered_recipient_ids: list[str] = []

            if isinstance(channel, DMChannel):
                recipients = [
                    mid for mid in channel.member_ids if mid != sender_id
                ]
                dm_msg = SandboxMessage(
                    message_id=message_id,
                    sender=sender_addr,
                    recipient=recipient_addr,
                    content=content,
                    metadata={"mention_type": "mention"},
                )
                self._deliver_to_inboxes(channel_id, [dm_msg], recipients)
                delivered_recipient_ids = recipients

            elif isinstance(channel, GroupChannel):
                recipients = [
                    mid for mid in channel.member_ids if mid != sender_id
                ]

                if channel.notification_mode == NotificationMode.MENTION:
                    has_here, mentioned_ids = self._parse_mentions(content)
                    for rid in recipients:
                        if has_here or rid in mentioned_ids:
                            mtype = "mention"
                        else:
                            mtype = "ambient"
                        rid_msg = SandboxMessage(
                            message_id=message_id,
                            sender=sender_addr,
                            recipient=recipient_addr,
                            content=content,
                            metadata={"mention_type": mtype},
                        )
                        self._deliver_to_inboxes(channel_id, [rid_msg], [rid])
                else:
                    group_msg = SandboxMessage(
                        message_id=message_id,
                        sender=sender_addr,
                        recipient=recipient_addr,
                        content=content,
                        metadata={"mention_type": "mention"},
                    )
                    self._deliver_to_inboxes(channel_id, [group_msg], recipients)

                delivered_recipient_ids = recipients

            elif isinstance(channel, ProcessorChannel):
                processor = self._processors.get(channel_id)
                if processor is not None:
                    released = processor.accept_message(msg)
                    if released:
                        self._handle_processor_release(
                            channel_id, released, channel
                        )
                        delivered_recipient_ids = list(channel.subscriber_ids)

            self._notify_delivered(channel_id, message_id, sender_id)

            if delivered_recipient_ids:
                self._notify_new_message(
                    channel_id,
                    sender_id,
                    delivered_recipient_ids,
                    message_id,
                    channel.channel_type.value,
                    content,
                    reply_to=reply_to,
                )

            return {"status": "ok"}

    @staticmethod
    def _parse_mentions(content: str) -> tuple[bool, set[str]]:
        """Parse @here and @agent_id mentions from message content.

        Agent IDs may contain word characters and hyphens (e.g. ``agent-b``).

        Returns:
            Tuple of (has_at_here, set_of_mentioned_agent_ids).
        """
        has_here = bool(re.search(r"@here\b", content))
        # Match @<id> where id is word chars / hyphens, exclude @here
        mentioned = {
            m.group(1)
            for m in re.finditer(r"@([\w-]+)", content)
            if m.group(1) != "here"
        }
        return has_here, mentioned

    def _sender_allowed(self, sender_id: str, channel: ChannelDefinition) -> bool:
        """Check if a sender is allowed to write to a channel."""
        if isinstance(channel, (DMChannel, GroupChannel)):
            return sender_id in channel.member_ids
        if isinstance(channel, ProcessorChannel):
            return sender_id in channel.publisher_ids
        return False

    # -- Channel staking (write locking) --

    def _get_stake_condition(self, channel_id: str) -> threading.Condition:
        """Get or create a Condition for a channel's stake queue."""
        with self._stake_lock:
            if channel_id not in self._stake_conditions:
                self._stake_conditions[channel_id] = threading.Condition()
            return self._stake_conditions[channel_id]

    def _acquire_stake(self, channel_id: str, agent_id: str) -> bool:
        """Acquire the write stake for a group channel. Blocks if held.

        Returns True if the agent had to wait (was blocked by another agent).
        Returns False if the lock was acquired immediately.
        Raises TimeoutError if the wait exceeds STAKE_TIMEOUT_SECONDS.
        """
        condition = self._get_stake_condition(channel_id)
        waited = False

        with condition:
            while True:
                now = time.monotonic()
                existing = self._channel_stakes.get(channel_id)

                if existing is None:
                    # Lock is free
                    self._channel_stakes[channel_id] = (agent_id, now)
                    return waited

                holder, acquired_at = existing
                if holder == agent_id:
                    # Same agent re-acquiring — idempotent
                    self._channel_stakes[channel_id] = (agent_id, now)
                    return waited

                # Check if the stake expired
                if (now - acquired_at) >= STAKE_TIMEOUT_SECONDS:
                    logger.warning(
                        "Stake on %s held by %s expired (%.1fs), reclaiming for %s",
                        channel_id, holder, now - acquired_at, agent_id,
                    )
                    self._channel_stakes[channel_id] = (agent_id, now)
                    return waited

                # Lock is held — wait in FIFO queue
                waited = True
                got_notified = condition.wait(timeout=STAKE_TIMEOUT_SECONDS)
                if not got_notified:
                    # Timeout waiting — check if expired or give up
                    now2 = time.monotonic()
                    existing2 = self._channel_stakes.get(channel_id)
                    if existing2 is not None:
                        holder2, acquired_at2 = existing2
                        if holder2 != agent_id and (now2 - acquired_at2) < STAKE_TIMEOUT_SECONDS:
                            raise TimeoutError(
                                f"Timed out waiting for stake on {channel_id} "
                                f"(held by {holder2})"
                            )
                    # Expired or released — loop will re-check and acquire

    def _release_stake(self, channel_id: str, agent_id: str) -> None:
        """Release the write stake, waking the next queued agent."""
        condition = self._get_stake_condition(channel_id)
        with condition:
            existing = self._channel_stakes.get(channel_id)
            if existing is not None and existing[0] == agent_id:
                del self._channel_stakes[channel_id]
            condition.notify_all()

    def _cleanup_stakes_for_agent(self, agent_id: str) -> None:
        """Release all stakes held by an agent (called after step or unregister)."""
        for channel_id in list(self._channel_stakes.keys()):
            existing = self._channel_stakes.get(channel_id)
            if existing is not None and existing[0] == agent_id:
                logger.info("Cleanup: releasing leaked stake on %s for agent %s", channel_id, agent_id)
                self._release_stake(channel_id, agent_id)
        # Also clear any lingering typing indicators
        for channel_id in list(self._typing.keys()):
            if agent_id in self._typing.get(channel_id, set()):
                self._clear_typing(channel_id, agent_id)

    def _deliver_to_inboxes(
        self,
        channel_id: str,
        messages: list[SandboxMessage],
        recipient_ids: list[str],
    ) -> None:
        """Deliver messages to recipient inboxes."""
        for rid in recipient_ids:
            self._inboxes[rid].extend(messages)
            if logger.isEnabledFor(logging.DEBUG):
                for msg in messages:
                    logger.debug(
                        "[inbox-deliver] %s ← %s (ch=%s, msg_id=%s) inbox_len=%d",
                        rid, msg.sender.endpoint_id, channel_id,
                        msg.message_id, len(self._inboxes[rid]),
                    )

    def _handle_processor_release(
        self,
        channel_id: str,
        released: list[SandboxMessage],
        channel: ProcessorChannel,
    ) -> None:
        """Handle processor-released messages by delivering to subscribers."""
        self._deliver_to_inboxes(channel_id, released, list(channel.subscriber_ids))

    def _notify_delivered(
        self,
        channel_id: str,
        message_id: str,
        sender_id: str,
        error: str = "",
    ) -> None:
        """Notify callbacks that a message was delivered."""
        ts = dt.datetime.now(dt.UTC).isoformat()
        for cb in self._on_message_delivered:
            try:
                cb(channel_id, message_id, sender_id, ts, error)
            except Exception:
                logger.exception("Error in message_delivered callback")

    def _notify_new_message(
        self,
        channel_id: str,
        sender_id: str,
        recipient_ids: list[str],
        message_id: str,
        channel_type: str,
        content: str = "",
        reply_to: str = "",
    ) -> None:
        """Notify callbacks that new messages are available."""
        for cb in self._on_new_message:
            try:
                cb(channel_id, sender_id, recipient_ids, message_id, channel_type, content, reply_to)
            except Exception:
                logger.exception("Error in new_message callback")

    # -- Reading messages --

    def read_inbox(self, agent_id: str) -> list[SandboxMessage]:
        """Return and clear the agent's inbox.

        Args:
            agent_id: The agent whose inbox to read.

        Returns:
            List of messages, now cleared from the inbox.
        """
        with self._lock:
            messages = list(self._inboxes.get(agent_id, []))
            self._inboxes[agent_id] = []
            if messages and logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "[inbox-read] %s drained %d msg(s): %s",
                    agent_id, len(messages),
                    [(m.message_id, m.sender.endpoint_id) for m in messages],
                )
            return messages

    def peek_inbox(self, agent_id: str) -> list[SandboxMessage]:
        """Return the agent's inbox without clearing.

        Args:
            agent_id: The agent whose inbox to peek.

        Returns:
            List of messages, still in the inbox.
        """
        with self._lock:
            return list(self._inboxes.get(agent_id, []))

    def load_channel_history(self, channel_id: str) -> list[dict[str, Any]]:
        """Load full channel history from the store.

        Args:
            channel_id: Channel to load history for.

        Returns:
            List of message dicts from the store.
        """
        if self._store is None:
            return []
        return self._store.load_channel(channel_id)

    def inject_seed(
        self,
        channel_id: str,
        content: str,
        sender_id: str = "system",
        recipients: list[str] | None = None,
    ) -> None:
        """Inject a seed message into a channel.

        By default the message is delivered to every member's inbox.  Pass
        *recipients* to deliver only to specific agents (e.g. to kick-start
        a single agent while others stay in hibernation).

        Args:
            channel_id: Target channel.
            content: Seed message text.
            sender_id: Sender label (default "system").
            recipients: Optional list of agent IDs to deliver to.
                        If None, delivers to all channel members.
        """
        with self._lock:
            channel = self._channels.get(channel_id)
            if channel is None:
                raise KeyError(f"Channel not found: {channel_id}")

            msg_id = f"seed-{channel_id}"
            sender_addr = EndpointAddress(endpoint_id=sender_id, kind=EndpointKind.AGENT)
            recipient_addr = EndpointAddress(endpoint_id=channel_id, kind=EndpointKind.GROUP_CHAT)

            msg = SandboxMessage(
                message_id=msg_id,
                sender=sender_addr,
                recipient=recipient_addr,
                content=content,
            )

            msg_index = self._channel_counters[channel_id]
            self._channel_counters[channel_id] += 1
            if self._store:
                self._store.append_message(
                    channel_id=channel_id,
                    message_index=msg_index,
                    sender_id=sender_id,
                    content=content,
                    timestamp=dt.datetime.now(dt.UTC).isoformat(),
                )

            # Determine recipients
            if recipients is None:
                if isinstance(channel, (DMChannel, GroupChannel)):
                    recipients = list(channel.member_ids)
                elif isinstance(channel, ProcessorChannel):
                    recipients = list(channel.subscriber_ids)
                else:
                    recipients = []

            self._deliver_to_inboxes(channel_id, [msg], recipients)

            if recipients:
                self._notify_new_message(
                    channel_id,
                    sender_id,
                    recipients,
                    msg_id,
                    channel.channel_type.value,
                    content,
                )

    def leave_channel(self, agent_id: str, channel_id: str) -> None:
        """Remove an agent from a channel, auto-deleting if empty.

        Args:
            agent_id: Agent leaving the channel.
            channel_id: Channel to leave.
        """
        with self._lock:
            channel = self._channels.get(channel_id)
            if channel is None:
                return

            if isinstance(channel, (DMChannel, GroupChannel)):
                if agent_id in channel.member_ids:
                    channel.member_ids.remove(agent_id)
                if not channel.member_ids:
                    self._remove_channel_internal(channel_id)
            elif isinstance(channel, ProcessorChannel):
                if agent_id in channel.publisher_ids:
                    channel.publisher_ids.remove(agent_id)
                if agent_id in channel.subscriber_ids:
                    channel.subscriber_ids.remove(agent_id)
                if not channel.publisher_ids and not channel.subscriber_ids:
                    self._remove_channel_internal(channel_id)
