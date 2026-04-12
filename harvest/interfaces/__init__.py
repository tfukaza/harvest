"""Harvest external-world interface contracts.

This package defines the unified ``Service`` abstraction that replaces the
legacy ``Broker`` and ``Resource`` contracts, as well as the earlier
``DataSource``, ``Action``, and ``EventSource`` ABCs from Phase 13.

A ``Service`` declares one or more :class:`ServiceRole` values:

- ``DATA_SOURCE`` — pull-based, read-only external data (agents request,
  service responds)
- ``ACTION`` — imperative external effects (agents command, world changes)
- ``EVENT_SOURCE`` — push-based external signals (service fires, agents
  are notified via inbox)

Together with the :class:`~harvest.policy.ServicePermission`-based policy
system defined in :mod:`harvest.policy`, these abstractions form the
"corporate firewall" architecture: agents can only reach external services
that the sandbox has explicitly registered **and** that the agent's
individual policy permits.  All interactions are routed through the
:class:`~harvest.agent_sandbox.services.router.SandboxServiceRouter` and
logged as typed events on the orchestrator event bus.
"""

from harvest.interfaces.service import (
    ActionCommand,
    ActionResult,
    DataQuery,
    DataResult,
    Service,
    ServicePermission,
    ServiceRole,
)
from harvest.interfaces.tool_definition import InterfaceTool, ToolArgument
from harvest.interfaces.tool_registry import ToolRegistry

__all__ = [
    "Service",
    "ServiceRole",
    "ServicePermission",
    "DataQuery",
    "DataResult",
    "ActionCommand",
    "ActionResult",
    "InterfaceTool",
    "ToolArgument",
    "ToolRegistry",
]
