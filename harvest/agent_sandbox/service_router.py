"""SandboxServiceRouter: policy-enforced routing for Service interactions.

This module is the "corporate firewall" layer described in Phase 13 and
unified in Phase 15.  Every external interaction an agent makes — fetching
data, executing an action, or reading an event notification — is routed
through this class.

Agents never hold direct references to Service instances.  Instead, three
generic tools are registered on every agent (subject to policy):

- ``fetch_data(service_id, query_type, params)``
- ``execute_action(service_id, command_type, params)``
- ``read_event_notifications()``

All three tools delegate to the SandboxServiceRouter, which enforces the
two-level policy (sandbox registry ∩ agent ServicePermission) before calling
the underlying service method.

Routing visibility
------------------
Every request emits a typed event onto the event bus (if one is connected):

- ``DataFetchRequested`` / ``DataFetchCompleted``
- ``ActionRequested`` / ``ActionCompleted``
- ``ExternalEventDelivered``
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import threading
import uuid
from typing import TYPE_CHECKING, Any, Callable

from harvest.events.base import (
    ActionCompleted,
    ActionRequested,
    DataFetchCompleted,
    DataFetchRequested,
    ExternalEventDelivered,
    ToolsAutoRegistered,
    ToolSpecsInjected,
)
from harvest.interfaces.service import (
    ActionCommand,
    ActionResult,
    DataQuery,
    DataResult,
    Service,
    ServiceRole,
)
from harvest.interfaces.tool_definition import InterfaceTool
from harvest.interfaces.tool_registry import ToolRegistry

if TYPE_CHECKING:
    from harvest.events.event_bus import EventBus
    from harvest.policy import AgentPolicy

logger = logging.getLogger(__name__)


def _run_coro(coro: Any) -> Any:
    """Execute an async coroutine from a synchronous (threaded) context.

    Agent tools run in threads managed by BasicSandbox.  This helper bridges
    the sync/async boundary by running the coroutine in a new event loop when
    no loop is already running (the normal case for agent threads).

    Args:
        coro: Awaitable coroutine to execute.

    Returns:
        The coroutine's return value.
    """
    try:
        asyncio.get_running_loop()
        # A loop is running (unusual for agent threads but handle gracefully).
        # Spin up a dedicated thread with its own loop to avoid deadlock.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(asyncio.run, coro)
            return fut.result()
    except RuntimeError:
        # No running loop — safe to use asyncio.run().
        return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Tool spec helpers (OpenAI function-calling format)
# ---------------------------------------------------------------------------

_FETCH_DATA_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "fetch_data",
        "description": (
            "Request data from an approved external service (DATA_SOURCE role). "
            "Only services listed in your policy with DATA_SOURCE access are accessible."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "service_id": {
                    "type": "string",
                    "description": "ID of the service to query.",
                },
                "query_type": {
                    "type": "string",
                    "description": "Category of data (e.g. 'price', 'news', 'search').",
                },
                "params": {
                    "type": "object",
                    "description": "Query-specific parameters.",
                    "additionalProperties": True,
                },
            },
            "required": ["service_id", "query_type"],
        },
    },
}

_EXECUTE_ACTION_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "execute_action",
        "description": (
            "Execute an action through an approved external service (ACTION role). "
            "Only services listed in your policy with ACTION access are accessible."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "service_id": {
                    "type": "string",
                    "description": "ID of the service to invoke.",
                },
                "command_type": {
                    "type": "string",
                    "description": "Category of action (e.g. 'place_order', 'post_request').",
                },
                "params": {
                    "type": "object",
                    "description": "Command-specific parameters.",
                    "additionalProperties": True,
                },
            },
            "required": ["service_id", "command_type"],
        },
    },
}

_READ_EVENT_NOTIFICATIONS_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "read_event_notifications",
        "description": (
            "Read pending event notifications delivered from subscribed external "
            "event sources. Returns a list of notifications since the last call."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

_DISCOVER_TOOLS_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "discover_tools",
        "description": (
            "Discover interface tools available to you. "
            "Call with no arguments to get a lightweight catalogue of tool names and short descriptions. "
            "Call with a tool_name argument to get the full spec for that tool and activate it in your system prompt."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": (
                        "Name of a specific tool to get the full spec for and activate. "
                        "Omit to get the lightweight catalogue listing."
                    ),
                },
            },
            "required": [],
        },
    },
}


# ---------------------------------------------------------------------------
# Policy helper
# ---------------------------------------------------------------------------


def _policy_permits_role(
    policy: AgentPolicy,
    service_id: str | None,
    role: ServiceRole,
) -> bool:
    """Return True if the policy grants access to a role.

    If *service_id* is ``None``, checks whether *any* service permission
    covers the role (equivalent to the old ``_policy_has_any_role``).
    """
    for perm in policy.allowed_services:
        if service_id is not None and perm.service_id != service_id:
            continue
        if perm.roles is None or role in perm.roles:
            return True
    return False


# ---------------------------------------------------------------------------
# SandboxServiceRouter
# ---------------------------------------------------------------------------


class SandboxServiceRouter:
    """Policy-enforced router for Service interactions.

    One instance is created per sandbox.  It holds the sandbox-level service
    registry (Level 1 policy) and enforces per-agent
    :class:`~harvest.policy.AgentPolicy` ``allowed_services`` (Level 2
    policy) for every external interaction.

    Usage::

        router = SandboxServiceRouter(sandbox_id="my-sandbox", event_bus=bus)
        router.register_service(my_service)

        # When registering an agent with BasicSandbox, wire the tools:
        tools, tool_map = router.make_service_tools(agent_id, policy)
        # Add tools / tool_map entries to the agent.
    """

    def __init__(
        self,
        sandbox_id: str = "",
        event_bus: EventBus | None = None,
        sandbox_bus: Any | None = None,
    ) -> None:
        """Initialise the service router.

        Args:
            sandbox_id: ID of the owning sandbox (used in audit events).
            event_bus: Optional event bus for dispatching audit events.
            sandbox_bus: Optional per-sandbox SyncEventBus (Phase 18).
        """
        self._sandbox_id = sandbox_id
        self._event_bus = event_bus
        self._sandbox_bus = sandbox_bus

        # Level 1: unified service registry
        self._services: dict[str, Service] = {}

        # Tool registry: aggregates InterfaceTools from all registered services
        self._tool_registry = ToolRegistry()

        # Per-agent subscriptions: agent_id → set of service IDs (EVENT_SOURCE role)
        self._agent_subscriptions: dict[str, set[str]] = {}

        # Per-agent pending event notification queues
        self._pending_events: dict[str, list[dict[str, Any]]] = {}

        # Callbacks to wake agents when an event fires
        self._agent_wake_callbacks: dict[str, Callable[[], None]] = {}

        # Callback for pushing event arrival notifications into system prompt
        # agent_id, source_id, event_type → None
        self._event_notification_callback: Callable[[str, str, str], None] | None = None

        self._lock = threading.Lock()

    # -- Service registry management -----------------------------------------

    def register_service(self, service: Service) -> None:
        """Register a Service with the sandbox.

        Based on the service's ``roles``:

        - ``DATA_SOURCE``: injects fetch callback, registers data tools
        - ``ACTION``: injects execute callback, registers action tools
        - ``EVENT_SOURCE``: subscribes to event bus for this service's events

        Args:
            service: Service instance to register.

        Raises:
            ValueError: If a service with the same ID is already registered,
                or if any of its tools collide with an existing tool name.
        """
        with self._lock:
            if service.service_id in self._services:
                raise ValueError(f"Service already registered: {service.service_id}")
            self._services[service.service_id] = service
            if ServiceRole.EVENT_SOURCE in service.roles and self._event_bus is not None:
                self._subscribe_to_bus_for_source(service.service_id)

        if ServiceRole.DATA_SOURCE in service.roles:
            service.bind_fetch_callback(
                self._make_tool_fetch_callback(service.service_id)
            )
            for tool in service.get_tools(ServiceRole.DATA_SOURCE):
                self._tool_registry.register(tool)

        if ServiceRole.ACTION in service.roles:
            service.bind_execute_callback(
                self._make_tool_execute_callback(service.service_id)
            )
            for tool in service.get_tools(ServiceRole.ACTION):
                self._tool_registry.register(tool)

    def list_services(self) -> list[str]:
        """Return IDs of all registered Services."""
        with self._lock:
            return list(self._services.keys())

    def get_service(self, service_id: str) -> Service | None:
        """Return the Service instance for *service_id*, or ``None``."""
        with self._lock:
            return self._services.get(service_id)

    # -- Callback binding helpers for tool handlers --------------------------

    def _make_tool_fetch_callback(self, service_id: str) -> Callable[..., str]:
        """Return a fetch callback bound to service_id for injection into a Service."""

        def _callback(
            agent_id: str,
            _service_id: str,
            query_type: str,
            params: dict[str, Any],
        ) -> str:
            return self._do_fetch(agent_id, _service_id, query_type, params, policy=None)

        return _callback

    def _make_tool_execute_callback(self, service_id: str) -> Callable[..., str]:
        """Return an execute callback bound to service_id for injection into a Service."""

        def _callback(
            agent_id: str,
            _service_id: str,
            command_type: str,
            params: dict[str, Any],
        ) -> str:
            return self._do_execute(agent_id, _service_id, command_type, params, policy=None)

        return _callback

    # -- Agent wiring --------------------------------------------------------

    def register_agent_wake_callback(
        self,
        agent_id: str,
        wake_fn: Callable[[], None],
    ) -> None:
        """Register a callback that wakes an agent when an event fires.

        Args:
            agent_id: Target agent.
            wake_fn: Zero-argument callable that signals the agent to wake.
        """
        with self._lock:
            self._agent_wake_callbacks[agent_id] = wake_fn
            if agent_id not in self._pending_events:
                self._pending_events[agent_id] = []

    def subscribe_agent(self, agent_id: str, service_id: str) -> None:
        """Subscribe an agent to an EVENT_SOURCE service.

        Args:
            agent_id: The subscribing agent.
            service_id: Service ID with EVENT_SOURCE role to subscribe to.

        Raises:
            ValueError: If ``service_id`` is not a registered service with
                EVENT_SOURCE role.
        """
        with self._lock:
            svc = self._services.get(service_id)
            if svc is None or ServiceRole.EVENT_SOURCE not in svc.roles:
                raise ValueError(
                    f"Cannot subscribe agent '{agent_id}' to unknown event source '{service_id}'"
                )
            if agent_id not in self._agent_subscriptions:
                self._agent_subscriptions[agent_id] = set()
            self._agent_subscriptions[agent_id].add(service_id)
            if agent_id not in self._pending_events:
                self._pending_events[agent_id] = []

    def unregister_agent(self, agent_id: str) -> None:
        """Remove all router state for an agent.

        Args:
            agent_id: Agent being removed from the sandbox.
        """
        with self._lock:
            self._agent_subscriptions.pop(agent_id, None)
            self._pending_events.pop(agent_id, None)
            self._agent_wake_callbacks.pop(agent_id, None)

    def register_event_notification_callback(
        self,
        callback: Callable[[str, str, str], None],
    ) -> None:
        """Register the callback invoked when an external event is delivered.

        Args:
            callback: Called once per agent per delivered external event.
                Signature: ``(agent_id, source_id, event_type) -> None``.
        """
        self._event_notification_callback = callback

    # -- Auto-registration and discovery tools -------------------------------

    def wire_agent_tools(
        self,
        agent_id: str,
        policy: AgentPolicy | None,
    ) -> list[tuple[dict, Callable[..., str]]]:
        """Wire interface tools as callables onto an agent at startup.

        Queries the tool registry for all interface tools permitted by
        *policy*, wraps each handler with an agent-scoped closure (so
        ``agent_id`` is injected automatically), and returns the pairs.
        The caller is responsible for appending these to the agent's
        ``_tools`` / ``_tool_map``.

        Side effects:
            Emits a :class:`ToolsAutoRegistered` event on the sandbox
            event bus listing the names of all tools that were wired.

        Args:
            agent_id: The agent receiving the tools.
            policy: Agent policy used to filter the tool registry, or
                ``None`` for admin (all tools).

        Returns:
            List of ``(tool_spec_dict, callable)`` pairs.
        """
        permitted_tools = self._tool_registry.tools_for_policy(policy)

        pairs: list[tuple[dict, Callable[..., str]]] = []
        tool_names: list[str] = []

        for tool in permitted_tools:
            spec = tool.to_tool_spec()
            wrapped = self._wrap_handler(tool, agent_id, policy)
            pairs.append((spec, wrapped))
            tool_names.append(tool.name)

        if tool_names:
            self._emit(ToolsAutoRegistered(source=f"sandbox:{self._sandbox_id}", agent_id=agent_id, tool_names=tool_names, sandbox_id=self._sandbox_id))

        return pairs

    @staticmethod
    def _wrap_handler(
        tool: InterfaceTool,
        agent_id: str,
        policy: AgentPolicy | None,
    ) -> Callable[..., str]:
        """Wrap a tool handler with an agent-scoped closure injecting agent_id."""

        def wrapped(**kwargs: Any) -> str:
            return tool.handler(agent_id=agent_id, **kwargs)

        return wrapped

    def make_discovery_tool(
        self,
        agent_id: str,
        policy: AgentPolicy | None,
        inject_callback: Callable[[str, InterfaceTool], None],
    ) -> tuple[dict, Callable[..., str]]:
        """Return the ``discover_tools`` callable for an agent.

        The returned closure maintains an ``already_injected: set[str]``
        that tracks which tool names have been fully activated.  On the
        first call with a specific ``tool_name``, the *inject_callback* is
        invoked to register the full tool spec on the agent; subsequent
        calls for the same name skip injection.  Calling without a
        ``tool_name`` returns a lightweight catalogue of all discoverable
        tools without triggering any injection.

        Args:
            agent_id: The agent this tool belongs to.
            policy: Agent policy used to scope which tools are discoverable.
            inject_callback: Called with ``(agent_id, tool)`` when a full
                spec activation is requested.

        Returns:
            ``(tool_spec_dict, callable)`` pair for the discover_tools tool.
        """
        already_injected: set[str] = set()

        def _discover_tools(tool_name: str | None = None) -> str:
            permitted = self._tool_registry.tools_for_policy(policy)

            if tool_name is None:
                catalogue = [
                    {
                        "name": t.name,
                        "short_description": t.short_description,
                        "service_id": t.service_id,
                        "service_type": t.service_type,
                    }
                    for t in permitted
                ]
                return json.dumps(catalogue)

            permitted_names = {t.name for t in permitted}
            if tool_name not in permitted_names:
                return json.dumps({"error": "unknown_tool", "tool_name": tool_name})

            tool = self._tool_registry.get_tool(tool_name)
            if tool is None:
                return json.dumps({"error": "unknown_tool", "tool_name": tool_name})

            if tool_name not in already_injected:
                inject_callback(agent_id, tool)
                already_injected.add(tool_name)
                self._emit(ToolSpecsInjected(source=f"sandbox:{self._sandbox_id}", agent_id=agent_id, tool_names=[tool_name]))

            full_spec = {
                "name": tool.name,
                "full_description": tool.full_description,
                "arguments": [
                    {
                        "name": a.name,
                        "type": a.type,
                        "description": a.description,
                        "required": a.required,
                        **({"default": a.default} if not a.required else {}),
                    }
                    for a in tool.arguments
                ],
                "returns_description": tool.returns_description,
                "service_id": tool.service_id,
                "service_type": tool.service_type,
            }
            return json.dumps(full_spec)

        return _DISCOVER_TOOLS_TOOL, _discover_tools

    # -- Tool factories ------------------------------------------------------

    def make_service_tools(
        self,
        agent_id: str,
        policy: AgentPolicy | None,
        clear_notifications_callback: Callable[[str], None] | None = None,
    ) -> tuple[list[dict], dict[str, Callable[..., str]]]:
        """Generate the generic service tools for an agent.

        The tools respect the agent's policy:

        - ``fetch_data`` is only registered if the policy permits at least
          one service with ``DATA_SOURCE`` role.
        - ``execute_action`` is only registered if the policy permits at
          least one service with ``ACTION`` role.
        - ``read_event_notifications`` is only registered if the policy
          permits at least one service with ``EVENT_SOURCE`` role.

        If no policy is provided, all three tools are registered (admin mode).

        Args:
            agent_id: The agent receiving the tools.
            policy: Optional AgentPolicy for access scoping.
            clear_notifications_callback: Optional callable invoked after
                ``read_event_notifications()`` drains the queue.
                Signature: ``(agent_id: str) -> None``.

        Returns:
            A ``(tool_specs, tool_map)`` tuple ready to be merged into a
            ``HarvestAgent``'s ``_tools`` and ``_tool_map``.
        """
        has_ds = policy is None or _policy_permits_role(policy, None, ServiceRole.DATA_SOURCE)
        has_act = policy is None or _policy_permits_role(policy, None, ServiceRole.ACTION)
        has_es = policy is None or _policy_permits_role(policy, None, ServiceRole.EVENT_SOURCE)

        tool_specs: list[dict] = []
        tool_map: dict[str, Callable[..., str]] = {}

        if has_ds:
            tool_specs.append(_FETCH_DATA_TOOL)
            tool_map["fetch_data"] = self._make_dispatch_callable(agent_id, policy, self._do_fetch)

        if has_act:
            tool_specs.append(_EXECUTE_ACTION_TOOL)
            tool_map["execute_action"] = self._make_dispatch_callable(agent_id, policy, self._do_execute)

        if has_es:
            tool_specs.append(_READ_EVENT_NOTIFICATIONS_TOOL)
            tool_map["read_event_notifications"] = (
                self._make_read_event_notifications_callable(
                    agent_id,
                    clear_notifications_callback=clear_notifications_callback,
                )
            )

        return tool_specs, tool_map

    # -- Internal tool callables ---------------------------------------------

    def _make_dispatch_callable(
        self,
        agent_id: str,
        policy: AgentPolicy | None,
        method: Callable[..., str],
    ) -> Callable[..., str]:
        """Create a closure that dispatches a fetch or execute request."""
        def _dispatch(
            service_id: str,
            op_type: str,
            params: dict[str, Any] | None = None,
        ) -> str:
            if params is None:
                params = {}
            return method(agent_id, service_id, op_type, params, policy)

        return _dispatch

    def _make_read_event_notifications_callable(
        self,
        agent_id: str,
        clear_notifications_callback: Callable[[str], None] | None = None,
    ) -> Callable[..., str]:
        def _read_event_notifications() -> str:
            result = self._do_read_notifications(agent_id)
            if clear_notifications_callback is not None:
                try:
                    clear_notifications_callback(agent_id)
                except Exception:
                    logger.exception(
                        "clear_notifications_callback failed for agent '%s'", agent_id
                    )
            return result

        return _read_event_notifications

    # -- Routing logic -------------------------------------------------------

    def _do_fetch(
        self,
        agent_id: str,
        service_id: str,
        query_type: str,
        params: dict[str, Any],
        policy: AgentPolicy | None,
    ) -> str:
        """Execute a data fetch with policy enforcement."""
        request_id = str(uuid.uuid4())

        self._emit(DataFetchRequested(source=f"sandbox:{self._sandbox_id}", agent_id=agent_id, source_id=service_id, request_id=request_id, query_type=query_type, params=params))

        # Level 2 policy check
        if policy is not None and not _policy_permits_role(
            policy, service_id, ServiceRole.DATA_SOURCE
        ):
            error = (
                f"policy_denied: agent '{agent_id}' is not permitted to access "
                f"data source '{service_id}'"
            )
            self._emit(DataFetchCompleted(source=f"sandbox:{self._sandbox_id}", agent_id=agent_id, source_id=service_id, request_id=request_id, payload={}, error=error))
            return json.dumps({"error": error})

        # Level 1 registry check
        with self._lock:
            service = self._services.get(service_id)
        if service is None or ServiceRole.DATA_SOURCE not in service.roles:
            error = f"unknown_source: data source '{service_id}' is not registered in this sandbox"
            self._emit(DataFetchCompleted(source=f"sandbox:{self._sandbox_id}", agent_id=agent_id, source_id=service_id, request_id=request_id, payload={}, error=error))
            return json.dumps({"error": error})

        query = DataQuery(
            query_type=query_type,
            params=params,
            agent_id=agent_id,
            request_id=request_id,
        )
        try:
            result: DataResult = _run_coro(service.fetch(query))
        except Exception as exc:
            error = f"fetch_error: {exc}"
            logger.exception(
                "Service '%s' raised an exception for agent '%s'", service_id, agent_id
            )
            self._emit(DataFetchCompleted(source=f"sandbox:{self._sandbox_id}", agent_id=agent_id, source_id=service_id, request_id=request_id, payload={}, error=error))
            return json.dumps({"error": error})

        if result.error:
            self._emit(DataFetchCompleted(source=f"sandbox:{self._sandbox_id}", agent_id=agent_id, source_id=service_id, request_id=request_id, payload={}, error=result.error))
            return json.dumps({"error": result.error})

        self._emit(DataFetchCompleted(source=f"sandbox:{self._sandbox_id}", agent_id=agent_id, source_id=service_id, request_id=request_id, payload=result.payload, error=""))
        return json.dumps(result.payload)

    def _do_execute(
        self,
        agent_id: str,
        service_id: str,
        command_type: str,
        params: dict[str, Any],
        policy: AgentPolicy | None,
    ) -> str:
        """Execute an action with policy enforcement."""
        request_id = str(uuid.uuid4())

        self._emit(ActionRequested(source=f"sandbox:{self._sandbox_id}", agent_id=agent_id, action_id=service_id, request_id=request_id, command_type=command_type, params=params))

        # Level 2 policy check
        if policy is not None and not _policy_permits_role(
            policy, service_id, ServiceRole.ACTION
        ):
            error = (
                f"policy_denied: agent '{agent_id}' is not permitted to use "
                f"action '{service_id}'"
            )
            self._emit(ActionCompleted(source=f"sandbox:{self._sandbox_id}", agent_id=agent_id, action_id=service_id, request_id=request_id, payload={}, error=error))
            return json.dumps({"error": error})

        # Level 1 registry check
        with self._lock:
            service = self._services.get(service_id)
        if service is None or ServiceRole.ACTION not in service.roles:
            error = f"unknown_action: action '{service_id}' is not registered in this sandbox"
            self._emit(ActionCompleted(source=f"sandbox:{self._sandbox_id}", agent_id=agent_id, action_id=service_id, request_id=request_id, payload={}, error=error))
            return json.dumps({"error": error})

        command = ActionCommand(
            command_type=command_type,
            params=params,
            agent_id=agent_id,
            request_id=request_id,
        )
        try:
            result: ActionResult = _run_coro(service.execute(command))
        except Exception as exc:
            error = f"execute_error: {exc}"
            logger.exception(
                "Service '%s' raised an exception for agent '%s'", service_id, agent_id
            )
            self._emit(ActionCompleted(source=f"sandbox:{self._sandbox_id}", agent_id=agent_id, action_id=service_id, request_id=request_id, payload={}, error=error))
            return json.dumps({"error": error})

        if result.error:
            self._emit(ActionCompleted(source=f"sandbox:{self._sandbox_id}", agent_id=agent_id, action_id=service_id, request_id=request_id, payload={}, error=result.error))
            return json.dumps({"error": result.error})

        self._emit(ActionCompleted(source=f"sandbox:{self._sandbox_id}", agent_id=agent_id, action_id=service_id, request_id=request_id, payload=result.payload, error=""))
        return json.dumps(result.payload)

    def _do_read_notifications(self, agent_id: str) -> str:
        """Drain and return pending event notifications for an agent."""
        with self._lock:
            notifications = list(self._pending_events.get(agent_id, []))
            if agent_id in self._pending_events:
                self._pending_events[agent_id].clear()
        return json.dumps(notifications)

    # -- External event delivery ---------------------------------------------

    def deliver_external_event(
        self,
        source_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Deliver a fired external event to all subscribed agents.

        For each agent subscribed to *source_id*, this method:

        1. Appends a notification dict to ``self._pending_events[agent_id]``
           so the agent can retrieve it via ``read_event_notifications``.
        2. Invokes the sandbox-level ``_event_notification_callback`` (if
           set) to inject a system-prompt hint about the new event.
        3. Calls the agent's registered wake callback (if any) to interrupt
           hibernation sleep, allowing the agent to process the event
           promptly.
        4. Emits an :class:`ExternalEventDelivered` event on the sandbox
           event bus for observability.

        Args:
            source_id: The service (EVENT_SOURCE role) that fired.
            event_type: The event subtype.
            payload: Event data.
        """
        notification = {
            "source_id": source_id,
            "event_type": event_type,
            "payload": payload,
        }

        with self._lock:
            subscribed_agents = [
                aid
                for aid, sources in self._agent_subscriptions.items()
                if source_id in sources
            ]

        for agent_id in subscribed_agents:
            with self._lock:
                if agent_id not in self._pending_events:
                    self._pending_events[agent_id] = []
                self._pending_events[agent_id].append(notification)

            if self._event_notification_callback is not None:
                try:
                    self._event_notification_callback(agent_id, source_id, event_type)
                except Exception:
                    logger.exception(
                        "Event notification callback failed for agent '%s'", agent_id
                    )

            wake_fn = self._agent_wake_callbacks.get(agent_id)
            if wake_fn is not None:
                try:
                    wake_fn()
                except Exception:
                    logger.exception(
                        "Wake callback failed for agent '%s'", agent_id
                    )

            self._emit(ExternalEventDelivered(source=f"sandbox:{self._sandbox_id}", source_id=source_id, agent_id=agent_id, sandbox_id=self._sandbox_id, event_type=event_type))
            logger.debug(
                "External event '%s' from source '%s' delivered to agent '%s'",
                event_type,
                source_id,
                agent_id,
            )

    # -- Event bus helpers ---------------------------------------------------

    def set_event_bus(self, event_bus: EventBus) -> None:
        """Attach an event bus after construction.

        Args:
            event_bus: The orchestrator event bus.
        """
        self._event_bus = event_bus
        self._wire_external_event_fired_handler()

    def _wire_external_event_fired_handler(self) -> None:
        if self._event_bus is None:
            return
        from harvest.events.base import ExternalEventFired

        def _handler(event: ExternalEventFired) -> None:
            self.deliver_external_event(
                source_id=event.source_id,
                event_type=event.event_type,
                payload=event.payload,
            )

        self._event_bus.on(ExternalEventFired, _handler)

    def _subscribe_to_bus_for_source(self, service_id: str) -> None:
        """No-op — all ExternalEventFired events share one handler."""

    def _emit(self, event: Any) -> None:
        """Dispatch an audit event to the orchestrator bus if available."""
        if self._event_bus is not None:
            self._event_bus.dispatch(event)
