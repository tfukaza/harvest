"""Agent contract for Harvest AI agents."""


from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from harvest.agent_sandbox.system_prompt_builder import SystemPromptBuilder
    from harvest.interfaces.tool_definition import InterfaceTool


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

    # System prompt — set by BasicSandbox._wire_agent_prompt()
    base_system_prompt: str = ""
    _system_prompt_fn: Callable[[], str] | None = None
    _prompt_builder: SystemPromptBuilder | None = None
    _injected_tool_names: set[str]

    # Tool registry — overridden by HarvestAgent.__init__()
    _tools: list[dict] = []
    _tool_map: dict[str, Any] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

    def __init__(self) -> None:
        # Ensure each instance gets its own mutable set
        self._injected_tool_names: set[str] = set()

    # -- Prompt / notification methods --

    def inject_tool_spec(self, tool: InterfaceTool) -> None:
        """Append a tool spec to the system prompt. Idempotent."""
        builder = self._prompt_builder
        if builder is None:
            return
        if tool.name not in self._injected_tool_names:
            if not self._injected_tool_names:
                builder.append("tool_specs", "## Available Tools\n")
            builder.append("tool_specs", tool.to_system_prompt_block())
            self._injected_tool_names.add(tool.name)

    def add_event_notification(self, source_id: str, event_type: str) -> None:
        """Append an event arrival notification to the system prompt."""
        builder = self._prompt_builder
        if builder is None:
            return
        block = (
            f"## Pending Event Notification\n\n"
            f"A new event has arrived from source '{source_id}' "
            f"(type: '{event_type}'). Call read_event_notifications() to read it."
        )
        builder.append("event_notifications", block)

    def clear_event_notifications(self) -> None:
        """Clear the 'event_notifications' section."""
        builder = self._prompt_builder
        if builder is None:
            return
        builder.clear("event_notifications")

    def add_inbox_notification(self, channel_id: str, sender_id: str) -> None:
        """Append an inbox notification (auto-cleared after next prompt build)."""
        builder = self._prompt_builder
        if builder is None:
            return
        block = (
            f"**New message** from @{sender_id} in #{channel_id}. "
            f"Call read_messages(channel_id=\"{channel_id}\") to see it."
        )
        builder.append_auto_clear("inbox_notifications", block)

    def clear_inbox_notifications(self) -> None:
        """Clear the 'inbox_notifications' section."""
        builder = self._prompt_builder
        if builder is None:
            return
        builder.clear("inbox_notifications")

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
