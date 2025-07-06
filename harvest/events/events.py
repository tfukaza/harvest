import datetime as dt
from dataclasses import dataclass
from enum import StrEnum

from ..definitions import (
    TickerFrame,
    Transaction,
    OrderSide,
    Order,
    Account,
    Position
)


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


@dataclass
class PriceUpdateEvent:
    """Event fired when price data is updated for a symbol."""
    symbol: str
    price_data: TickerFrame
    timestamp: dt.datetime


@dataclass
class OrderPlacedEvent:
    """Event fired when an order is placed by an algorithm."""
    order_id: str
    algorithm_name: str
    symbol: str
    side: OrderSide
    quantity: float
    order_type: str
    timestamp: dt.datetime
    order: Order | None = None


@dataclass
class OrderFilledEvent:
    """Event fired when an order is filled."""
    order_id: str
    algorithm_name: str
    symbol: str
    fill_price: float
    fill_quantity: float
    side: OrderSide
    timestamp: dt.datetime
    order: Order | None = None


@dataclass
class OrderCancelledEvent:
    """Event fired when an order is cancelled."""
    order_id: str
    algorithm_name: str
    symbol: str
    timestamp: dt.datetime
    reason: str | None = None


@dataclass
class TransactionEvent:
    """Event fired when a transaction is recorded."""
    algorithm_name: str
    transaction: Transaction
    timestamp: dt.datetime


@dataclass
class AccountUpdateEvent:
    """Event fired when account information is updated."""
    algorithm_name: str
    equity: float
    buying_power: float
    cash: float
    asset_value: float
    timestamp: dt.datetime
    account: Account | None = None


@dataclass
class PositionUpdateEvent:
    """Event fired when a position is updated."""
    algorithm_name: str
    symbol: str
    position: Position
    timestamp: dt.datetime


@dataclass
class AlgorithmStartedEvent:
    """Event fired when an algorithm starts running."""
    algorithm_name: str
    timestamp: dt.datetime
    metadata: dict | None = None


@dataclass
class AlgorithmStoppedEvent:
    """Event fired when an algorithm stops running."""
    algorithm_name: str
    timestamp: dt.datetime
    reason: str | None = None


@dataclass
class MarketDataEvent:
    """Event fired for general market data updates."""
    symbol: str
    data_type: DataType
    data: dict
    timestamp: dt.datetime


@dataclass
class ErrorEvent:
    """Event fired when an error occurs in the system."""
    component: ComponentType
    error_type: str
    error_message: str
    timestamp: dt.datetime
    algorithm_name: str | None = None
    metadata: dict | None = None


@dataclass
class ServiceHealthEvent:
    """Event fired when a service health status changes."""
    service_name: str
    health_status: HealthStatus
    timestamp: dt.datetime
    metadata: dict | None = None


@dataclass
class LogEvent:
    """Event fired for structured logging across the system."""
    level: LogLevel
    message: str
    component: ComponentType
    timestamp: dt.datetime
    algorithm_name: str | None = None
    metadata: dict | None = None


# Event type constants for easy reference
class EventTypes(StrEnum):
    PRICE_UPDATE = "price_update"
    ORDER_PLACED = "order_placed"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    TRANSACTION = "transaction"
    ACCOUNT_UPDATE = "account_update"
    POSITION_UPDATE = "position_update"
    ALGORITHM_STARTED = "algorithm_started"
    ALGORITHM_STOPPED = "algorithm_stopped"
    MARKET_DATA = "market_data"
    ERROR = "error"
    SERVICE_HEALTH = "service_health"
    LOG = "log"
