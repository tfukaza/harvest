"""Fixtures for channel and chat router tests."""

from __future__ import annotations

import pytest

from harvest.agent_sandbox.channels import (
    AggregationProcessorChannel,
    ChannelType,
    DMChannel,
    GatedProcessorChannel,
    GroupChannel,
    NotificationMode,
)
from harvest.agent_sandbox.chat import ChatRouter
from harvest.storage.schema.chat import ChatStore


@pytest.fixture
def chat_store() -> ChatStore:
    """Create an in-memory ChatStore."""
    return ChatStore(database_url="sqlite:///:memory:")


@pytest.fixture
def router(chat_store: ChatStore) -> ChatRouter:
    """Create a ChatRouter with an in-memory store."""
    return ChatRouter(store=chat_store)


@pytest.fixture
def router_no_store() -> ChatRouter:
    """Create a ChatRouter without persistence."""
    return ChatRouter()


def make_dm_channel(
    agent_a: str = "agent-a",
    agent_b: str = "agent-b",
    channel_id: str | None = None,
) -> DMChannel:
    """Create a DM channel between two agents."""
    if channel_id is None:
        ids = sorted([agent_a, agent_b])
        channel_id = f"dm:{ids[0]}:{ids[1]}"
    return DMChannel(
        channel_id=channel_id,
        member_ids=[agent_a, agent_b],
    )


def make_group_channel(
    channel_id: str = "group-1",
    member_ids: list[str] | None = None,
    title: str = "",
    description: str = "",
    notification_mode: NotificationMode = NotificationMode.AMBIENT,
) -> GroupChannel:
    """Create a group channel."""
    return GroupChannel(
        channel_id=channel_id,
        member_ids=member_ids or ["agent-a", "agent-b", "agent-c"],
        title=title,
        description=description,
        notification_mode=notification_mode,
    )


def make_gated_channel(
    channel_id: str = "gated-1",
    publisher_ids: list[str] | None = None,
    subscriber_ids: list[str] | None = None,
) -> GatedProcessorChannel:
    """Create a gated processor channel."""
    return GatedProcessorChannel(
        channel_id=channel_id,
        publisher_ids=publisher_ids or ["agent-a", "agent-b"],
        subscriber_ids=subscriber_ids or ["agent-c"],
    )


def make_aggregation_channel(
    channel_id: str = "agg-1",
    publisher_ids: list[str] | None = None,
    subscriber_ids: list[str] | None = None,
    batch_threshold: int = 3,
) -> AggregationProcessorChannel:
    """Create an aggregation processor channel."""
    return AggregationProcessorChannel(
        channel_id=channel_id,
        publisher_ids=publisher_ids or ["agent-a"],
        subscriber_ids=subscriber_ids or ["agent-b"],
        batch_threshold=batch_threshold,
    )
