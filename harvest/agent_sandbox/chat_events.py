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
    reply_to: str = ""


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


# -- Staking (write locking) ------------------------------------------------


class RequestStake(HarvestEvent):
    """Agent requests the write lock on a channel."""

    agent_id: str
    channel_id: str
    request_id: str


class StakeGranted(HarvestEvent):
    """ChatRouter grants the write lock.

    Fired immediately if the stake is free, or later when the agent reaches
    the front of the FIFO queue.
    """

    agent_id: str
    channel_id: str
    request_id: str


class StakeQueued(HarvestEvent):
    """The stake is currently held. The request has been enqueued.

    The agent's send_message tool returns immediately, telling the LLM
    that a StakeGranted event will arrive later.
    """

    agent_id: str
    channel_id: str
    request_id: str
    position: int = 0


class StakeExpired(HarvestEvent):
    """The agent's stake timed out — revoked and given to the next in queue."""

    agent_id: str
    channel_id: str


class ReleaseStake(HarvestEvent):
    """Agent explicitly releases the write lock without sending.

    Used only as an abort mechanism. Normal sends auto-release on delivery.
    """

    agent_id: str
    channel_id: str


# -- Reads -------------------------------------------------------------------


class ReadMessagesRequest(HarvestEvent):
    """Agent requests inbox contents or channel history."""

    agent_id: str
    request_id: str
    channel_id: str = ""
    history: bool = False


class ReadMessagesResponse(HarvestEvent):
    """ChatRouter returns requested messages."""

    agent_id: str
    request_id: str
    messages: list[dict] = Field(default_factory=list)


# -- Channel listing ---------------------------------------------------------


class ListChannelsRequest(HarvestEvent):
    """Agent requests its visible channels."""

    agent_id: str
    request_id: str
    channel_type: str = ""


class ListChannelsResponse(HarvestEvent):
    """ChatRouter returns channel list."""

    agent_id: str
    request_id: str
    channels: list[dict] = Field(default_factory=list)


# -- Channel membership ------------------------------------------------------


class AddAgentToChannelRequest(HarvestEvent):
    """Agent requests adding another agent (or itself) to a channel."""

    requester_id: str
    agent_id: str
    channel_id: str
    request_id: str


class AddAgentToChannelResponse(HarvestEvent):
    """ChatRouter confirms or rejects the membership change."""

    requester_id: str
    agent_id: str
    channel_id: str
    request_id: str
    status: str = ""
    error: str = ""


# -- Typing ------------------------------------------------------------------


class TypingChanged(HarvestEvent):
    """Agent started or stopped typing on a channel."""

    channel_id: str
    agent_id: str
    is_typing: bool = False
