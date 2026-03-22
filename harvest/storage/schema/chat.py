"""Chat message schema and store for the unified channel system."""

from __future__ import annotations

from typing import Any

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from harvest.storage.base import FlexibleStorage, StorageRecord


class ChatMessageRecord(StorageRecord):
    """Persisted chat message row."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[str]
    message_index: Mapped[int]
    sender_id: Mapped[str]
    content: Mapped[str]
    timestamp: Mapped[str]

    __table_args__ = (UniqueConstraint("channel_id", "message_index"),)


class ChatStore:
    """Append-only chat message log backed by FlexibleStorage."""

    def __init__(self, database_url: str = "sqlite:///:memory:") -> None:
        """Initialize the chat store.

        Args:
            database_url: SQLAlchemy database URL.
        """
        self._storage = FlexibleStorage(database_url=database_url)
        self._storage.register_table(ChatMessageRecord)

    def append_message(
        self,
        channel_id: str,
        message_index: int,
        sender_id: str,
        content: str,
        timestamp: str = "",
    ) -> None:
        """Persist a single chat message.

        Args:
            channel_id: Channel the message belongs to.
            message_index: Ordering index within the channel.
            sender_id: ID of the sending agent.
            content: Message text.
            timestamp: ISO UTC timestamp.
        """
        import datetime as dt

        if not timestamp:
            timestamp = dt.datetime.now(dt.UTC).isoformat()

        row = {
            "channel_id": channel_id,
            "message_index": message_index,
            "sender_id": sender_id,
            "content": content,
            "timestamp": timestamp,
        }
        self._storage.upsert_rows(ChatMessageRecord, [row])

    def load_channel(self, channel_id: str) -> list[dict[str, Any]]:
        """Fetch all messages for a channel, ordered by message_index.

        Args:
            channel_id: Channel to load.

        Returns:
            List of message dicts ordered by message_index.
        """
        frame = self._storage.fetch_rows(
            ChatMessageRecord,
            filters={"channel_id": channel_id},
            timestamp_field="message_index",
            order_by=[("message_index", True)],
        )
        if frame.is_empty():
            return []
        return frame.to_dicts()

    def list_channels(self) -> list[str]:
        """Return distinct channel IDs.

        Returns:
            Sorted list of unique channel IDs.
        """
        frame = self._storage.fetch_rows(ChatMessageRecord)
        if frame.is_empty():
            return []
        return frame["channel_id"].unique().sort().to_list()

    def delete_channel(self, channel_id: str) -> None:
        """Delete all messages for a channel.

        Args:
            channel_id: Channel to purge.
        """
        self._storage.delete_rows(
            ChatMessageRecord,
            filters={"channel_id": channel_id},
        )
