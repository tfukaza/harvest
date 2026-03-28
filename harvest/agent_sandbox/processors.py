"""Message-processor scaffolding for agent sandboxes."""


from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from harvest.agent_sandbox.endpoints import EndpointAddress
from harvest.agent_sandbox.messages import SandboxMessage


class MessageProcessor(ABC):
    """Defines the scaffold contract for sandbox-local message processors.

    A message processor is a first-class endpoint that may eventually stage,
    transform, aggregate, or gate messages before release.
    """

    @property
    @abstractmethod
    def endpoint(self) -> EndpointAddress:
        """Return the endpoint address used to route messages to this processor."""

    @abstractmethod
    def process_message(self, message: SandboxMessage) -> list[SandboxMessage]:
        """Process one scaffolded message and return any immediately releasable output."""

    @abstractmethod
    def flush(self) -> list[SandboxMessage]:
        """Flush any staged output known to the processor scaffold."""

    @abstractmethod
    def get_state_snapshot(self) -> dict[str, Any]:
        """Return scaffold state for inspection or future persistence."""


@dataclass(slots=True, frozen=True)
class AggregationProcessorConfig:
    """Defines scaffold configuration for a future aggregation processor.

    Attributes:
        processor_id: Stable identifier for the future processor instance.
        release_after_message_count: Number of messages required before release.
        output_recipient_id: Identifier of the endpoint that will receive output.
    """

    processor_id: str
    release_after_message_count: int
    output_recipient_id: str


@dataclass(slots=True, frozen=True)
class GatedReleaseProcessorConfig:
    """Defines scaffold configuration for a future gated-release processor.

    Attributes:
        processor_id: Stable identifier for the future processor instance.
        required_dependency_ids: Dependency identifiers required before release.
        output_recipient_id: Identifier of the endpoint that will receive output.
    """

    processor_id: str
    required_dependency_ids: tuple[str, ...]
    output_recipient_id: str
