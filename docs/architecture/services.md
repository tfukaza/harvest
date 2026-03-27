# Service Abstraction

**Files:** `harvest/interfaces/service.py`, `harvest/services/`

The Service abstraction is the unified contract for every external-world interaction in the agent sandbox. One `Service` object per external entity handles data reads, action execution, and event streaming — all from a single lifecycle.

## Design Rationale

Before Phase 15, three separate ABCs existed: `DataSource`, `Action`, and `EventSource`. A real-world entity like Alpaca, which provides market data, order execution, and live streaming, required three separate objects sharing credentials and lifecycle. Phase 15 unified them.

The `DATA_SOURCE` / `ACTION` / `EVENT_SOURCE` distinction is **preserved for policy and security**, not discarded. Policy systems grant access to roles individually, enforcing the read-only / read-write boundary at the type level.

## ServiceRole

```python
class ServiceRole(Enum):
    DATA_SOURCE = "data_source"   # read-only, side-effect-free data access
    EVENT_SOURCE = "event_source" # push-based, read-only event delivery
    ACTION = "action"             # operations that may cause side effects
```

`DATA_SOURCE` and `EVENT_SOURCE` are both read-only. `ACTION` is the deliberate privileged role — granting it is a separate policy decision with different risk implications.

## Service ABC

```python
class Service(ABC):
    service_id: str              # stable identifier, e.g. "alpaca"
    roles: frozenset[ServiceRole]

    async def fetch(query: DataQuery) -> DataResult        # DATA_SOURCE
    async def execute(command: ActionCommand) -> ActionResult  # ACTION
    async def start(event_bus=None) -> None
    async def stop() -> None
    def get_tools(role=None) -> list[InterfaceTool]
    def health_check() -> dict
```

Agents never hold direct references to `Service` instances. All interactions route through `SandboxServiceRouter`, which enforces the two-level policy before calling `fetch()` or `execute()`.

## Data Transfer Objects

```python
# DATA_SOURCE request/response
DataQuery(query_type, params, agent_id, request_id)
DataResult(request_id, source_id, payload, error="")

# ACTION request/response
ActionCommand(command_type, params, agent_id, request_id)
ActionResult(request_id, action_id, payload, error="")
```

`error` is an empty string on success, non-empty on failure. Callers check `result.error` before using `result.payload`.

## ServicePermission

`ServicePermission` is the agent-level policy entry for service access:

```python
@dataclass(frozen=True)
class ServicePermission:
    service_id: str
    roles: frozenset[ServiceRole] | None  # None = all roles the service declares
```

Examples:
```python
# Full access to alpaca (data + actions + events)
ServicePermission("alpaca")

# Read-only access to alpaca (market data only, no order placement)
ServicePermission("alpaca", roles=frozenset({ServiceRole.DATA_SOURCE}))

# News data only
ServicePermission("newsapi", roles=frozenset({ServiceRole.DATA_SOURCE}))
```

## Callback Binding

Tool handlers in concrete services call the router without holding a direct reference to it. At registration time, the router injects two callbacks:

```python
service.bind_fetch_callback(callback)    # DATA_SOURCE tools use this
service.bind_execute_callback(callback)  # ACTION tools use this
```

The callback signature is `(agent_id, service_id, query_type_or_command_type, params) -> str`. This lets tool handlers route through the full pipeline (policy enforcement, audit events) while remaining decoupled from the router.

## Concrete Services

### AlpacaService (`harvest/services/alpaca.py`)

`service_id = "alpaca"`, `roles = {DATA_SOURCE, EVENT_SOURCE, ACTION}`

Uses the `alpaca-py` SDK (lazy-imported to avoid hard dependency). Provides:

| Role | Tools |
|------|-------|
| DATA_SOURCE | `alpaca_get_stock_bars`, `alpaca_get_latest_quote`, `alpaca_get_account`, `alpaca_get_positions` |
| ACTION | `alpaca_place_order`, `alpaca_cancel_order`, `alpaca_get_order` |
| EVENT_SOURCE | Streams `bar_update` and `trade_update` events via `StockDataStream` background thread |

### PaperBrokerService (`harvest/services/paper_broker.py`)

`service_id = "paper"`, `roles = {DATA_SOURCE, ACTION}`

Fully in-memory simulated broker. No external dependencies. Uses `generate_ticker_frame()` from `harvest/util/helper.py` for deterministic synthetic price history (seeded by `hash(symbol)`).

| Role | Tools |
|------|-------|
| DATA_SOURCE | `paper_get_price_history`, `paper_get_latest_price`, `paper_get_account`, `paper_get_positions` |
| ACTION | `paper_place_order`, `paper_cancel_order`, `paper_get_order` |

Market orders fill immediately; limit orders stay pending. Tracks cash and position balances, returns `insufficient_funds` errors when appropriate.

### NewsAPIService (`harvest/services/newsapi.py`)

`service_id = "newsapi"`, `roles = {DATA_SOURCE}`

Wraps the NewsAPI REST API. Uses `requests.Session` with `X-Api-Key` header.

| Role | Tools |
|------|-------|
| DATA_SOURCE | `newsapi_get_top_headlines`, `newsapi_search_articles` |

`start()` fires a validation request. `stop()` closes the session.

### PerplexityService (`harvest/services/perplexity.py`)

`service_id = "perplexity"`, `roles = {DATA_SOURCE}`

Wraps Perplexity's OpenAI-compatible REST API at `https://api.perplexity.ai/chat/completions`.

| Role | Tools |
|------|-------|
| DATA_SOURCE | `perplexity_search`, `perplexity_search_focused` |

`perplexity_search_focused` accepts a `search_focus` domain hint (e.g. `"news"`, `"academic"`). Returns `{answer, citations, model, usage}`.

### TavilyService (`harvest/services/tavily.py`)

`service_id = "tavily"`, `roles = {DATA_SOURCE}`

Wraps the Tavily REST API (`https://api.tavily.com`) for web search, page extraction, and site crawling. Uses `requests.Session` with Bearer token auth.

| Role | Tools |
|------|-------|
| DATA_SOURCE | `tavily_search`, `tavily_extract`, `tavily_crawl` |

`tavily_search` supports `search_depth` (basic/advanced), `topic` filtering (general/news/finance), and `time_range` constraints (day/week/month/year). `tavily_extract` reads full page content from one or more URLs. `tavily_crawl` performs graph-based site crawling with `max_depth`, `max_breadth`, and natural-language `instructions` for guided exploration. All three tools return `ServiceResult` objects for integration with the ResultBuffer.

## Implementing a New Service

```python
from harvest.interfaces.service import Service, ServiceRole, DataQuery, DataResult

class MyDataService(Service):
    service_id = "myservice"
    roles = frozenset({ServiceRole.DATA_SOURCE})

    def get_capabilities(self):
        return ["my_data"]

    def get_tools(self, role=None):
        return [InterfaceTool(
            name="myservice_query",
            short_description="Query my service",
            full_description="...",
            arguments=[ToolArgument("q", "string", "The query", required=True)],
            returns_description="JSON result",
            service_id="myservice",
            service_type="data_source",
            handler=self._handle_query,
        )]

    def _handle_query(self, agent_id: str, q: str) -> str:
        return self._fetch_callback(agent_id, "myservice", "query", {"q": q})

    async def fetch(self, query: DataQuery) -> DataResult:
        if query.query_type == "query":
            data = self._do_work(query.params["q"])
            return DataResult(query.request_id, "myservice", {"result": data})
        return DataResult(query.request_id, "myservice", {}, error="unknown query_type")

    async def execute(self, command):
        raise NotImplementedError

    async def start(self, event_bus=None):
        pass

    async def stop(self):
        pass

    def health_check(self):
        return {"status": "ok"}
```

Register it:

```python
router.register_service(MyDataService())
```
