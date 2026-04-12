"""Channel definitions for the unified channel-based chat system."""


import enum
from dataclasses import dataclass, field


class ChannelType(enum.Enum):
    """Enumerates the types of channels in the chat system."""

    GROUP = "group"
    PROCESSOR_GATED = "processor_gated"
    PROCESSOR_AGGREGATION = "processor_aggregation"


class NotificationMode(enum.Enum):
    """Controls how group channel messages notify members.

    AMBIENT: All messages are delivered to every member's inbox with full
        content (like a small group chat where everyone sees everything).
    MENTION: Only members explicitly ``@mentioned`` or targeted by ``@here``
        receive a strong notification with message content.  Other members
        get a soft "N new messages" summary (like a large Slack channel).
    """

    AMBIENT = "ambient"
    MENTION = "mention"


@dataclass
class ChannelDefinition:
    """Base definition for all channel types."""

    channel_id: str
    channel_type: ChannelType
    title: str = ""
    description: str = ""
    created_by: str = ""


@dataclass
class GroupChannel(ChannelDefinition):
    """Member-based chat channel.

    Covers both 1-on-1 (DM) and multi-member conversations — a DM is simply
    a group with two members, ``staking_enabled=False``, and AMBIENT
    notification mode.
    """

    channel_type: ChannelType = ChannelType.GROUP
    member_ids: list[str] = field(default_factory=list)
    notification_mode: NotificationMode = NotificationMode.AMBIENT
    staking_enabled: bool = True


@dataclass
class ProcessorChannel(ChannelDefinition):
    """Channel backed by a message processor.

    Agents interact with it identically to a group chat, but routing is
    controlled by processor logic.
    """

    publisher_ids: list[str] = field(default_factory=list)
    subscriber_ids: list[str] = field(default_factory=list)


@dataclass
class GatedProcessorChannel(ProcessorChannel):
    """Gated release: subscribers notified only after ALL publishers have sent."""

    channel_type: ChannelType = ChannelType.PROCESSOR_GATED


@dataclass
class AggregationProcessorChannel(ProcessorChannel):
    """Aggregation: subscribers notified in batches after count threshold."""

    channel_type: ChannelType = ChannelType.PROCESSOR_AGGREGATION
    batch_threshold: int = 1
