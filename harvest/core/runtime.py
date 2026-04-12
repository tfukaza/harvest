"""Runtime contract for hosting Harvest agents."""


from abc import ABC, abstractmethod
from typing import Any

from harvest.core.agent import Agent


class Runtime(ABC):
    """Defines the sandbox and integration boundary for active compute.

    The runtime hosts one or more agents, mediates access to tools and resources,
    and translates between Harvest framework concerns and agent-facing inputs.
    """

    @abstractmethod
    def register_agent(self, agent_id: str, agent: Agent) -> None:
        """Register an agent with the runtime."""

    @abstractmethod
    def list_agents(self) -> list[str]:
        """Return the identifiers of all hosted agents."""

    @abstractmethod
    def remove_agent(self, agent_id: str) -> None:
        """Remove an agent from the runtime."""

    @abstractmethod
    def bind_resource(self, resource_id: str, resource: Any) -> None:
        """Bind a resource to the runtime."""

    @abstractmethod
    def bind_tool(self, tool_name: str, tool: Any) -> None:
        """Bind a tool to the runtime."""

    @abstractmethod
    def publish_event(self, event_type: str, payload: dict[str, Any]) -> None:
        """Publish a framework-facing event."""

    @abstractmethod
    def handle_event(self, event_type: str, payload: dict[str, Any]) -> None:
        """Handle a framework event and translate it for agents."""

    @abstractmethod
    async def start(self) -> None:
        """Start the runtime."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the runtime."""

    @abstractmethod
    def health_check(self) -> dict[str, Any]:
        """Return runtime health information."""
