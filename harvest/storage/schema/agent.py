"""Conversation history schema and store for the Harvest agent."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from harvest.harvest_agent import (
    Message,
    SummaryMessage,
    TextMessage,
    ToolCallMessage,
    ToolCallRecord,
    ToolResultMessage,
)
from harvest.storage.base import FlexibleStorage, StorageRecord


class ConversationHistory(StorageRecord):
    """Persisted conversation message row."""

    __tablename__ = "conversation_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str]
    turn_index: Mapped[int]
    message_type: Mapped[str]
    role: Mapped[str]
    content: Mapped[str | None] = mapped_column(nullable=True, default=None)
    tool_call_id: Mapped[str | None] = mapped_column(nullable=True, default=None)
    tool_calls_json: Mapped[str | None] = mapped_column(nullable=True, default=None)
    timestamp: Mapped[str]

    __table_args__ = (UniqueConstraint("session_id", "turn_index"),)


def _message_to_row(session_id: str, turn_index: int, message: Message) -> dict[str, Any]:
    """Convert a Message subclass to a storage row dict."""

    base = {
        "session_id": session_id,
        "turn_index": turn_index,
        "role": message.role,
        "timestamp": message.timestamp.isoformat(),
    }

    if isinstance(message, SummaryMessage):
        base["message_type"] = "summary"
        base["content"] = json.dumps({
            "summary": message.content,
            "summarized_turn_count": message.summarized_turn_count,
            "summary_generation": message.summary_generation,
        })
    elif isinstance(message, ToolCallMessage):
        base["message_type"] = "tool_call"
        base["content"] = message.content
        base["tool_calls_json"] = json.dumps([tc.to_dict() for tc in message.tool_calls])
    elif isinstance(message, ToolResultMessage):
        base["message_type"] = "tool_result"
        base["content"] = message.content
        base["tool_call_id"] = message.tool_call_id
    elif isinstance(message, TextMessage):
        base["message_type"] = "text"
        base["content"] = message.content
    else:
        base["message_type"] = "text"
        base["content"] = ""

    return base


class ConversationStore:
    """Append-only conversation log backed by FlexibleStorage."""

    def __init__(self, database_url: str = "sqlite:///:memory:") -> None:
        self._storage = FlexibleStorage(database_url=database_url)
        self._storage.register_table(ConversationHistory)

    def append_message(self, session_id: str, turn_index: int, message: Message) -> None:
        """Persist a single message."""
        row = _message_to_row(session_id, turn_index, message)
        self._storage.upsert_rows(ConversationHistory, [row])

    def load_log(self, session_id: str) -> list[dict[str, Any]]:
        """Fetch full log for a session, ordered by turn_index."""
        frame = self._storage.fetch_rows(
            ConversationHistory,
            filters={"session_id": session_id},
            timestamp_field="turn_index",
            order_by=[("turn_index", True)],
        )
        if frame.is_empty():
            return []
        return frame.to_dicts()

    def list_sessions(self) -> list[str]:
        """Return distinct session IDs."""
        frame = self._storage.fetch_rows(ConversationHistory)
        if frame.is_empty():
            return []
        return frame["session_id"].unique().sort().to_list()
