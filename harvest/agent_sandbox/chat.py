"""Chat router for the unified channel-based chat system.

One ChatRouter instance exists per agent sandbox. It manages all channels
within that sandbox and routes messages between agents.
"""


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

    # Pseudo-agent ID used as the sender for seed messages.  Agents see
    # this label in wake-event formatting and know the message is a
    # pre-fabricated scenario prompt — not a real participant.
    SEED_SENDER_ID: str = "scenario"

    def __init__(
        self,
        store: ChatStore | None = None,
        sandbox_bus: Any | None = None,
    ) -> None:
        """Initialize the chat router.

        Args:
            store: Optional ChatStore for message persistence.
            sandbox_bus: Optional per-sandbox SyncEventBus for event-driven
                communication. When provided, the router subscribes to
                request events and dispatches responses on this bus.
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
        self._sandbox_bus = sandbox_bus

        # Channel staking (write locking) for group channels
        self._stake_lock = threading.Lock()
        self._channel_stakes: dict[str, tuple[str, float]] = {}  # channel_id → (holder_id, mono_time)
        self._stake_conditions: dict[str, threading.Condition] = {}
        self._stake_queues: dict[str, list[threading.Event]] = defaultdict(list)

        # Event-driven FIFO stake queues (used when sandbox_bus is provided)
        self._event_stake_queues: dict[str, list[Any]] = defaultdict(list)
        self._stake_timers: dict[str, threading.Timer] = {}

        # Typing indicators: tracks agents currently trying to send
        self._typing: dict[str, set[str]] = defaultdict(set)  # channel_id → {agent_ids}
        self._on_typing_changed: list[Any] = []

        # Wire event-driven handlers if sandbox bus provided
        if sandbox_bus is not None:
            self._wire_event_handlers()

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

        This is the **direct API path** (called from legacy tool wrappers
        that hold a ChatRouter reference).  For the event-driven equivalent,
        see :meth:`_handle_send`.

        **Write-stake mechanism (group channels):**  Before sending, a
        write stake is acquired via :meth:`_acquire_stake`.  If the lock
        is free the message is sent immediately.  If another agent holds
        the lock, the call **blocks** in a FIFO queue with a **30-second
        timeout**.  When the caller finally acquires the stake after
        waiting, the channel context has changed, so the method returns
        ``{"status": "channel_updated", ...}`` with the latest messages
        instead of sending -- the caller now holds the lock and should
        compose a fresh response.

        **Typing indicator:** A typing indicator is set before the stake
        attempt (``_set_typing``) and cleared in a ``finally`` block after
        send or error (``_clear_typing``), ensuring it is always removed.

        Args:
            sender_id: The sending agent's ID.
            channel_id: Target channel.
            content: Message text.
            message_id: Unique message identifier.
            reply_to: Comma-separated short message IDs being replied to.

        Returns:
            Dict with ``'status'`` and additional fields depending on
            outcome (``'sent'``, ``'channel_updated'``, or ``'error'``).
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

            # Notify observers. For DM/Group channels, always notify even
            # when the sender is the only member — the message was written to
            # the channel and should be visible to external observers (debug
            # monitor, GUI, etc.). For processor channels, only notify when
            # messages are actually released to subscribers.
            if isinstance(channel, ProcessorChannel):
                if delivered_recipient_ids:
                    self._notify_new_message(
                        channel_id, sender_id, delivered_recipient_ids,
                        message_id, channel.channel_type.value, content,
                        reply_to=reply_to,
                    )
            else:
                all_member_ids = delivered_recipient_ids or [sender_id]
                self._notify_new_message(
                    channel_id, sender_id, all_member_ids,
                    message_id, channel.channel_type.value, content,
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
        if sender_id == "admin":
            return True
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

    def drain_channel_messages(self, agent_id: str, channel_id: str) -> list[SandboxMessage]:
        """Remove and return messages for a specific channel from an agent's inbox.

        This prevents stale ``inbox_updated`` loops where the same messages
        are returned repeatedly on every send attempt.

        Args:
            agent_id: The agent whose inbox to drain.
            channel_id: Only remove messages for this channel.

        Returns:
            List of removed messages.
        """
        with self._lock:
            all_msgs = self._inboxes.get(agent_id, [])
            drained = [
                m for m in all_msgs
                if (m.recipient.endpoint_id if m.recipient else "") == channel_id
            ]
            self._inboxes[agent_id] = [
                m for m in all_msgs
                if (m.recipient.endpoint_id if m.recipient else "") != channel_id
            ]
            if drained and logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "[inbox-drain] %s drained %d msg(s) for channel %s",
                    agent_id, len(drained), channel_id,
                )
            return drained

    def load_channel_history(self, channel_id: str) -> list[dict[str, Any]]:
        """Load full channel history from the store.

        Args:
            channel_id: Channel to load history for.

        Returns:
            List of message dicts from the store.
        """
        if self._store is None:
            return []
        rows = self._store.load_channel(channel_id)
        for row in rows:
            if row.get("sender_id") == self.SEED_SENDER_ID:
                row["sender_id"] = "system"
                row["is_seed_prompt"] = True
                row["note"] = (
                    "This is the channel topic set by the system, not a "
                    "message from another agent. Engage with the topic."
                )
        return rows

    def inject_seed(
        self,
        channel_id: str,
        content: str,
        sender_id: str | None = None,
        recipients: list[str] | None = None,
    ) -> None:
        """Inject a seed message into a channel.

        By default the message is delivered to every member's inbox.  Pass
        *recipients* to deliver only to specific agents (e.g. to kick-start
        a single agent while others stay in hibernation).

        Args:
            channel_id: Target channel.
            content: Seed message text.
            sender_id: Sender label (defaults to :attr:`SEED_SENDER_ID`).
            recipients: Optional list of agent IDs to deliver to.
                        If None, delivers to all channel members.
        """
        if sender_id is None:
            sender_id = self.SEED_SENDER_ID
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

    # -- Event-driven handlers (sandbox bus) ---------------------------------

    def _wire_event_handlers(self) -> None:
        """Subscribe to request events on the sandbox bus."""
        from harvest.agent_sandbox.chat_events import (
            AddAgentToChannelRequest,
            CreateChannelRequest,
            LeaveChannelRequest,
            ListChannelsRequest,
            ReadMessagesRequest,
            ReleaseStake,
            RequestStake,
            SendChatMessage,
        )

        bus = self._sandbox_bus
        bus.on(RequestStake, self._handle_request_stake)
        bus.on(ReleaseStake, self._handle_release_stake)
        bus.on(SendChatMessage, self._handle_send)
        bus.on(ReadMessagesRequest, self._handle_read)
        bus.on(ListChannelsRequest, self._handle_list)
        bus.on(AddAgentToChannelRequest, self._handle_add_to_channel)
        bus.on(CreateChannelRequest, self._handle_create_channel)
        bus.on(LeaveChannelRequest, self._handle_leave_channel)

    def _handle_request_stake(self, event: Any) -> None:
        """Grant immediately, re-entrant grant, or enqueue. Never blocks."""
        from harvest.agent_sandbox.chat_events import StakeGranted, StakeQueued

        channel = self._channels.get(event.channel_id)
        if channel is None or not isinstance(channel, GroupChannel):
            self._sandbox_bus.dispatch(StakeGranted(
                agent_id=event.agent_id,
                channel_id=event.channel_id,
                request_id=event.request_id,
            ))
            return

        with self._stake_lock:
            existing = self._channel_stakes.get(event.channel_id)
            now = time.monotonic()

            if existing is None:
                self._channel_stakes[event.channel_id] = (event.agent_id, now)
                self._start_hold_timer(event.channel_id, event.agent_id)
                self._sandbox_bus.dispatch(StakeGranted(
                    agent_id=event.agent_id,
                    channel_id=event.channel_id,
                    request_id=event.request_id,
                ))
            elif existing[0] == event.agent_id:
                self._channel_stakes[event.channel_id] = (event.agent_id, now)
                self._refresh_hold_timer(event.channel_id, event.agent_id)
                self._sandbox_bus.dispatch(StakeGranted(
                    agent_id=event.agent_id,
                    channel_id=event.channel_id,
                    request_id=event.request_id,
                ))
            else:
                queue = self._event_stake_queues[event.channel_id]
                queue.append(event)
                self._sandbox_bus.dispatch(StakeQueued(
                    agent_id=event.agent_id,
                    channel_id=event.channel_id,
                    request_id=event.request_id,
                    position=len(queue),
                ))

    def _handle_release_stake(self, event: Any) -> None:
        """Explicit abort release — agent acquired stake but chose not to send."""
        with self._stake_lock:
            existing = self._channel_stakes.get(event.channel_id)
            if existing is None or existing[0] != event.agent_id:
                return
            self._cancel_hold_timer(event.channel_id)
            del self._channel_stakes[event.channel_id]
            self._grant_next_in_queue(event.channel_id)

    def _handle_send(self, event: Any) -> None:
        """Event-driven send path: deliver a message in response to a :class:`SendChatMessage` event.

        This is the counterpart of :meth:`send_message` for the event-bus
        architecture.  It performs the following steps:

        1. Resolves the target channel and builds a :class:`SandboxMessage`.
        2. Determines recipient IDs from channel membership and delivers
           the message to each recipient's inbox via
           :meth:`_deliver_to_inboxes`.
        3. Persists the message to the chat store (if one is configured).
        4. Dispatches a :class:`ChatMessageDelivered` event on the sandbox
           bus so the calling :class:`ChatRouterClient` can unblock.
        5. Dispatches a :class:`NewChatMessage` event so listening agents
           are woken from hibernation.
        6. Releases the sender's write stake (if held) and grants the
           next queued agent.
        """
        from harvest.agent_sandbox.chat_events import ChatMessageDelivered, NewChatMessage
        import uuid as _uuid

        channel = self._channels.get(event.channel_id)
        if channel is None:
            self._sandbox_bus.dispatch(ChatMessageDelivered(
                channel_id=event.channel_id,
                message_id=event.message_id,
                sender_id=event.sender_id,
                error="channel_not_found",
            ))
            return

        sender_addr = self._agents.get(event.sender_id)
        if sender_addr is None:
            sender_addr = EndpointAddress(
                endpoint_id=event.sender_id, kind=EndpointKind.AGENT
            )
        recipient_addr = EndpointAddress(
            endpoint_id=event.channel_id, kind=EndpointKind.GROUP_CHAT
        )
        msg = SandboxMessage(
            message_id=event.message_id or _uuid.uuid4().hex,
            sender=sender_addr,
            recipient=recipient_addr,
            content=event.content,
        )
        # Determine recipient list from channel membership, excluding the
        # sender so agents don't receive their own messages in their inbox.
        if isinstance(channel, (DMChannel, GroupChannel)):
            recipient_ids = [
                mid for mid in channel.member_ids if mid != event.sender_id
            ]
        elif isinstance(channel, ProcessorChannel):
            recipient_ids = [
                sid for sid in channel.subscriber_ids if sid != event.sender_id
            ]
        else:
            recipient_ids = []
        self._deliver_to_inboxes(event.channel_id, [msg], recipient_ids)

        if self._store is not None:
            msg_index = self._channel_counters.get(event.channel_id, 0)
            self._channel_counters[event.channel_id] = msg_index + 1
            self._store.append_message(
                channel_id=event.channel_id,
                message_index=msg_index,
                sender_id=event.sender_id,
                content=event.content,
            )

        self._sandbox_bus.dispatch(ChatMessageDelivered(
            channel_id=event.channel_id,
            message_id=msg.message_id,
            sender_id=event.sender_id,
            timestamp_delivered=msg.created_at.isoformat(),
        ))

        self._sandbox_bus.dispatch(NewChatMessage(
            channel_id=event.channel_id,
            sender_id=event.sender_id,
            recipient_ids=recipient_ids,
            message_id=msg.message_id,
            channel_type=channel.channel_type.value if hasattr(channel.channel_type, 'value') else str(channel.channel_type),
        ))

        self._notify_new_message(
            event.channel_id, event.sender_id, recipient_ids,
            msg.message_id, channel.channel_type.value,
            content=event.content, reply_to=event.reply_to,
        )

        with self._stake_lock:
            existing = self._channel_stakes.get(event.channel_id)
            if existing and existing[0] == event.sender_id:
                self._cancel_hold_timer(event.channel_id)
                del self._channel_stakes[event.channel_id]
                self._grant_next_in_queue(event.channel_id)

    def _handle_read(self, event: Any) -> None:
        """Return inbox contents or channel history."""
        from harvest.agent_sandbox.chat_events import ReadMessagesResponse

        def _msg_to_dict(m: SandboxMessage) -> dict[str, Any]:
            """Convert a SandboxMessage to a dict with channel_id."""
            ch = m.recipient.endpoint_id if m.recipient else ""
            sender = m.sender.endpoint_id if m.sender else ""
            d: dict[str, Any] = {
                "channel_id": ch,
                "sender": sender,
                "content": m.content,
                "message_id": m.message_id,
                "timestamp": m.created_at.isoformat(),
            }
            if sender == self.SEED_SENDER_ID:
                d["sender"] = "system"
                d["is_seed_prompt"] = True
                d["note"] = (
                    "This is the channel topic set by the system, not a "
                    "message from another agent. Engage with the topic."
                )
            return d

        if event.channel_id and event.history:
            messages = self.load_channel_history(event.channel_id)
        elif event.channel_id:
            with self._lock:
                all_msgs = self._inboxes.get(event.agent_id, [])
                channel_msgs = [
                    m for m in all_msgs
                    if (m.recipient.endpoint_id if m.recipient else "") == event.channel_id
                ]
                self._inboxes[event.agent_id] = [
                    m for m in all_msgs
                    if (m.recipient.endpoint_id if m.recipient else "") != event.channel_id
                ]
            messages = [_msg_to_dict(m) for m in channel_msgs]
        else:
            msgs = self.read_inbox(event.agent_id)
            messages = [_msg_to_dict(m) for m in msgs]

        self._sandbox_bus.dispatch(ReadMessagesResponse(
            agent_id=event.agent_id,
            request_id=event.request_id,
            messages=messages,
        ))

    def _handle_list(self, event: Any) -> None:
        """Return channels visible to the agent."""
        from harvest.agent_sandbox.chat_events import ListChannelsResponse

        channels = self.list_channels_for_agent(event.agent_id)
        channel_dicts = []
        for ch in channels:
            info: dict[str, Any] = {
                "channel_id": ch.channel_id,
                "type": ch.channel_type.value if hasattr(ch.channel_type, 'value') else str(ch.channel_type),
                "description": getattr(ch, "description", ""),
            }
            if hasattr(ch, "member_ids"):
                info["members"] = list(ch.member_ids)
            channel_dicts.append(info)

        self._sandbox_bus.dispatch(ListChannelsResponse(
            agent_id=event.agent_id,
            request_id=event.request_id,
            channels=channel_dicts,
        ))

    def _handle_add_to_channel(self, event: Any) -> None:
        """Add an agent to a channel."""
        from harvest.agent_sandbox.chat_events import AddAgentToChannelResponse

        with self._lock:
            channel = self._channels.get(event.channel_id)
            if channel is None:
                self._sandbox_bus.dispatch(AddAgentToChannelResponse(
                    requester_id=event.requester_id, agent_id=event.agent_id,
                    channel_id=event.channel_id, request_id=event.request_id,
                    status="error", error="channel_not_found",
                ))
                return

            if isinstance(channel, (DMChannel, GroupChannel)):
                if event.agent_id in channel.member_ids:
                    self._sandbox_bus.dispatch(AddAgentToChannelResponse(
                        requester_id=event.requester_id, agent_id=event.agent_id,
                        channel_id=event.channel_id, request_id=event.request_id,
                        status="error", error="already_member",
                    ))
                    return
                channel.member_ids.append(event.agent_id)
            else:
                self._sandbox_bus.dispatch(AddAgentToChannelResponse(
                    requester_id=event.requester_id, agent_id=event.agent_id,
                    channel_id=event.channel_id, request_id=event.request_id,
                    status="error", error="not_supported_for_channel_type",
                ))
                return

        self._sandbox_bus.dispatch(AddAgentToChannelResponse(
            requester_id=event.requester_id, agent_id=event.agent_id,
            channel_id=event.channel_id, request_id=event.request_id,
            status="added",
        ))

    def _handle_create_channel(self, event: Any) -> None:
        """Create a new channel in response to a CreateChannelRequest."""
        from harvest.agent_sandbox.chat_events import CreateChannelResponse

        try:
            member_ids = list(event.member_ids)
            if event.requester_id not in member_ids:
                member_ids.insert(0, event.requester_id)

            ch_type = event.channel_type
            if ch_type == "dm":
                channel = DMChannel(
                    channel_id=event.channel_id,
                    member_ids=member_ids,
                    description=event.description,
                    created_by=event.requester_id,
                )
            elif ch_type == "group":
                channel = GroupChannel(
                    channel_id=event.channel_id,
                    member_ids=member_ids,
                    description=event.description,
                    created_by=event.requester_id,
                )
            else:
                self._sandbox_bus.dispatch(CreateChannelResponse(
                    requester_id=event.requester_id, request_id=event.request_id,
                    channel_id=event.channel_id,
                    status="error", error=f"unsupported_channel_type: {ch_type}",
                ))
                return

            self.create_channel(channel)
            self._sandbox_bus.dispatch(CreateChannelResponse(
                requester_id=event.requester_id, request_id=event.request_id,
                channel_id=event.channel_id, status="created",
            ))
        except Exception as exc:
            self._sandbox_bus.dispatch(CreateChannelResponse(
                requester_id=event.requester_id, request_id=event.request_id,
                channel_id=event.channel_id,
                status="error", error=str(exc),
            ))

    def _handle_leave_channel(self, event: Any) -> None:
        """Remove an agent from a channel in response to a LeaveChannelRequest."""
        from harvest.agent_sandbox.chat_events import LeaveChannelResponse

        try:
            self.leave_channel(event.agent_id, event.channel_id)
            self._sandbox_bus.dispatch(LeaveChannelResponse(
                agent_id=event.agent_id, request_id=event.request_id,
                channel_id=event.channel_id, status="left",
            ))
        except Exception as exc:
            self._sandbox_bus.dispatch(LeaveChannelResponse(
                agent_id=event.agent_id, request_id=event.request_id,
                channel_id=event.channel_id,
                status="error", error=str(exc),
            ))

    # -- Event-driven stake management ---------------------------------------

    def _grant_next_in_queue(self, channel_id: str) -> None:
        """Pop the next queued request and grant it. Must hold _stake_lock."""
        from harvest.agent_sandbox.chat_events import StakeGranted

        queue = self._event_stake_queues.get(channel_id)
        if not queue:
            return
        next_req = queue.pop(0)
        now = time.monotonic()
        self._channel_stakes[channel_id] = (next_req.agent_id, now)
        self._start_hold_timer(channel_id, next_req.agent_id)
        self._sandbox_bus.dispatch(StakeGranted(
            agent_id=next_req.agent_id,
            channel_id=channel_id,
            request_id=next_req.request_id,
        ))

    def _start_hold_timer(self, channel_id: str, agent_id: str) -> None:
        """Start a timer that revokes the stake after STAKE_HOLD_SECONDS."""
        self._cancel_hold_timer(channel_id)
        timer = threading.Timer(
            STAKE_HOLD_SECONDS,
            self._on_hold_timer_expired,
            args=(channel_id, agent_id),
        )
        timer.daemon = True
        timer.start()
        self._stake_timers[channel_id] = timer

    def _refresh_hold_timer(self, channel_id: str, agent_id: str) -> None:
        """Restart the hold timer."""
        self._start_hold_timer(channel_id, agent_id)

    def _cancel_hold_timer(self, channel_id: str) -> None:
        """Cancel an active hold timer."""
        timer = self._stake_timers.pop(channel_id, None)
        if timer is not None:
            timer.cancel()

    def _on_hold_timer_expired(self, channel_id: str, agent_id: str) -> None:
        """Called when STAKE_HOLD_SECONDS elapses without release or send."""
        from harvest.agent_sandbox.chat_events import StakeExpired

        with self._stake_lock:
            existing = self._channel_stakes.get(channel_id)
            if existing is None or existing[0] != agent_id:
                return
            logger.warning(
                "Stake on %s held by %s expired after %.0fs, revoking",
                channel_id, agent_id, STAKE_HOLD_SECONDS,
            )
            del self._channel_stakes[channel_id]
            self._sandbox_bus.dispatch(StakeExpired(
                agent_id=agent_id,
                channel_id=channel_id,
            ))
            self._grant_next_in_queue(channel_id)
