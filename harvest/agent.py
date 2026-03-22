"""Agent contract for Harvest AI agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Agent(ABC):
    """Defines the framework-agnostic contract for an AI agent.

    An agent is a self-contained AI loop that manages its own reasoning state
    and tool-use decisions. Framework integration concerns such as event-bus
    wiring, resource binding, and lifecycle orchestration belong to the runtime
    layer, not the agent itself.
    """

    @abstractmethod
    def step(self, input_data: Any) -> Any:
        """Advance the agent by one input step.

        Args:
            input_data: Agent-facing input translated by the runtime.

        Returns:
            An agent-defined output, action request, or artifact.
        """

    @abstractmethod
    def reset(self) -> None:
        """Reset the agent's internal state."""

    @abstractmethod
    def get_reasoning_history(self) -> list[Any]:
        """Return the agent's reasoning history."""

    def shutdown(self) -> None:
        """Clean up agent resources. Called by the sandbox before removal.

        Default is a no-op. Subclasses override if they hold resources.
        """
