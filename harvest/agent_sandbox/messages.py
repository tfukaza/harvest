"""Message schemas for future sandbox-local communication."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from harvest.agent_sandbox.endpoints import EndpointAddress


def get_current_utc_timestamp() -> datetime:
    """Return the current UTC timestamp for scaffold message records."""

    return datetime.now(UTC)


@dataclass(slots=True)
class SandboxMessage:
    """Represents a scaffolded message exchanged inside a runner sandbox.

    Attributes:
        message_id: Stable identifier for the message record.
        sender: Sender address within the sandbox.
        recipient: Recipient address within the sandbox.
        content: Opaque message content.
        created_at: UTC timestamp recording when the message was created.
        metadata: Additional future-facing routing or tracing metadata.
    """

    message_id: str
    sender: EndpointAddress
    recipient: EndpointAddress
    content: str
    created_at: datetime = field(default_factory=get_current_utc_timestamp)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MessageBatch:
    """Represents a group of messages exposed to one endpoint.

    Attributes:
        recipient: Endpoint that should observe the batch.
        messages: Ordered messages made available to that endpoint.
    """

    recipient: EndpointAddress
    messages: list[SandboxMessage] = field(default_factory=list)
