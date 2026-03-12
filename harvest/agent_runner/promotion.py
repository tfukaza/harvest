"""Promotion-policy scaffolding for sandbox-to-orchestrator boundaries."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class PromotionTarget(StrEnum):
    """Enumerates the currently known promotion targets."""

    ORCHESTRATOR_EVENT_BUS = "orchestrator_event_bus"


@dataclass(slots=True)
class PromotionCandidate:
    """Represents one sandbox-local event considered for promotion.

    Attributes:
        event_type: Sandbox-local event type being evaluated.
        payload: Event payload.
        source_endpoint_id: Endpoint that originated the event.
        severity: Event severity classification for future policy decisions.
        metadata: Future-facing promotion metadata.
    """

    event_type: str
    payload: dict[str, Any]
    source_endpoint_id: str
    severity: str = "normal"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PromotionDecision:
    """Represents the outcome of promotion-policy evaluation.

    Attributes:
        should_promote: Whether the candidate should leave the sandbox.
        reason: Human-readable explanation for the decision.
        target: Promotion target selected by policy.
        promoted_event_type: Optional orchestrator-facing event type.
    """

    should_promote: bool
    reason: str
    target: PromotionTarget = PromotionTarget.ORCHESTRATOR_EVENT_BUS
    promoted_event_type: str | None = None


class PromotionPolicy(ABC):
    """Defines the scaffold contract for future promotion policy logic."""

    @abstractmethod
    def evaluate(self, candidate: PromotionCandidate) -> PromotionDecision:
        """Evaluate whether a sandbox-local event should be promoted outward."""
