"""Shared enumerations used by the Harvest event system.

Typed event classes live in ``harvest.events.base``.  This module
retains domain enums that are referenced by events and other runtime
code.
"""

from enum import StrEnum


class HealthStatus(StrEnum):
    """Health status enumeration."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    ERROR = "error"


class LogLevel(StrEnum):
    """Log level enumeration."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ComponentType(StrEnum):
    """Component type enumeration."""

    ALGORITHM = "algorithm"
    BROKER = "broker"
    SERVICE = "service"
    SYSTEM = "system"
    MAIN = "main"


class DataType(StrEnum):
    """Market data type enumeration."""

    CANDLE = "candle"
    QUOTE = "quote"
    TRADE = "trade"
    ORDERBOOK = "orderbook"
    NEWS = "news"


class LifecycleState(StrEnum):
    """Lifecycle state for runtime and agent events."""

    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
