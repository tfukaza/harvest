"""Factory scaffolding for constructing future agent-runner instances."""

from __future__ import annotations

from abc import ABC, abstractmethod

from harvest.agent_runner.config import AgentRunnerConfig
from harvest.agent_runner.runner import AgentRunner


class AgentRunnerFactory(ABC):
    """Defines the scaffold contract for future agent-runner factories."""

    @abstractmethod
    def create_runner(self, config: AgentRunnerConfig) -> AgentRunner:
        """Create a scaffolded agent runner from configuration."""
