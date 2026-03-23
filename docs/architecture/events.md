# Event System

**Files:** `harvest/events/base.py`, `harvest/events/events.py`, `harvest/events/event_bus.py`

Harvest uses a typed, in-process event bus (backed by `bubus`) for decoupled communication between system components. Events are strongly typed Pydantic models — there are no string event names.

## Event Bus

`harvest/events/event_bus.py` wraps `bubus.EventBus`:

```python
from harvest.events.event_bus import EventBus

bus = EventBus(name="my-sandbox")
bus.emit(PriceUpdated(source="alpaca", symbol="AAPL", interval="1d", broker_id="alpaca"))

# Subscribe by event class
bus.subscribe(PriceUpdated, my_handler)
```

**Cross-process distribution:** `harvest/event_server.py` and `harvest/event_client.py` provide HTTP-based event distribution. The server receives events over HTTP and fans them out to subscribers. Clients connect to the server and receive a filtered stream.

## HarvestEvent Base

All events extend `HarvestEvent`:

```python
class HarvestEvent(BaseEvent):
    source: str           # component that emitted the event (e.g. "alpaca-service")
    timestamp_utc: datetime  # UTC timestamp of the domain action
```

`BaseEvent` is from `bubus` and adds routing infrastructure. Every concrete event class is a Pydantic model with typed fields.

## Event Taxonomy

### Market Data

| Event | When | Key fields |
|-------|------|------------|
| `PriceUpdated` | New price data for a symbol | `symbol`, `interval`, `broker_id`, `price_data` |
| `AllPricesUpdated` | All tickers for an interval cycle ready | `interval`, `symbols`, `ticker_data` |
| `PeriodicTick` | Periodic schedule (cron-like) | `interval`, `broker_id` |

### Orders & Execution

| Event | When | Key fields |
|-------|------|------------|
| `OrderPlaced` | Order submitted to broker | `order_id`, `symbol`, `side`, `quantity` |
| `OrderFilled` | Order filled | `order_id`, `filled_price`, `filled_time` |
| `OrderCancelled` | Order cancelled | `order_id`, `reason` |

### Account & Positions

| Event | When | Key fields |
|-------|------|------------|
| `AccountUpdated` | Account info refreshed | `equity`, `buying_power`, `cash`, `asset_value` |
| `PositionUpdated` | Position changed | `symbol`, `position` |

### Lifecycle

| Event | When | Key fields |
|-------|------|------------|
| `AlgorithmStarted` | Algorithm begins running | `algorithm_name` |
| `AlgorithmStopped` | Algorithm stops | `algorithm_name`, `reason` |
| `RuntimeLifecycleChanged` | Runtime state change | `runtime_id`, `state` |
| `AgentLifecycleChanged` | Agent state change | `agent_id`, `state` |

### Tool Invocation

| Event | When | Key fields |
|-------|------|------------|
| `ToolCallRequested` | Tool called on behalf of agent | `agent_id`, `tool_name`, `arguments` |
| `ToolCallCompleted` | Tool returned | `agent_id`, `tool_name`, `result`, `error` |

### Service Routing (Audit)

These events are emitted by `SandboxServiceRouter` for every external interaction. They provide a complete audit trail of agent behavior.

| Event | When | Key fields |
|-------|------|------------|
| `DataFetchRequested` | Agent called `fetch_data` | `agent_id`, `source_id`, `query_type`, `params` |
| `DataFetchCompleted` | Fetch returned | `agent_id`, `source_id`, `payload`, `error` |
| `ActionRequested` | Agent called `execute_action` | `agent_id`, `action_id`, `command_type`, `params` |
| `ActionCompleted` | Action returned | `agent_id`, `action_id`, `payload`, `error` |
| `ExternalEventFired` | EVENT_SOURCE service published | `source_id`, `event_type`, `payload` |
| `ExternalEventDelivered` | Event delivered to agent inbox | `source_id`, `agent_id`, `sandbox_id`, `event_type` |

### Tool Discovery

| Event | When | Key fields |
|-------|------|------------|
| `ToolsAutoRegistered` | Agent wired at startup | `agent_id`, `sandbox_id`, `tool_names` |
| `ToolSpecsInjected` | Agent called `discover_tools(tool_name)` | `agent_id`, `sandbox_id`, `tool_name` |

### Resources

| Event | When | Key fields |
|-------|------|------------|
| `ResourceUpdated` | Runtime resource produced update | `resource_id`, `payload`, `capability` |

### Health & Errors

| Event | When | Key fields |
|-------|------|------------|
| `ServiceHealthChanged` | Service health status changed | `service_id`, `status` |
| `ErrorOccurred` | Component-level error | `component`, `error`, `details` |
| `LogEmitted` | Structured log event | `level`, `message`, `component` |

## Enumerations (`harvest/events/events.py`)

```python
class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    ERROR = "error"

class LifecycleState(Enum):
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"

class ComponentType(Enum):
    ALGORITHM = "algorithm"
    BROKER = "broker"
    SERVICE = "service"
    SYSTEM = "system"
    MAIN = "main"

class DataType(Enum):
    CANDLE = "candle"
    QUOTE = "quote"
    TRADE = "trade"
    ORDERBOOK = "orderbook"
    NEWS = "news"
```

## Event Bus in the Sandbox

`BasicSandbox` creates or accepts an `EventBus` at construction time. The bus is:

- **Optional** — most sandbox functionality works without one
- **Shared** — passed to the `SandboxServiceRouter` for audit events and to EVENT_SOURCE services for publishing
- **Used for observation** — the orchestrator and debug systems subscribe to events for monitoring

The event bus is not used for agent-to-agent communication. That happens exclusively through channels and the `ChatRouter`. The event bus is for system observability and service-to-sandbox push events.

## Structured Logging vs. Events

The event bus handles domain events (things that happened in the trading system). The structured logging system (`harvest/logging_config.py`) handles operational logs (component behavior, errors, debug traces). The two systems are complementary:

- Use events for things other components might act on (price updates, order fills, agent lifecycle changes)
- Use `log_event()` for observability, debugging, and audit trails that don't need reactive dispatch
