"""ToolRegistry: aggregates InterfaceTool instances from all registered services.

The ToolRegistry is owned by SandboxServiceRouter and populated at service
registration time.  It enforces global tool-name uniqueness and provides
policy-filtered tool lookups for agent wiring and discovery.
"""


import threading
from typing import TYPE_CHECKING

from harvest.interfaces.service import ServiceRole
from harvest.interfaces.tool_definition import InterfaceTool

if TYPE_CHECKING:
    from harvest.core.policy import AgentPolicy


class ToolRegistry:
    """Aggregates InterfaceTool instances across all registered services.

    One instance lives inside :class:`~harvest.agent_sandbox.services.router.SandboxServiceRouter`.
    Tools are registered at service-registration time and looked up at
    agent-wiring time and discovery time.

    Tool name uniqueness is enforced globally across all service types.  Two
    services may not both define a tool with the same name — if they do,
    :meth:`register` raises :class:`ValueError` at startup.

    Usage::

        registry = ToolRegistry()
        registry.register(tool)
        tools = registry.tools_for_policy(agent_policy)
        tool = registry.get_tool("get_stock_price")
    """

    def __init__(self) -> None:
        self._tools: dict[str, InterfaceTool] = {}
        self._lock = threading.Lock()

    def register(self, tool: InterfaceTool) -> None:
        """Register a tool.  Raises :class:`ValueError` on name collision.

        Args:
            tool: The :class:`InterfaceTool` to register.

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        with self._lock:
            if tool.name in self._tools:
                existing = self._tools[tool.name]
                raise ValueError(
                    f"Tool name collision: '{tool.name}' is already registered "
                    f"by service '{existing.service_id}' (type: {existing.service_type}). "
                    f"Attempted re-registration by service '{tool.service_id}'."
                )
            self._tools[tool.name] = tool

    def tools_for_policy(self, policy: AgentPolicy | None) -> list[InterfaceTool]:
        """Return all tools accessible to an agent given their policy.

        Filters the registered tool set by checking whether the tool's
        ``service_id`` and ``service_type`` are permitted by the agent's
        ``allowed_services``.  EventSources never produce tools (inbox model).

        If ``policy`` is ``None`` (admin / unrestricted mode), all registered
        tools are returned.

        Args:
            policy: Agent policy to filter by, or ``None`` for no filtering.

        Returns:
            List of permitted :class:`InterfaceTool` instances.
        """
        with self._lock:
            all_tools = list(self._tools.values())

        if policy is None:
            return all_tools

        result: list[InterfaceTool] = []
        for tool in all_tools:
            try:
                tool_role = ServiceRole(tool.service_type)
            except ValueError:
                # Unknown service_type — skip
                continue

            if tool_role == ServiceRole.EVENT_SOURCE:
                # EventSources never have tools
                continue

            for perm in policy.allowed_services:
                if perm.service_id == tool.service_id:
                    if perm.roles is None or tool_role in perm.roles:
                        result.append(tool)
                    break

        return result

    def get_tool(self, tool_name: str) -> InterfaceTool | None:
        """Look up a tool by name.

        Args:
            tool_name: Exact tool name to look up.

        Returns:
            The :class:`InterfaceTool` if found, or ``None`` if not registered.
        """
        with self._lock:
            return self._tools.get(tool_name)

    def list_tool_names(self) -> list[str]:
        """Return names of all registered tools.

        Returns:
            List of tool name strings.
        """
        with self._lock:
            return list(self._tools.keys())
