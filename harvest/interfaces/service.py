"""Unified Service abstract contract for all external-world interactions.

Phase 15 replaces the three separate ABCs (DataSource, Action, EventSource)
with a single ``Service`` class whose capabilities are declared via ``roles``.

Design rationale
----------------
A single real-world entity (e.g. Alpaca) often needs to act as a data
provider *and* an order executor *and* an event stream.  The old three-ABC
model required three separate objects sharing credentials and lifecycle.
The unified ``Service`` class solves this with a ``roles`` frozenset:

- One service, one object, one lifecycle.
- Roles declare what the service can do; callers check roles before
  calling ``fetch`` or ``execute``.
- Policy can grant access to some roles but not others for the same service.

The ``DATA_SOURCE`` / ``ACTION`` / ``EVENT_SOURCE`` distinction is preserved
for *policy and security* reasons — see ``ServiceRole`` docstring.
"""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from harvest.events.event_bus import EventBus
    from harvest.interfaces.tool_definition import InterfaceTool


# ---------------------------------------------------------------------------
# ServiceRole
# ---------------------------------------------------------------------------


class ServiceRole(enum.Enum):
    """Declares the capabilities a Service fulfills.

    DATA_SOURCE — Read-only, side-effect-free data access.  Queries through
        a data source are guaranteed to never mutate external state.  Policy
        systems can grant DATA_SOURCE access with confidence that the agent
        can only read.

    EVENT_SOURCE — Push-based, read-only event delivery.  The service
        publishes events onto the event bus; agents receive them in their
        inbox.  Like DATA_SOURCE, this is a read-only channel — the agent
        cannot cause effects through the event source.

    ACTION — Operations that may cause side effects in external systems.  An
        action *can* be a query (e.g. "check order status"), but the role
        makes no guarantee about side effects.  Granting ACTION access is a
        separate, deliberate policy decision with different risk implications
        than DATA_SOURCE.  This is why the two roles are not merged: the
        distinction enables policy systems to enforce the read-only /
        read-write boundary.
    """

    DATA_SOURCE = "data_source"
    EVENT_SOURCE = "event_source"
    ACTION = "action"


# ---------------------------------------------------------------------------
# ServicePermission (policy entry)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ServicePermission:
    """One service permission entry in an agent policy.

    Attributes:
        service_id: The service this permission applies to.
        roles: The roles the agent may use.  ``None`` means all roles the
            service declares.  Specify a frozenset to grant only a subset.

    Examples::

        # All roles of alpaca:
        ServicePermission("alpaca")

        # Read-only access to alpaca (no order placement):
        ServicePermission("alpaca", roles=frozenset({ServiceRole.DATA_SOURCE}))

        # Data reads only from a news service:
        ServicePermission("newsapi", roles=frozenset({ServiceRole.DATA_SOURCE}))
    """

    service_id: str
    roles: frozenset[ServiceRole] | None = None  # None = all roles the service declares


# ---------------------------------------------------------------------------
# Data transfer objects (moved from data_source.py / action.py)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class DataQuery:
    """A structured request for data from a Service (DATA_SOURCE role).

    Attributes:
        query_type: Category of data requested (e.g. ``"price"``, ``"news"``).
        params: Query-specific parameters (symbol, date range, etc.).
        agent_id: ID of the agent making the request.
        request_id: Correlation ID used to match the response on the event bus.
    """

    query_type: str
    params: dict[str, Any]
    agent_id: str
    request_id: str


@dataclass(slots=True)
class DataResult:
    """The response from a Service fetch call (DATA_SOURCE role).

    Attributes:
        request_id: Matches the originating :class:`DataQuery`.
        source_id: Stable ID of the Service that produced this result.
        payload: Query-specific result data.
        error: Non-empty string if the fetch failed; empty string means success.
    """

    request_id: str
    source_id: str
    payload: dict[str, Any]
    error: str = ""


@dataclass(slots=True)
class ActionCommand:
    """A structured request to execute a Service (ACTION role).

    Attributes:
        command_type: Category of effect (e.g. ``"place_order"``).
        params: Command-specific parameters.
        agent_id: ID of the agent issuing the command.
        request_id: Correlation ID used to match the response on the event bus.
    """

    command_type: str
    params: dict[str, Any]
    agent_id: str
    request_id: str


@dataclass(slots=True)
class ActionResult:
    """The result of an executed Service action (ACTION role).

    Attributes:
        request_id: Matches the originating :class:`ActionCommand`.
        action_id: Stable ID of the Service that produced this result.
        payload: Command-specific result data.
        error: Non-empty string if execution failed; empty string means success.
    """

    request_id: str
    action_id: str
    payload: dict[str, Any]
    error: str = ""


# ---------------------------------------------------------------------------
# Service ABC
# ---------------------------------------------------------------------------


class Service(ABC):
    """Unified abstract contract for all external-world interactions.

    A Service declares one or more :class:`ServiceRole` values that describe
    what it can do.  The sandbox registers one ``Service`` instance per
    external entity.  The :class:`~harvest.agent_sandbox.service_router.SandboxServiceRouter`
    routes requests to the correct method based on role.

    Agents never hold direct references to ``Service`` instances.  All
    interactions are routed through the service router which enforces the
    two-level policy (sandbox registry ∩ agent :class:`~harvest.policy.ServicePermission`).

    Implementers must:

    - Declare ``service_id`` and ``roles``.
    - Implement ``fetch`` if ``DATA_SOURCE in roles``; raise
      :class:`NotImplementedError` otherwise.
    - Implement ``execute`` if ``ACTION in roles``; raise
      :class:`NotImplementedError` otherwise.
    - Accept ``event_bus`` in ``start`` if ``EVENT_SOURCE in roles``; the bus
      is used to publish :class:`~harvest.events.base.ExternalEventFired` events.
    - Return appropriate tools from ``get_tools``; ``EVENT_SOURCE``-only
      services return an empty list (inbox model).
    """

    @property
    @abstractmethod
    def service_id(self) -> str:
        """Stable identifier for this service (e.g. ``"alpaca"``)."""

    @property
    @abstractmethod
    def roles(self) -> frozenset[ServiceRole]:
        """The roles this service fulfills.

        Returns:
            Immutable set of :class:`ServiceRole` values.
        """

    @abstractmethod
    def get_capabilities(self) -> list[str]:
        """Return human-readable capabilities across all roles.

        Returns:
            List of capability strings.
        """

    @abstractmethod
    def get_tools(self, role: ServiceRole | None = None) -> list[InterfaceTool]:
        """Return interface tools, optionally filtered by role.

        If *role* is ``None``, return all tools across all roles.
        If *role* is specified, return only tools for that role.

        :class:`ServiceRole.EVENT_SOURCE` services return an empty list —
        events follow the inbox model, not the tool model.

        Args:
            role: Optional role filter.

        Returns:
            List of :class:`~harvest.interfaces.tool_definition.InterfaceTool`
            instances.
        """

    @abstractmethod
    async def fetch(self, query: DataQuery) -> DataResult:
        """Pull data on demand (DATA_SOURCE role).

        The service router calls this after verifying the requesting agent
        has policy permission.  The agent never calls this directly.

        Raise :class:`NotImplementedError` if ``DATA_SOURCE`` is not in
        :attr:`roles`.

        Args:
            query: Structured data request.

        Returns:
            A :class:`DataResult` with either a payload or an error string.
        """

    @abstractmethod
    async def execute(self, command: ActionCommand) -> ActionResult:
        """Execute a side-effecting operation (ACTION role).

        The service router calls this after verifying the requesting agent
        has policy permission.  The agent never calls this directly.

        Raise :class:`NotImplementedError` if ``ACTION`` is not in
        :attr:`roles`.

        Args:
            command: Structured action request.

        Returns:
            An :class:`ActionResult` with either a payload or an error string.
        """

    @abstractmethod
    async def start(self, event_bus: EventBus | None = None) -> None:
        """Initialize connections, authenticate, and prepare for use.

        For ``EVENT_SOURCE`` role services, ``event_bus`` is provided so the
        service can publish :class:`~harvest.events.base.ExternalEventFired`
        events.  Non-event-source services may ignore the parameter.

        Args:
            event_bus: Optional event bus provided by the router for
                EVENT_SOURCE role services.
        """

    @abstractmethod
    async def stop(self) -> None:
        """Tear down connections gracefully."""

    @abstractmethod
    def health_check(self) -> dict[str, Any]:
        """Return current health information.

        Returns:
            Dict with at least a ``"status"`` key.
        """

    # ------------------------------------------------------------------
    # Callback binding (concrete — not overridden by subclasses)
    # ------------------------------------------------------------------

    def bind_fetch_callback(
        self,
        callback: Callable[[str, str, str, dict[str, Any]], str],
    ) -> None:
        """Inject the service router's fetch dispatch callback.

        Called by :class:`~harvest.agent_sandbox.service_router.SandboxServiceRouter`
        at registration time for services with ``DATA_SOURCE`` role.
        Tool handlers use this callback to route requests through the full
        pipeline (policy enforcement, event bus audit) without holding a
        direct reference to the router.

        The callback signature is::

            callback(agent_id, service_id, query_type, params) -> str

        Args:
            callback: Router dispatch function.
        """
        self._fetch_callback: Callable[[str, str, str, dict[str, Any]], str] = callback

    def bind_execute_callback(
        self,
        callback: Callable[[str, str, str, dict[str, Any]], str],
    ) -> None:
        """Inject the service router's execute dispatch callback.

        Called by :class:`~harvest.agent_sandbox.service_router.SandboxServiceRouter`
        at registration time for services with ``ACTION`` role.
        Tool handlers use this callback to route commands through the full
        pipeline (policy enforcement, event bus audit) without holding a
        direct reference to the router.

        The callback signature is::

            callback(agent_id, service_id, command_type, params) -> str

        Args:
            callback: Router dispatch function.
        """
        self._execute_callback: Callable[[str, str, str, dict[str, Any]], str] = callback

    # ------------------------------------------------------------------
    # Dispatch helpers (reduce boilerplate in subclasses)
    # ------------------------------------------------------------------

    async def _dispatch_fetch(
        self,
        query: DataQuery,
        dispatch_table: dict[str, Callable[..., dict]],
    ) -> DataResult:
        """Route a DataQuery through a query_type → method mapping.

        Handles the try/except and unknown-type boilerplate that every
        ``fetch`` implementation repeats.

        Args:
            query: Incoming data query.
            dispatch_table: ``{query_type: method}`` map.  Methods are
                called with ``**query.params``.
        """
        handler = dispatch_table.get(query.query_type)
        if handler is None:
            return DataResult(
                request_id=query.request_id,
                source_id=self.service_id,
                payload={},
                error=f"Unknown query_type: {query.query_type}",
            )
        try:
            payload = handler(**query.params)
        except Exception as exc:
            return DataResult(
                request_id=query.request_id,
                source_id=self.service_id,
                payload={},
                error=str(exc),
            )
        return DataResult(
            request_id=query.request_id,
            source_id=self.service_id,
            payload=payload,
        )

    async def _dispatch_execute(
        self,
        command: ActionCommand,
        dispatch_table: dict[str, Callable[..., dict]],
    ) -> ActionResult:
        """Route an ActionCommand through a command_type → method mapping.

        Args:
            command: Incoming action command.
            dispatch_table: ``{command_type: method}`` map.
        """
        handler = dispatch_table.get(command.command_type)
        if handler is None:
            return ActionResult(
                request_id=command.request_id,
                action_id=self.service_id,
                payload={},
                error=f"Unknown command_type: {command.command_type}",
            )
        try:
            payload = handler(**command.params)
        except Exception as exc:
            return ActionResult(
                request_id=command.request_id,
                action_id=self.service_id,
                payload={},
                error=str(exc),
            )
        return ActionResult(
            request_id=command.request_id,
            action_id=self.service_id,
            payload=payload,
        )
