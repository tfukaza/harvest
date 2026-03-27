"""Service Result Buffering System.

Phase 21: Transparent orchestration-layer middleware that intercepts all
service/tool results and applies size-appropriate handling.

Three-tier model:
- **Passthrough**: Small results injected directly into agent context.
- **Paginated**: Medium results chunked; page 0 + metadata injected.
- **Summarized**: Large results chunked and summarized; summaries injected.

Tools return :class:`ServiceResult` via factory constructors. The
:class:`ResultBuffer` handles all sizing, chunking, and navigation.
"""

from __future__ import annotations

import enum
import json
import math
import random
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Human-friendly ID generation
# ---------------------------------------------------------------------------

_ADJECTIVES = [
    "blue", "calm", "cool", "dark", "deep", "fair", "fast", "firm", "free",
    "full", "gold", "good", "gray", "half", "hard", "high", "keen", "kind",
    "last", "lean", "long", "main", "mild", "neat", "next", "nice", "open",
    "pale", "pink", "pure", "rare", "real", "rich", "ripe", "safe", "slim",
    "soft", "sure", "tall", "thin", "tiny", "warm", "wide", "wild", "wise",
]

_NOUNS = [
    "arch", "bank", "barn", "bell", "bird", "bolt", "bone", "book", "bush",
    "cake", "cape", "cave", "clay", "coat", "coin", "cord", "cork", "crab",
    "crow", "dawn", "deer", "dock", "dove", "drum", "duck", "dune", "dust",
    "edge", "fawn", "fern", "fish", "flag", "flax", "foam", "fork", "gate",
    "glen", "glow", "hare", "hawk", "helm", "hill", "hive", "horn", "jade",
    "kite", "knot", "lake", "lark", "leaf", "lime", "lion", "loom", "lynx",
    "mace", "malt", "mare", "mill", "mint", "mist", "moth", "nest", "opal",
    "orca", "pear", "pine", "plum", "pond", "reef", "rose", "sage", "seal",
    "snow", "star", "swan", "teak", "tide", "twig", "vale", "veil", "vine",
    "wave", "wren", "yew", "cove", "peak", "reed", "silk", "frog", "puma",
]


def _generate_friendly_id() -> str:
    """Generate a short, memorable ID like 'calm-deer' or 'gold-swan'."""
    return f"{random.choice(_ADJECTIVES)}-{random.choice(_NOUNS)}"


# ---------------------------------------------------------------------------
# Enums for data kind and browse mode
# ---------------------------------------------------------------------------


class ResultKind(str, enum.Enum):
    """Declares the shape of data in a ServiceResult."""

    LIST = "list"       # Array of objects: log entries, search results, records
    DICT = "dict"       # Nested object: configs, API responses, state snapshots
    TEXT = "text"       # Unstructured text: log dumps, web page content, docs
    TABLE = "table"     # Tabular data: SQL results, CSV exports, metric series


class BrowseMode(str, enum.Enum):
    """Modes for the browse_results tool."""

    PAGE = "page"       # Navigate by page index
    GREP = "grep"       # Search within buffered data
    SLICE = "slice"     # Extract a range by offset and count


# ---------------------------------------------------------------------------
# ServiceResult — tool/service return contract
# ---------------------------------------------------------------------------


class ServiceResult:
    """Structured return value from a service or tool.

    Tool authors use the ``from_*`` factory methods to declare data shape.
    The :class:`ResultBuffer` uses ``kind`` to select the appropriate
    chunking, grep, and slice strategy.
    """

    __slots__ = ("data", "kind", "summary")

    def __init__(self, data: Any, kind: ResultKind | str, summary: str | None = None) -> None:
        self.data = data
        self.kind = ResultKind(kind) if isinstance(kind, str) else kind
        self.summary = summary

    @classmethod
    def from_list(cls, items: list, summary: str | None = None) -> ServiceResult:
        """For arrays of objects: log entries, search results, records."""
        return cls(items, kind=ResultKind.LIST, summary=summary)

    @classmethod
    def from_dict(cls, obj: dict, summary: str | None = None) -> ServiceResult:
        """For nested objects: configs, API responses, state snapshots."""
        return cls(obj, kind=ResultKind.DICT, summary=summary)

    @classmethod
    def from_text(cls, text: str, summary: str | None = None) -> ServiceResult:
        """For unstructured text: log dumps, web page content, docs."""
        return cls(text, kind=ResultKind.TEXT, summary=summary)

    @classmethod
    def from_table(
        cls,
        rows: list[dict],
        columns: list[str] | None = None,
        summary: str | None = None,
    ) -> ServiceResult:
        """For tabular data: SQL results, CSV exports, metric series."""
        return cls(
            {"rows": rows, "columns": columns or list(rows[0].keys()) if rows else []},
            kind=ResultKind.TABLE,
            summary=summary,
        )


# ---------------------------------------------------------------------------
# BufferedResult — per-call storage
# ---------------------------------------------------------------------------


@dataclass
class BufferedResult:
    """Stored state for a single buffered service result."""

    raw_data: Any
    chunks: list[str]
    chunk_summaries: list[str] | None
    kind: ResultKind
    summary: str
    created_at: float
    last_accessed: float


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------

_SECONDS_PER_TURN = 60
"""Approximate seconds per agent turn, used for TTL-based buffer eviction."""


def _estimate_tokens(text: str) -> int:
    """Fast token estimate: ~4 characters per token."""
    return max(1, len(text) // 4)


def _auto_summary(data: Any, kind: ResultKind) -> str:
    """Generate a fallback summary from data shape."""
    if kind == ResultKind.LIST:
        return f"{len(data)} items"
    if kind == ResultKind.DICT:
        keys = list(data.keys())
        preview = ", ".join(keys[:10])
        if len(keys) > 10:
            preview += f", ... ({len(keys)} total keys)"
        return f"Dict with keys: {preview}"
    if kind == ResultKind.TEXT:
        lines = data.splitlines()
        return f"{len(lines)} lines, {len(data)} characters"
    if kind == ResultKind.TABLE:
        rows = data.get("rows", [])
        cols = data.get("columns", [])
        return f"{len(rows)} rows, columns: {', '.join(cols[:10])}"
    return f"Data of kind '{kind}'"


# ---------------------------------------------------------------------------
# ResultBuffer — core processing
# ---------------------------------------------------------------------------


class ResultBuffer:
    """Intercepts service results and applies three-tier size handling.

    Args:
        small_threshold_tokens: Below this, pass through as-is.
        large_threshold_tokens: Above this, summarize chunks.
        page_token_budget: Max tokens per page/response.
        text_overlap_lines: Context overlap for text chunking.
        buffer_ttl_turns: Evict buffers not accessed in this many turns.
        max_active_buffers: Max concurrent buffers.
        max_recursion_depth: Max depth for recursive buffering.
        summarization_strategy: "heuristic" or "llm".
        llm_summarizer_func: Callable for LLM summarization (if strategy="llm").
    """

    def __init__(
        self,
        small_threshold_tokens: int = 2000,
        large_threshold_tokens: int = 8000,
        page_token_budget: int = 2000,
        text_overlap_lines: int = 3,
        buffer_ttl_turns: int = 10,
        max_active_buffers: int = 20,
        max_recursion_depth: int = 2,
        summarization_strategy: str = "heuristic",
        llm_summarizer_func: Callable[..., str] | None = None,
    ) -> None:
        self._small_threshold = small_threshold_tokens
        self._large_threshold = large_threshold_tokens
        self._page_budget = page_token_budget
        self._text_overlap = text_overlap_lines
        self._ttl_turns = buffer_ttl_turns
        self._max_buffers = max_active_buffers
        self._max_recursion = max_recursion_depth
        self._summarization = summarization_strategy
        self._llm_summarizer = llm_summarizer_func

        self._buffers: dict[str, BufferedResult] = {}
        self._alias_to_key: dict[str, str] = {}  # friendly alias -> tool_call_id
        self._key_to_alias: dict[str, str] = {}  # tool_call_id -> friendly alias
        self._current_turn: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def advance_turn(self) -> None:
        """Called once per agent step to track turn-based expiry."""
        self._current_turn += 1
        self._evict_expired()

    def process(
        self,
        tool_call_id: str,
        result: ServiceResult | str,
        *,
        _recursion_depth: int = 0,
    ) -> str:
        """Process a service result and return the string to inject into context.

        Applies the three-tier model based on estimated token count:

        1. **Passthrough** (below ``small_threshold_tokens``): result is
           serialized and returned directly.
        2. **Paginated** (between small and large thresholds): data is chunked
           and page 0 + metadata is returned.  Agent can call ``browse_results``
           to access subsequent pages.
        3. **Summarized** (above ``large_threshold_tokens``): data is chunked
           and each chunk is summarized.  Full chunks remain accessible via
           ``browse_results``.

        Side effects:
            For tiers 2 and 3, the buffer is stored internally (keyed by
            ``tool_call_id``) for later ``browse()`` calls.  Old buffers are
            evicted when capacity or TTL limits are reached.

        Args:
            tool_call_id: Unique ID for this tool call.
            result: The service result (or plain string for legacy callers).

        Returns:
            String to inject as the tool_result content.
        """
        # Handle legacy string returns
        if isinstance(result, str):
            tokens = _estimate_tokens(result)
            if tokens <= self._small_threshold:
                return result
            # Wrap legacy string as text ServiceResult
            result = ServiceResult.from_text(result)

        serialized = self._serialize(result.data, result.kind)
        tokens = _estimate_tokens(serialized)
        summary = result.summary or _auto_summary(result.data, result.kind)

        # Tier 1: Passthrough
        if tokens <= self._small_threshold:
            return serialized

        # Chunk the data
        chunks = self._chunk(result.data, result.kind)

        # Tier 2: Paginated
        if tokens <= self._large_threshold:
            buf = BufferedResult(
                raw_data=result.data,
                chunks=chunks,
                chunk_summaries=None,
                kind=result.kind,
                summary=summary,
                created_at=time.time(),
                last_accessed=time.time(),
            )
            alias = self._store(tool_call_id, buf)
            return self._format_paginated(alias, buf, page=0)

        # Tier 3: Summarized
        chunk_summaries = self._summarize_chunks(chunks, result.kind)
        buf = BufferedResult(
            raw_data=result.data,
            chunks=chunks,
            chunk_summaries=chunk_summaries,
            kind=result.kind,
            summary=summary,
            created_at=time.time(),
            last_accessed=time.time(),
        )
        alias = self._store(tool_call_id, buf)
        return self._format_summarized(alias, buf)

    def browse(
        self,
        tool_call_id: str,
        mode: BrowseMode | str,
        page: int | None = None,
        query: str | None = None,
        offset: int | None = None,
        count: int | None = None,
        *,
        _recursion_depth: int = 0,
    ) -> str:
        """Navigate a previously buffered result.

        Supports three modes:
        - ``page``: Navigate by page index (0-based).
        - ``grep``: Search within buffered data by regex pattern.
        - ``slice``: Extract a range by offset and count.

        Returns:
            String result (may itself be buffered if too large).
        """
        # Resolve friendly alias to internal key
        resolved_key = self._alias_to_key.get(tool_call_id, tool_call_id)
        display_id = tool_call_id  # keep the alias the agent used
        buf = self._buffers.get(resolved_key)
        if buf is None:
            return json.dumps({
                "error": f"Buffer for '{display_id}' has expired or "
                         f"does not exist. Re-run the tool if you still need this data."
            })

        try:
            mode = BrowseMode(mode) if isinstance(mode, str) else mode
        except ValueError:
            return json.dumps({"error": f"Unknown mode: {mode}. Use page, grep, or slice."})

        buf.last_accessed = time.time()

        # raw_chunk holds the bare content (no page headers) for recursive
        # buffering; raw holds the full formatted output for direct return.
        raw_chunk: str | None = None

        if mode == BrowseMode.PAGE:
            p = page if page is not None else 0
            if p < 0 or p >= len(buf.chunks):
                return json.dumps({
                    "error": f"Page {p} out of range. Valid pages: 0–{len(buf.chunks) - 1}"
                })
            raw_chunk = buf.chunks[p]
            raw = self._format_page(display_id, buf, p)

        elif mode == BrowseMode.GREP:
            if not query:
                return json.dumps({"error": "query is required for mode=grep"})
            raw = self._grep(buf, query)

        elif mode == BrowseMode.SLICE:
            if offset is None or count is None:
                return json.dumps({"error": "offset and count are required for mode=slice"})
            raw = self._slice(buf, offset, count)

        # Recursive buffering: if browse result is too large, buffer it too.
        # Use raw_chunk (bare content) when available to avoid nesting
        # "Page X of Y" headers inside another pagination layer.
        content_to_check = raw_chunk if raw_chunk is not None else raw
        if _recursion_depth < self._max_recursion:
            tokens = _estimate_tokens(content_to_check)
            if tokens > self._small_threshold:
                total_pages = len(buf.chunks)
                item_info = self._page_item_info(buf, p) if mode == BrowseMode.PAGE else ""
                summary = (
                    f"Page {p + 1} of {total_pages}{item_info} from {display_id} "
                    f"(content too large, sub-paginated)"
                ) if raw_chunk is not None else f"Browse result ({mode}) for {display_id}"
                browse_id = f"{display_id}__browse_{mode}_{self._current_turn}"
                return self.process(
                    browse_id,
                    ServiceResult.from_text(content_to_check, summary=summary),
                    _recursion_depth=_recursion_depth + 1,
                )

        return raw

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def _serialize(self, data: Any, kind: ResultKind) -> str:
        if kind == ResultKind.TEXT:
            return data
        return json.dumps(data, indent=2, default=str)

    # ------------------------------------------------------------------
    # Chunking by kind
    # ------------------------------------------------------------------

    def _chunk(self, data: Any, kind: ResultKind) -> list[str]:
        dispatch = {
            ResultKind.LIST: self._chunk_list,
            ResultKind.DICT: self._chunk_dict,
            ResultKind.TEXT: self._chunk_text,
            ResultKind.TABLE: self._chunk_table,
        }
        chunker = dispatch.get(kind, self._chunk_fallback)
        return chunker(data)

    def _chunk_list(self, items: list) -> list[str]:
        chunks: list[str] = []
        current_items: list = []
        current_tokens = 0

        for item in items:
            item_str = json.dumps(item, default=str)
            item_tokens = _estimate_tokens(item_str)

            if current_tokens + item_tokens > self._page_budget and current_items:
                chunks.append(json.dumps(current_items, indent=2, default=str))
                current_items = []
                current_tokens = 0

            current_items.append(item)
            current_tokens += item_tokens

        if current_items:
            chunks.append(json.dumps(current_items, indent=2, default=str))

        return chunks or ["[]"]

    def _chunk_dict(self, obj: dict) -> list[str]:
        chunks: list[str] = []
        current_pairs: dict = {}
        current_tokens = 0

        for key, value in obj.items():
            pair_str = json.dumps({key: value}, default=str)
            pair_tokens = _estimate_tokens(pair_str)

            if current_tokens + pair_tokens > self._page_budget and current_pairs:
                chunks.append(json.dumps(current_pairs, indent=2, default=str))
                current_pairs = {}
                current_tokens = 0

            current_pairs[key] = value
            current_tokens += pair_tokens

        if current_pairs:
            chunks.append(json.dumps(current_pairs, indent=2, default=str))

        return chunks or ["{}"]

    def _chunk_text(self, text: str) -> list[str]:
        lines = text.splitlines(keepends=True)
        chunks: list[str] = []
        start = 0

        while start < len(lines):
            current_tokens = 0
            end = start
            while end < len(lines):
                line_tokens = _estimate_tokens(lines[end])
                if current_tokens + line_tokens > self._page_budget and end > start:
                    break
                current_tokens += line_tokens
                end += 1

            chunk_lines = lines[start:end]
            chunks.append("".join(chunk_lines))

            # Advance with overlap
            start = max(start + 1, end - self._text_overlap)

        return chunks or [""]

    def _chunk_table(self, data: dict) -> list[str]:
        rows = data.get("rows", [])
        columns = data.get("columns", [])
        header_str = json.dumps({"columns": columns}, default=str)
        header_tokens = _estimate_tokens(header_str)

        chunks: list[str] = []
        current_rows: list = []
        current_tokens = header_tokens

        for row in rows:
            row_str = json.dumps(row, default=str)
            row_tokens = _estimate_tokens(row_str)

            if current_tokens + row_tokens > self._page_budget and current_rows:
                chunk = json.dumps(
                    {"columns": columns, "rows": current_rows},
                    indent=2, default=str,
                )
                chunks.append(chunk)
                current_rows = []
                current_tokens = header_tokens

            current_rows.append(row)
            current_tokens += row_tokens

        if current_rows:
            chunk = json.dumps(
                {"columns": columns, "rows": current_rows},
                indent=2, default=str,
            )
            chunks.append(chunk)

        return chunks or [json.dumps({"columns": columns, "rows": []}, indent=2)]

    def _chunk_fallback(self, data: Any) -> list[str]:
        serialized = json.dumps(data, indent=2, default=str)
        # Treat as text
        return self._chunk_text(serialized)

    # ------------------------------------------------------------------
    # Chunk summarization (heuristic)
    # ------------------------------------------------------------------

    def _summarize_chunks(self, chunks: list[str], kind: ResultKind) -> list[str]:
        if self._summarization == "llm" and self._llm_summarizer:
            return self._summarize_chunks_llm(chunks)
        return [self._summarize_chunk_heuristic(c, kind, i) for i, c in enumerate(chunks)]

    def _summarize_chunk_heuristic(self, chunk: str, kind: ResultKind, index: int) -> str:
        if kind == ResultKind.LIST:
            try:
                items = json.loads(chunk)
                n = len(items)
                # Try to detect notable field distributions
                levels: dict[str, int] = {}
                for item in items:
                    if isinstance(item, dict):
                        for key in ("level", "status", "type", "severity"):
                            val = item.get(key)
                            if val:
                                levels[str(val)] = levels.get(str(val), 0) + 1
                summary = f"Chunk {index}: {n} items"
                if levels:
                    dist = ", ".join(f"{v} {k}" for k, v in sorted(levels.items(), key=lambda x: -x[1])[:5])
                    summary += f" ({dist})"
                return summary
            except (json.JSONDecodeError, TypeError):
                pass

        if kind == ResultKind.DICT:
            try:
                obj = json.loads(chunk)
                keys = list(obj.keys())
                return f"Chunk {index}: keys [{', '.join(keys[:8])}]"
            except (json.JSONDecodeError, TypeError):
                pass

        if kind == ResultKind.TEXT:
            lines = chunk.splitlines()
            first = lines[0].strip()[:80] if lines else ""
            last = lines[-1].strip()[:80] if len(lines) > 1 else ""
            summary = f"Chunk {index}: {len(lines)} lines"
            if first:
                summary += f", starts with: \"{first}\""
            if last and last != first:
                summary += f", ends with: \"{last}\""
            return summary

        if kind == ResultKind.TABLE:
            try:
                obj = json.loads(chunk)
                rows = obj.get("rows", [])
                return f"Chunk {index}: {len(rows)} rows"
            except (json.JSONDecodeError, TypeError):
                pass

        return f"Chunk {index}: {_estimate_tokens(chunk)} tokens"

    def _summarize_chunks_llm(self, chunks: list[str]) -> list[str]:
        summaries = []
        for i, chunk in enumerate(chunks):
            try:
                prompt = (
                    "Summarize this data in one sentence. "
                    "Mention notable patterns, errors, or anomalies.\n\n"
                    + chunk[:4000]
                )
                summary = self._llm_summarizer(prompt)  # type: ignore
                summaries.append(f"Chunk {i}: {summary}")
            except Exception:
                summaries.append(f"Chunk {i}: {_estimate_tokens(chunk)} tokens (summarization failed)")
        return summaries

    # ------------------------------------------------------------------
    # Grep by kind
    # ------------------------------------------------------------------

    def _grep(self, buf: BufferedResult, query: str) -> str:
        dispatch = {
            ResultKind.LIST: self._grep_list,
            ResultKind.DICT: self._grep_dict,
            ResultKind.TEXT: self._grep_text,
            ResultKind.TABLE: self._grep_table,
        }
        handler = dispatch.get(buf.kind, self._grep_text_fallback)
        return handler(buf.raw_data, query)

    def _grep_list(self, items: list, query: str) -> str:
        q = query.lower()
        matches = [
            item for item in items
            if q in json.dumps(item, default=str).lower()
        ]
        if not matches:
            return json.dumps({"matches": [], "total": 0, "query": query})
        return json.dumps({"matches": matches, "total": len(matches), "query": query}, indent=2, default=str)

    def _grep_dict(self, obj: dict, query: str) -> str:
        q = query.lower()
        matches = {}
        for key, value in obj.items():
            if q in key.lower() or q in json.dumps(value, default=str).lower():
                matches[key] = value
        if not matches:
            return json.dumps({"matches": {}, "total": 0, "query": query})
        return json.dumps({"matches": matches, "total": len(matches), "query": query}, indent=2, default=str)

    def _grep_text(self, text: str, query: str) -> str:
        q = query.lower()
        lines = text.splitlines()
        results: list[str] = []
        context = 3

        matching_indices = [i for i, line in enumerate(lines) if q in line.lower()]
        if not matching_indices:
            return json.dumps({"matches": [], "total": 0, "query": query})

        # Build context windows, merging overlaps
        shown: set[int] = set()
        for idx in matching_indices:
            start = max(0, idx - context)
            end = min(len(lines), idx + context + 1)
            for i in range(start, end):
                if i not in shown:
                    shown.add(i)
                    marker = ">>> " if i == idx else "    "
                    results.append(f"{marker}{i + 1:>5}: {lines[i]}")
            if end < len(lines):
                results.append("    ---")

        header = f"{len(matching_indices)} matches for \"{query}\"\n"
        return header + "\n".join(results)

    def _grep_table(self, data: dict, query: str) -> str:
        q = query.lower()
        rows = data.get("rows", [])
        columns = data.get("columns", [])
        matches = [
            row for row in rows
            if any(q in str(v).lower() for v in row.values())
        ]
        if not matches:
            return json.dumps({"columns": columns, "rows": [], "total": 0, "query": query})
        return json.dumps(
            {"columns": columns, "rows": matches, "total": len(matches), "query": query},
            indent=2, default=str,
        )

    def _grep_text_fallback(self, data: Any, query: str) -> str:
        return self._grep_text(json.dumps(data, indent=2, default=str), query)

    # ------------------------------------------------------------------
    # Slice by kind
    # ------------------------------------------------------------------

    def _slice(self, buf: BufferedResult, offset: int, count: int) -> str:
        dispatch = {
            ResultKind.LIST: self._slice_list,
            ResultKind.DICT: self._slice_dict,
            ResultKind.TEXT: self._slice_text,
            ResultKind.TABLE: self._slice_table,
        }
        handler = dispatch.get(buf.kind, self._slice_fallback)
        return handler(buf.raw_data, offset, count)

    def _slice_list(self, items: list, offset: int, count: int) -> str:
        sliced = items[offset:offset + count]
        return json.dumps(
            {"items": sliced, "offset": offset, "count": len(sliced), "total": len(items)},
            indent=2, default=str,
        )

    def _slice_dict(self, obj: dict, offset: int, count: int) -> str:
        keys = list(obj.keys())
        selected_keys = keys[offset:offset + count]
        sliced = {k: obj[k] for k in selected_keys}
        return json.dumps(
            {"data": sliced, "offset": offset, "count": len(sliced), "total_keys": len(keys)},
            indent=2, default=str,
        )

    def _slice_text(self, text: str, offset: int, count: int) -> str:
        lines = text.splitlines()
        sliced = lines[offset:offset + count]
        numbered = [f"{offset + i + 1:>5}: {line}" for i, line in enumerate(sliced)]
        header = f"Lines {offset + 1}–{offset + len(sliced)} of {len(lines)}\n"
        return header + "\n".join(numbered)

    def _slice_table(self, data: dict, offset: int, count: int) -> str:
        rows = data.get("rows", [])
        columns = data.get("columns", [])
        sliced = rows[offset:offset + count]
        return json.dumps(
            {"columns": columns, "rows": sliced, "offset": offset, "count": len(sliced), "total_rows": len(rows)},
            indent=2, default=str,
        )

    def _slice_fallback(self, data: Any, offset: int, count: int) -> str:
        return self._slice_text(json.dumps(data, indent=2, default=str), offset, count)

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def _format_paginated(self, tool_call_id: str, buf: BufferedResult, page: int) -> str:
        total_pages = len(buf.chunks)
        item_info = self._page_item_info(buf, page)
        lines = [
            f"Summary: {buf.summary}",
            f"Showing page {page + 1} of {total_pages}{item_info}",
            "",
            buf.chunks[page],
            "",
            f'[Use browse_results("{tool_call_id}", mode="page|grep|slice", ...) to explore further.]',
        ]
        return "\n".join(lines)

    def _format_summarized(self, tool_call_id: str, buf: BufferedResult) -> str:
        total_chunks = len(buf.chunks)
        lines = [
            f"Summary: {buf.summary}",
            f"Result was large ({total_chunks} chunks). Chunk summaries below:",
            "",
        ]
        for i, s in enumerate(buf.chunk_summaries or []):
            lines.append(s)
        lines.append("")
        lines.append(f'[Use browse_results("{tool_call_id}", mode="page", page=N) to read a specific chunk.]')
        lines.append(f'[Use browse_results("{tool_call_id}", mode="grep", query="...") to search across all chunks.]')
        lines.append(f'[Use browse_results("{tool_call_id}", mode="slice", offset=N, count=N) to read a specific range.]')
        return "\n".join(lines)

    def _format_page(self, tool_call_id: str, buf: BufferedResult, page: int) -> str:
        total_pages = len(buf.chunks)
        item_info = self._page_item_info(buf, page)
        lines = [
            f"Page {page + 1} of {total_pages}{item_info}",
            "",
            buf.chunks[page],
        ]
        if page + 1 < total_pages:
            lines.append("")
            lines.append(f'[Next page: browse_results("{tool_call_id}", mode="page", page={page + 1})]')
        return "\n".join(lines)

    def _page_item_info(self, buf: BufferedResult, page: int) -> str:
        if buf.kind == ResultKind.LIST and isinstance(buf.raw_data, list):
            # Calculate item ranges per page
            total = len(buf.raw_data)
            items_per_page = math.ceil(total / len(buf.chunks)) if buf.chunks else total
            start = page * items_per_page
            end = min(start + items_per_page, total)
            return f" (items {start}–{end - 1} of {total})"
        return ""

    # ------------------------------------------------------------------
    # Buffer storage and lifecycle
    # ------------------------------------------------------------------

    def _store(self, tool_call_id: str, buf: BufferedResult) -> str:
        """Store a buffer and return the friendly alias for user-facing output."""
        # Capacity-based eviction
        while len(self._buffers) >= self._max_buffers:
            oldest_id = min(self._buffers, key=lambda k: self._buffers[k].last_accessed)
            old_alias = self._key_to_alias.pop(oldest_id, None)
            if old_alias:
                self._alias_to_key.pop(old_alias, None)
            del self._buffers[oldest_id]
        self._buffers[tool_call_id] = buf

        # Generate a unique friendly alias
        alias = _generate_friendly_id()
        attempts = 0
        while alias in self._alias_to_key and attempts < 20:
            alias = _generate_friendly_id()
            attempts += 1
        self._alias_to_key[alias] = tool_call_id
        self._key_to_alias[tool_call_id] = alias
        return alias

    def _evict_expired(self) -> None:
        """Remove buffers that haven't been accessed recently."""
        now = time.time()
        expired = [
            k for k, v in self._buffers.items()
            if (now - v.last_accessed) > self._ttl_turns * _SECONDS_PER_TURN
        ]
        for k in expired:
            alias = self._key_to_alias.pop(k, None)
            if alias:
                self._alias_to_key.pop(alias, None)
            del self._buffers[k]

    def get_buffer(self, tool_call_id: str) -> BufferedResult | None:
        """Look up a buffer by tool call ID (for testing/introspection)."""
        return self._buffers.get(tool_call_id)

    @property
    def active_buffer_count(self) -> int:
        return len(self._buffers)
