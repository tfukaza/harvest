"""Chat event types for the unified channel-based chat system."""

from __future__ import annotations

from pydantic import Field

from harvest.events.base import HarvestEvent


class SendChatMessage(HarvestEvent):
    """An agent requests to send a message to a channel.

    Fired by the agent's send_message tool handler onto the ChatRouter's
    event bus. The agent does not call ChatRouter methods directly.
    """

    sender_id: str
    channel_id: str
    content: str
    message_id: str


class ChatMessageDelivered(HarvestEvent):
    """The router has successfully accepted a message.

    Fired back to the sender as an ACK. The send tool blocks until this
    is received.
    """

    channel_id: str
    message_id: str
    sender_id: str
    timestamp_delivered: str = ""
    error: str = ""


class NewChatMessage(HarvestEvent):
    """New message(s) are available for listed recipients.

    Fired by the router after delivery to inboxes — immediately for DM/group,
    after processor release for processor channels.
    """

    channel_id: str
    sender_id: str
    recipient_ids: list[str] = Field(default_factory=list)
    message_id: str = ""
    channel_type: str = ""


class BatchReleased(HarvestEvent):
    """Aggregation processor released a batch."""

    channel_id: str
    batch_size: int = 0


class GateOpened(HarvestEvent):
    """All publishers have sent, gated processor gate opened."""

    channel_id: str
    publisher_ids: list[str] = Field(default_factory=list)
