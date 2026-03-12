"""Agent-runner scaffolding built on the existing runtime contract."""

from __future__ import annotations

from abc import ABC, abstractmethod

from harvest.agent_runner.config import AgentRunnerConfig
from harvest.agent_runner.endpoints import DeliveryMode, GroupChatDefinition, SandboxEndpoint
from harvest.agent_runner.processors import MessageProcessor
from harvest.runtime import Runtime


class AgentRunner(Runtime, ABC):
    """Defines the scaffold contract for future agent-runner sandboxes.

    This class narrows the generic runtime contract toward the agent-runner
    architecture without pretending that the concrete sandbox already exists.
    """

    @property
    @abstractmethod
    def config(self) -> AgentRunnerConfig:
        """Return the scaffold configuration for this runner."""

    @abstractmethod
    def register_processor(self, processor_id: str, processor: MessageProcessor) -> None:
        """Register a sandbox-local message processor."""

    @abstractmethod
    def list_processors(self) -> list[str]:
        """Return the identifiers of all registered message processors."""

    @abstractmethod
    def remove_processor(self, processor_id: str) -> None:
        """Remove a sandbox-local message processor."""

    @abstractmethod
    def register_group_chat(self, group_chat: GroupChatDefinition) -> None:
        """Register a scaffolded runtime group chat."""

    @abstractmethod
    def list_group_chats(self) -> list[str]:
        """Return the identifiers of all registered group chats."""

    @abstractmethod
    def remove_group_chat(self, group_chat_id: str) -> None:
        """Remove a scaffolded runtime group chat."""

    @abstractmethod
    def list_endpoints(self) -> list[SandboxEndpoint]:
        """Return the currently known sandbox endpoints."""

    @abstractmethod
    def get_supported_delivery_modes(self) -> list[DeliveryMode]:
        """Return the delivery modes that later implementations may support."""
