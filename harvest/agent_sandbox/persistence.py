"""Persistence scaffolding for agent-runner local state."""


from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def get_current_utc_timestamp() -> datetime:
    """Return the current UTC timestamp for local persistence records."""

    return datetime.now(UTC)


@dataclass(slots=True)
class ReasoningRecord:
    """Represents one persisted reasoning-history record.

    Attributes:
        agent_id: Identifier of the agent that produced the record.
        entry: Opaque reasoning artifact.
        recorded_at: UTC timestamp for the persisted record.
    """

    agent_id: str
    entry: Any
    recorded_at: datetime = field(default_factory=get_current_utc_timestamp)


@dataclass(slots=True)
class ToolResultRecord:
    """Represents one persisted tool-result record.

    Attributes:
        agent_id: Identifier of the agent that observed the tool result.
        tool_name: Logical name of the tool.
        result: Opaque result artifact.
        recorded_at: UTC timestamp for the persisted record.
    """

    agent_id: str
    tool_name: str
    result: Any
    recorded_at: datetime = field(default_factory=get_current_utc_timestamp)


@dataclass(slots=True)
class SessionStateRecord:
    """Represents a persisted session-state snapshot for a runner.

    Attributes:
        runner_id: Identifier of the runner that owns the state.
        state: Opaque session-state payload.
        recorded_at: UTC timestamp for the persisted record.
    """

    runner_id: str
    state: dict[str, Any]
    recorded_at: datetime = field(default_factory=get_current_utc_timestamp)


@dataclass(slots=True)
class RecoverySnapshot:
    """Represents the minimal scaffold for future runner recovery.

    Attributes:
        runner_id: Identifier of the runner that owns the snapshot.
        agent_ids: Agents expected to exist in the sandbox.
        processor_ids: Processors expected to exist in the sandbox.
        group_chat_ids: Group chats expected to exist in the sandbox.
        recorded_at: UTC timestamp for the snapshot.
    """

    runner_id: str
    agent_ids: list[str] = field(default_factory=list)
    processor_ids: list[str] = field(default_factory=list)
    group_chat_ids: list[str] = field(default_factory=list)
    recorded_at: datetime = field(default_factory=get_current_utc_timestamp)


class LocalAgentStore(ABC):
    """Defines the scaffold contract for agent-runner local persistence."""

    @abstractmethod
    def save_reasoning_record(self, record: ReasoningRecord) -> None:
        """Persist a reasoning-history record."""

    @abstractmethod
    def save_tool_result_record(self, record: ToolResultRecord) -> None:
        """Persist a tool-result record."""

    @abstractmethod
    def save_session_state_record(self, record: SessionStateRecord) -> None:
        """Persist a runner session-state record."""

    @abstractmethod
    def save_recovery_snapshot(self, snapshot: RecoverySnapshot) -> None:
        """Persist a recovery snapshot for a runner."""

    @abstractmethod
    def load_recovery_snapshot(self, runner_id: str) -> RecoverySnapshot | None:
        """Load the latest recovery snapshot for a runner if one exists."""
