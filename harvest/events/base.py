"""Harvest event base class and typed domain events built on bubus.

All runtime events in Harvest extend ``HarvestEvent`` which itself
extends ``bubus.BaseEvent``.  Event routing happens through event class
and typed fields -- there are no colon-delimited string event names.
"""


import datetime as dt
from typing import Any

from bubus import BaseEvent
from pydantic import Field


class HarvestEvent(BaseEvent):
    """Base class for every event that flows through the Harvest event bus.

    Adds common metadata fields that the runtime needs everywhere on top
    of the ``bubus.BaseEvent`` foundation.
    """

    source: str = Field(default="", description="Component that emitted the event")
    timestamp_utc: dt.datetime = Field(
        default_factory=lambda: dt.datetime.now(dt.UTC),
        description="UTC timestamp when the domain action occurred",
    )


# ---------------------------------------------------------------------------
# Market data events
# ---------------------------------------------------------------------------


class PriceUpdated(HarvestEvent):
    """Emitted when new price data arrives for a symbol."""

    symbol: str
    interval: str
    broker_id: str
    exchange: str = ""
    price_data: Any = None


class AllPricesUpdated(HarvestEvent):
    """Emitted when all tickers for an interval cycle are ready."""

    interval: str
    broker_id: str
    exchange: str = ""
    symbols: list[str] = Field(default_factory=list)
    ticker_data: dict[str, Any] = Field(default_factory=dict)


class PeriodicTick(HarvestEvent):
    """Emitted on a periodic schedule for cron-like tasks."""

    interval: str
    broker_id: str
    exchange: str = ""


# ---------------------------------------------------------------------------
# Broker / order events
# ---------------------------------------------------------------------------


class OrderPlaced(HarvestEvent):
    """Emitted when an order is submitted to a broker."""

    order_id: str
    symbol: str
    side: str
    quantity: float
    order_type: str = ""
    algorithm_name: str = ""
    brokerage: str = ""


class OrderFilled(HarvestEvent):
    """Emitted when an order is filled by the broker."""

    order_id: str
    symbol: str
    side: str
    quantity: float
    filled_price: float
    algorithm_name: str = ""
    filled_time: Any = None


class OrderCancelled(HarvestEvent):
    """Emitted when an order is cancelled."""

    order_id: str
    brokerage: str = ""
    reason: str = ""


# ---------------------------------------------------------------------------
# Account / position events
# ---------------------------------------------------------------------------


class AccountUpdated(HarvestEvent):
    """Emitted when account information is updated."""

    algorithm_name: str
    equity: float
    buying_power: float
    cash: float
    asset_value: float
    account: Any = None


class PositionUpdated(HarvestEvent):
    """Emitted when a position changes."""

    algorithm_name: str
    symbol: str
    position: Any = None


# ---------------------------------------------------------------------------
# Algorithm lifecycle events
# ---------------------------------------------------------------------------


class AlgorithmStarted(HarvestEvent):
    """Emitted when an algorithm starts running."""

    algorithm_name: str
    metadata: dict[str, Any] | None = None


class AlgorithmStopped(HarvestEvent):
    """Emitted when an algorithm stops running."""

    algorithm_name: str
    reason: str = ""


# ---------------------------------------------------------------------------
# Runtime / agent lifecycle events
# ---------------------------------------------------------------------------


class RuntimeLifecycleChanged(HarvestEvent):
    """Emitted when a runtime lifecycle state changes."""

    runtime_id: str
    state: str
    metadata: dict[str, Any] | None = None


class AgentLifecycleChanged(HarvestEvent):
    """Emitted when an agent lifecycle state changes."""

    agent_id: str
    state: str
    metadata: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Tool invocation events
# ---------------------------------------------------------------------------


class ToolCallRequested(HarvestEvent):
    """Emitted when a runtime invokes a tool on behalf of an agent."""

    agent_id: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    runtime_id: str = ""


class ToolCallCompleted(HarvestEvent):
    """Emitted when a tool invocation completes."""

    agent_id: str
    tool_name: str
    result: Any = None
    runtime_id: str = ""
    error: str = ""


# ---------------------------------------------------------------------------
# Resource events
# ---------------------------------------------------------------------------


class ResourceUpdated(HarvestEvent):
    """Emitted when a runtime resource produces an update."""

    resource_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    capability: str = ""


# ---------------------------------------------------------------------------
# DataSource / Action / EventSource routing events
# ---------------------------------------------------------------------------


class DataFetchRequested(HarvestEvent):
    """Emitted by the sandbox service router when an agent requests data.

    The orchestrator (or service router) receives this, checks the agent's
    policy, and forwards to the appropriate DataSource.
    """

    agent_id: str
    source_id: str
    request_id: str
    query_type: str
    params: dict[str, Any] = Field(default_factory=dict)


class DataFetchCompleted(HarvestEvent):
    """Emitted when a DataSource responds to a fetch request.

    ``error`` is empty on success; non-empty (e.g. ``"policy_denied"``) on
    failure.
    """

    agent_id: str
    source_id: str
    request_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    error: str = ""


class ActionRequested(HarvestEvent):
    """Emitted by the sandbox service router when an agent issues a command.

    The orchestrator (or service router) receives this, checks the agent's
    policy, and forwards to the appropriate Action handler.
    """

    agent_id: str
    action_id: str
    request_id: str
    command_type: str
    params: dict[str, Any] = Field(default_factory=dict)


class ActionCompleted(HarvestEvent):
    """Emitted when an Action execution completes.

    ``error`` is empty on success; non-empty (e.g. ``"policy_denied"``) on
    failure.
    """

    agent_id: str
    action_id: str
    request_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    error: str = ""


class ExternalEventFired(HarvestEvent):
    """Emitted by an EventSource when a monitored condition is met.

    The sandbox service router receives this and fans it out to all agents
    that are subscribed to ``source_id``.
    """

    source_id: str
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ExternalEventDelivered(HarvestEvent):
    """Emitted after an ExternalEventFired is delivered to a subscribed agent.

    One instance is emitted per (agent, event) pair, providing a full audit
    trail of which agents received which external events.
    """

    source_id: str
    agent_id: str
    sandbox_id: str
    event_type: str


# ---------------------------------------------------------------------------
# Tool discovery / auto-registration events
# ---------------------------------------------------------------------------


class ToolsAutoRegistered(HarvestEvent):
    """Emitted when interface tools are wired as callables onto an agent at startup.

    This event records the completion of policy-driven auto-registration.
    The listed tools are callable on the agent from this point forward, but
    their signatures have not yet been injected into the agent's context.
    """

    agent_id: str
    tool_names: list[str]
    sandbox_id: str


class ToolSpecsInjected(HarvestEvent):
    """Emitted when tool signatures are injected into an agent's system prompt.

    Injected specs are durable — they survive context compaction and remain
    visible in the system prompt for the rest of the session.  This event is
    emitted once per tool per agent (the first ``discover_tools(tool_name)``
    call for that tool).
    """

    agent_id: str
    tool_names: list[str]


# ---------------------------------------------------------------------------
# Health / error / log events
# ---------------------------------------------------------------------------


class ServiceHealthChanged(HarvestEvent):
    """Emitted when a service health status changes."""

    service_name: str
    health_status: str
    metadata: dict[str, Any] | None = None


class ErrorOccurred(HarvestEvent):
    """Emitted when an error occurs in the system."""

    component: str
    error_type: str
    error_message: str
    algorithm_name: str = ""
    metadata: dict[str, Any] | None = None


class LogEmitted(HarvestEvent):
    """Emitted for structured logging across the system."""

    level: str
    message: str
    component: str
    algorithm_name: str = ""
    metadata: dict[str, Any] | None = None
