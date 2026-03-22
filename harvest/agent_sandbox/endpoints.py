"""Endpoint and addressing schemas for agent-runner scaffolding."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EndpointKind(StrEnum):
    """Enumerates the sandbox endpoint kinds that the runner must address."""

    AGENT = "agent"
    GROUP_CHAT = "group_chat"
    MESSAGE_PROCESSOR = "message_processor"


class DeliveryMode(StrEnum):
    """Enumerates the future message-delivery modes supported by the sandbox."""

    PUSH = "push"
    PULL = "pull"


@dataclass(slots=True, frozen=True)
class EndpointAddress:
    """Represents an addressable endpoint inside a runner sandbox.

    Attributes:
        endpoint_id: Stable identifier of the endpoint within the sandbox.
        kind: Kind of the endpoint.
    """

    endpoint_id: str
    kind: EndpointKind


@dataclass(slots=True)
class SandboxEndpoint:
    """Describes a registered sandbox endpoint.

    Attributes:
        address: Address of the endpoint.
        display_name: Human-readable endpoint name.
        delivery_mode: Intended delivery mode for agent-facing endpoints.
        metadata: Additional scaffold metadata for future runtime wiring.
    """

    address: EndpointAddress
    display_name: str
    delivery_mode: DeliveryMode | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class GroupChatDefinition:
    """Defines a scaffolded runtime group-chat endpoint.

    Attributes:
        address: Address assigned to the group chat.
        member_ids: Identifiers of endpoints intended to participate.
        description: Human-readable purpose of the group chat.
    """

    address: EndpointAddress
    member_ids: list[str]
    description: str = ""
