"""Harvest event base class and typed domain events built on bubus.

All runtime events in Harvest extend ``HarvestEvent`` which itself
extends ``bubus.BaseEvent``.  Event routing happens through event class
and typed fields -- there are no colon-delimited string event names.
"""

from __future__ import annotations

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
