"""Agent contract for Harvest AI agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable


class Agent(ABC):
    """Defines the framework-agnostic contract for an AI agent.

    An agent is a self-contained AI loop that manages its own reasoning state
    and tool-use decisions. Framework integration concerns such as event-bus
    wiring, resource binding, and lifecycle orchestration belong to the runtime
    layer, not the agent itself.

    Sandbox-wiring attributes
    -------------------------
    The following attributes are provided with safe defaults so that
    :class:`~harvest.agent_sandbox.basic_sandbox.BasicSandbox` can
    always access them without ``hasattr`` checks.  Concrete agents
    (e.g. :class:`~harvest.harvest_agent.HarvestAgent`) override them
    in their ``__init__``.
    """

    # Identity — set by BasicSandbox.register_agent()
    agent_id: str = ""
    _sandbox: Any | None = None

    # Chat wiring — overridden by HarvestAgent.__init__()
    _chat_client: Any | None = None

    # System prompt — overridden by HarvestAgent.__init__()
    base_system_prompt: str = ""
    _system_prompt_fn: Callable[[], str] | None = None

    # Tool registry — overridden by HarvestAgent.__init__()
    _tools: list[dict] = []
    _tool_map: dict[str, Any] = {}

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

    def _wire_chat_client(self, sandbox_bus: Any, policy: Any | None) -> None:
        """Wire event-driven chat tools. No-op by default; overridden by HarvestAgent."""

    def _wire_cognitive_tools(self, enabled: frozenset[str]) -> None:
        """Wire cognitive tools (think, memory, todo). No-op by default."""
