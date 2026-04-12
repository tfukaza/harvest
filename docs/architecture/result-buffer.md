# Result Buffer

**File:** `harvest/result_buffer.py`

The `ResultBuffer` is transparent middleware that intercepts tool and service results before they enter the agent's conversation context. It applies size-appropriate handling so agents can work with arbitrarily large data without blowing up their context window.

## Three-Tier Model

Results are routed by estimated token count (4 chars per token):

1. **Passthrough** (below `small_threshold_tokens`, default 2000): The result is serialized and injected directly into context. No buffering occurs.
2. **Paginated** (between small and large thresholds, default 2000-8000): Data is chunked and page 0 plus navigation metadata is injected. The full dataset is stored internally, keyed by `tool_call_id`, for later `browse_results` calls.
3. **Summarized** (above `large_threshold_tokens`, default 8000): Data is chunked and each chunk receives a heuristic or LLM-generated summary. Only summaries are injected into context. Full chunks remain accessible via `browse_results`.

## ServiceResult Contract

Tool authors return `ServiceResult` instead of raw strings to declare data shape. Factory constructors:

- `ServiceResult.from_list(items, summary?)` — arrays (search results, log entries)
- `ServiceResult.from_dict(obj, summary?)` — nested objects (API responses, configs)
- `ServiceResult.from_text(text, summary?)` — unstructured text (page content, logs)
- `ServiceResult.from_table(rows, columns?, summary?)` — tabular data (SQL results, CSVs)

The `ResultKind` enum (`LIST`, `DICT`, `TEXT`, `TABLE`) drives kind-specific chunking, grep, and slice behavior. Legacy string returns are handled transparently — large strings are auto-wrapped as `TEXT`.

## BrowseMode

The `browse()` method supports three navigation modes:

- **page** — navigate by 0-based page index; returns a single chunk with prev/next hints
- **grep** — regex search within the buffered data; returns matching items/lines with context
- **slice** — extract a range by offset and count; returns the selected subset with position metadata

Each mode dispatches to kind-specific implementations (e.g., `_grep_list` filters items, `_grep_text` shows matching lines with context windows).

## Buffer Lifecycle

- **TTL-based eviction**: `advance_turn()` is called once per agent step. Buffers not accessed within `buffer_ttl_turns` (default 10) turns are evicted.
- **Capacity limits**: `max_active_buffers` (default 20) enforces a hard cap. When full, the least-recently-accessed buffer is evicted.
- **Turn tracking**: `_current_turn` increments each step, driving expiry calculations.

## browse_results Tool

Registered automatically on every `HarvestAgent` at construction via `_register_browse_results_tool()`. The tool signature:

```
browse_results(tool_call_id, mode="page", page=None, query=None, offset=None, count=None)
```

If a `browse_results` response is itself too large, it is recursively buffered (up to `max_recursion_depth`, default 2), so agents never receive unbounded output regardless of query selectivity.
