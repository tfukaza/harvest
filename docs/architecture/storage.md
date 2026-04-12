# Storage

**Files:** `harvest/storage/schema/chat.py`, `harvest/storage/schema/agent.py`, `harvest/storage/schema/market.py`, `harvest/storage/base.py`

Harvest uses a two-tier storage model. All stores use SQLAlchemy via a `FlexibleStorage` base class, defaulting to in-memory SQLite for tests and development.

## Two-Tier Model

```
┌──────────────────────────────────┐   ┌──────────────────────────────────┐
│         Central Storage          │   │          Local Storage            │
│  (shared across agents/algos)    │   │   (per-agent, per-algorithm)     │
│                                  │   │                                  │
│  PriceHistory (market data)      │   │  ChatStore (channel messages)    │
│  AccountPerformanceHistory       │   │  ConversationStore (LLM history) │
│  (shared account state)          │   │  AlgorithmStore (algo logs)      │
└──────────────────────────────────┘   └──────────────────────────────────┘
```

## ChatStore (`harvest/storage/schema/chat.py`)

Append-only log of channel messages within a sandbox. Used by `ChatRouter` to persist inter-agent communication.

```python
store = ChatStore("sqlite:///sandbox.db")  # or ":memory:"

store.append_message(
    channel_id="team-discussion",
    message_index=0,            # monotonic per channel
    sender_id="alice",
    content="Hello team",
    timestamp="2026-03-22T10:00:00+00:00",
)

messages = store.load_channel("team-discussion")
# → [{"channel_id": ..., "message_index": ..., "sender_id": ..., "content": ..., "timestamp": ...}, ...]

channels = store.list_channels()  # → ["team-discussion", "dm:alice:bob"]
store.delete_channel("team-discussion")
```

**Schema:** `(channel_id, message_index)` unique constraint. `message_index` provides ordering without relying on insertion timestamps. The `ChatRouter` maintains `_channel_counters` per channel to assign monotonic indices.

**Role in staking:** When an agent is blocked by the channel stake and receives `channel_updated`, the router calls `store.load_channel(channel_id)` to include recent messages in the response.

## ConversationStore (`harvest/storage/schema/agent.py`)

Append-only log of an agent's LLM conversation history (all messages passed to and from the model). Used by `HarvestAgent` for optional persistence across restarts.

```python
store = ConversationStore("sqlite:///agent.db")

store.append_message(session_id="agent-abc123", turn_index=0, message=TextMessage(...))
store.append_message(session_id="agent-abc123", turn_index=1, message=ToolCallMessage(...))

history = store.load_log(session_id="agent-abc123")
# → list of Message subclasses in turn order
```

**Schema:** `(session_id, turn_index)` unique constraint. Message types stored: `text`, `tool_call`, `tool_result`, `summary`. Tool calls serialize `tool_calls` as JSON.

**Message types supported:**
- `TextMessage` → `role`, `content`
- `ToolCallMessage` → `role`, `content`, `tool_calls` (JSON array of `{id, function_name, arguments}`)
- `ToolResultMessage` → `role="tool"`, `tool_call_id`, `content`
- `SummaryMessage` → `role`, `content` (summary text), `summarized_turn_count`, `summary_generation`

## CentralStorage / MarketStorage (`harvest/storage/schema/market.py`)

Shared market data and account performance history. Used by the Orchestrator path.

```python
storage = CentralStorage("sqlite:///central.db")

storage.store_price_data(
    symbol="AAPL",
    interval=Interval.DAY_1,
    price_data=df,   # polars DataFrame with OHLCV columns
)

df = storage.fetch_price_data(symbol="AAPL", interval=Interval.DAY_1, limit=100)

storage.store_account_performance(interval=Interval.DAY_1, equity=105000.0, ...)
history = storage.fetch_account_performance(interval=Interval.DAY_1, limit=30)
```

**Schema:** `PriceHistory` has `(timestamp, symbol, interval)` unique constraint. `AccountPerformanceHistory` has `(timestamp, interval)` unique constraint.

**Retention policies:** Automatically applied on write. Defaults:
- 1-minute data: 1 day
- 5-minute data: 1 week
- 1-hour data: 3 months
- 1-day data: 1 year

## FlexibleStorage Base

All store classes delegate to `FlexibleStorage` from `harvest/storage/base.py`, which wraps SQLAlchemy with automatic table creation and a unified session lifecycle. Supports any SQLAlchemy-compatible database URL.

```python
from harvest.storage.base import FlexibleStorage

store = FlexibleStorage("sqlite:///:memory:")      # in-memory (tests)
store = FlexibleStorage("sqlite:///data.db")       # file-based SQLite
store = FlexibleStorage("postgresql://user:pw@host/db")  # production
```

## Other Storage Backends

For the Orchestrator path:

- `PickleStorage` — simple pickle-based persistence (development/testing)
- `CSVStorage` — CSV file per symbol (data analysis workflows)
- `DatabaseStorage` — full SQLAlchemy-backed implementation

All implement the `BaseStorage` ABC from `harvest/storage/_base.py`.
