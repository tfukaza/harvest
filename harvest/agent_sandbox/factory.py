"""Factory scaffolding for constructing agent-sandbox instances."""


from abc import ABC, abstractmethod

from harvest.agent_sandbox.config import AgentSandboxConfig
from harvest.agent_sandbox.sandbox import AgentSandbox


class AgentSandboxFactory(ABC):
    """Defines the scaffold contract for agent-sandbox factories."""

    @abstractmethod
    def create_sandbox(self, config: AgentSandboxConfig) -> AgentSandbox:
        """Create an agent sandbox from configuration."""
