"""Unit tests for the ServiceResult buffering system."""

from __future__ import annotations

import json

import pytest

from harvest.result_buffer import (
    BufferedResult,
    ResultBuffer,
    ServiceResult,
    _auto_summary,
    _estimate_tokens,
)


# ---------------------------------------------------------------------------
# ServiceResult
# ---------------------------------------------------------------------------


class TestServiceResult:
    def test_from_list(self) -> None:
        r = ServiceResult.from_list([1, 2, 3], summary="3 items")
        assert r.kind == "list"
        assert r.data == [1, 2, 3]
        assert r.summary == "3 items"

    def test_from_dict(self) -> None:
        r = ServiceResult.from_dict({"a": 1}, summary="one key")
        assert r.kind == "dict"
        assert r.data == {"a": 1}

    def test_from_text(self) -> None:
        r = ServiceResult.from_text("hello\nworld")
        assert r.kind == "text"
        assert r.data == "hello\nworld"
        assert r.summary is None

    def test_from_table(self) -> None:
        rows = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
        r = ServiceResult.from_table(rows)
        assert r.kind == "table"
        assert r.data["rows"] == rows
        assert r.data["columns"] == ["name", "age"]

    def test_from_table_custom_columns(self) -> None:
        rows = [{"x": 1}]
        r = ServiceResult.from_table(rows, columns=["x", "y"])
        assert r.data["columns"] == ["x", "y"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_estimate_tokens(self) -> None:
        assert _estimate_tokens("") == 1
        assert _estimate_tokens("a" * 100) == 25

    def test_auto_summary_list(self) -> None:
        s = _auto_summary([1, 2, 3], "list")
        assert "3 items" in s

    def test_auto_summary_dict(self) -> None:
        s = _auto_summary({"foo": 1, "bar": 2}, "dict")
        assert "foo" in s
        assert "bar" in s

    def test_auto_summary_text(self) -> None:
        s = _auto_summary("line1\nline2\nline3", "text")
        assert "3 lines" in s

    def test_auto_summary_table(self) -> None:
        s = _auto_summary({"rows": [{}], "columns": ["a", "b"]}, "table")
        assert "1 rows" in s


# ---------------------------------------------------------------------------
# ResultBuffer — three tiers
# ---------------------------------------------------------------------------


class TestPassthroughTier:
    def test_small_string_passes_through(self) -> None:
        buf = ResultBuffer(small_threshold_tokens=100)
        result = buf.process("tc1", "small result")
        assert result == "small result"
        assert buf.active_buffer_count == 0

    def test_small_service_result_passes_through(self) -> None:
        buf = ResultBuffer(small_threshold_tokens=100)
        sr = ServiceResult.from_dict({"key": "val"}, summary="tiny")
        result = buf.process("tc1", sr)
        data = json.loads(result)
        assert data["key"] == "val"
        assert buf.active_buffer_count == 0


class TestPaginatedTier:
    def test_medium_result_is_paginated(self) -> None:
        buf = ResultBuffer(
            small_threshold_tokens=10,
            large_threshold_tokens=5000,
            page_token_budget=50,
        )
        items = [{"id": i, "data": f"item_{i}" * 10} for i in range(20)]
        sr = ServiceResult.from_list(items, summary="20 items")
        result = buf.process("tc1", sr)

        assert "Summary: 20 items" in result
        assert "browse_results" in result
        assert buf.active_buffer_count == 1

    def test_paginated_shows_page_1(self) -> None:
        buf = ResultBuffer(
            small_threshold_tokens=10,
            large_threshold_tokens=5000,
            page_token_budget=50,
        )
        items = [{"id": i, "data": f"x" * 20} for i in range(20)]
        sr = ServiceResult.from_list(items, summary="20 items")
        result = buf.process("tc1", sr)

        assert "page 1" in result.lower()


class TestSummarizedTier:
    def test_large_result_is_summarized(self) -> None:
        buf = ResultBuffer(
            small_threshold_tokens=10,
            large_threshold_tokens=100,
            page_token_budget=50,
        )
        items = [{"id": i, "data": f"item_{i}" * 50} for i in range(50)]
        sr = ServiceResult.from_list(items, summary="50 big items")
        result = buf.process("tc1", sr)

        assert "Summary: 50 big items" in result
        assert "Chunk" in result
        assert "browse_results" in result
        assert buf.active_buffer_count == 1


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


class TestChunking:
    def setup_method(self) -> None:
        self.buf = ResultBuffer(page_token_budget=100)

    def test_chunk_list_preserves_items(self) -> None:
        items = [{"id": i} for i in range(5)]
        chunks = self.buf._chunk_list(items)
        # All items should be present across chunks
        all_items = []
        for c in chunks:
            all_items.extend(json.loads(c))
        assert len(all_items) == 5

    def test_chunk_dict_preserves_keys(self) -> None:
        obj = {f"key_{i}": f"value_{i}" for i in range(5)}
        chunks = self.buf._chunk_dict(obj)
        all_keys = set()
        for c in chunks:
            all_keys.update(json.loads(c).keys())
        assert all_keys == set(obj.keys())

    def test_chunk_text_covers_all_lines(self) -> None:
        text = "\n".join(f"Line {i}" for i in range(20))
        chunks = self.buf._chunk_text(text)
        # First chunk should start with Line 0
        assert "Line 0" in chunks[0]
        # Last chunk should contain Line 19
        assert "Line 19" in chunks[-1]

    def test_chunk_table_includes_header(self) -> None:
        data = {
            "columns": ["name", "value"],
            "rows": [{"name": f"r{i}", "value": i} for i in range(10)],
        }
        chunks = self.buf._chunk_table(data)
        for c in chunks:
            parsed = json.loads(c)
            assert "columns" in parsed
            assert parsed["columns"] == ["name", "value"]


# ---------------------------------------------------------------------------
# Browse: page, grep, slice
# ---------------------------------------------------------------------------


class TestBrowse:
    def setup_method(self) -> None:
        self.buf = ResultBuffer(
            small_threshold_tokens=500,
            large_threshold_tokens=50000,
            page_token_budget=500,
        )
        # Each item has ~200 chars of padding to ensure total exceeds small_threshold
        items = [{"id": i, "name": f"item_{i}", "level": "ERROR" if i % 5 == 0 else "INFO", "detail": f"detail_{'x' * 50}_{i}"} for i in range(30)]
        sr = ServiceResult.from_list(items, summary="30 items")
        self.buf.process("tc1", sr)

    def test_page_mode(self) -> None:
        result = self.buf.browse("tc1", mode="page", page=0)
        assert "item_" in result

    def test_page_out_of_range(self) -> None:
        result = self.buf.browse("tc1", mode="page", page=999)
        data = json.loads(result)
        assert "error" in data

    def test_grep_mode(self) -> None:
        result = self.buf.browse("tc1", mode="grep", query="ERROR")
        data = json.loads(result)
        assert data["total"] > 0
        for match in data["matches"]:
            assert match["level"] == "ERROR"

    def test_grep_no_matches(self) -> None:
        result = self.buf.browse("tc1", mode="grep", query="NONEXISTENT")
        data = json.loads(result)
        assert data["total"] == 0

    def test_slice_mode(self) -> None:
        result = self.buf.browse("tc1", mode="slice", offset=5, count=3)
        data = json.loads(result)
        assert data["count"] == 3
        assert data["offset"] == 5
        assert len(data["items"]) == 3

    def test_expired_buffer(self) -> None:
        result = self.buf.browse("nonexistent", mode="page", page=0)
        data = json.loads(result)
        assert "expired" in data["error"].lower() or "does not exist" in data["error"].lower()

    def test_unknown_mode(self) -> None:
        result = self.buf.browse("tc1", mode="invalid")
        data = json.loads(result)
        assert "error" in data


class TestBrowseText:
    def setup_method(self) -> None:
        self.buf = ResultBuffer(
            small_threshold_tokens=10,
            large_threshold_tokens=5000,
            page_token_budget=100,
        )
        text = "\n".join(f"Line {i}: {'ERROR' if i == 15 else 'normal content'}" for i in range(50))
        sr = ServiceResult.from_text(text, summary="50 lines")
        self.buf.process("tc_text", sr)

    def test_grep_text_with_context(self) -> None:
        result = self.buf.browse("tc_text", mode="grep", query="ERROR")
        assert ">>>" in result  # match marker
        assert "Line 15" in result

    def test_slice_text(self) -> None:
        result = self.buf.browse("tc_text", mode="slice", offset=10, count=5)
        assert "Line 10" in result
        assert "Line 14" in result


class TestBrowseTable:
    def setup_method(self) -> None:
        self.buf = ResultBuffer(
            small_threshold_tokens=500,
            large_threshold_tokens=50000,
            page_token_budget=500,
        )
        rows = [{"name": f"user_{i}", "role": "admin" if i < 3 else "member", "bio": f"bio_{'y' * 60}_{i}"} for i in range(20)]
        sr = ServiceResult.from_table(rows, summary="20 users")
        self.buf.process("tc_table", sr)

    def test_grep_table(self) -> None:
        result = self.buf.browse("tc_table", mode="grep", query="admin")
        data = json.loads(result)
        assert data["total"] == 3
        assert "columns" in data

    def test_slice_table(self) -> None:
        result = self.buf.browse("tc_table", mode="slice", offset=0, count=5)
        data = json.loads(result)
        assert len(data["rows"]) == 5
        assert data["columns"] == ["name", "role", "bio"]


# ---------------------------------------------------------------------------
# Buffer lifecycle
# ---------------------------------------------------------------------------


class TestBufferLifecycle:
    def test_max_active_buffers(self) -> None:
        buf = ResultBuffer(
            small_threshold_tokens=5,
            large_threshold_tokens=5000,
            page_token_budget=50,
            max_active_buffers=3,
        )
        for i in range(5):
            sr = ServiceResult.from_text("x" * 100, summary=f"buf {i}")
            buf.process(f"tc_{i}", sr)

        assert buf.active_buffer_count == 3

    def test_legacy_string_buffering(self) -> None:
        buf = ResultBuffer(small_threshold_tokens=5, large_threshold_tokens=5000)
        big_string = json.dumps({"data": "x" * 500})
        result = buf.process("tc1", big_string)
        assert "browse_results" in result
        assert buf.active_buffer_count == 1


# ---------------------------------------------------------------------------
# Heuristic summarization
# ---------------------------------------------------------------------------


class TestHeuristicSummary:
    def test_list_summary_with_levels(self) -> None:
        buf = ResultBuffer()
        items = [{"level": "ERROR"}, {"level": "INFO"}, {"level": "INFO"}]
        chunk = json.dumps(items)
        s = buf._summarize_chunk_heuristic(chunk, "list", 0)
        assert "3 items" in s
        assert "INFO" in s

    def test_dict_summary_lists_keys(self) -> None:
        buf = ResultBuffer()
        chunk = json.dumps({"alpha": 1, "beta": 2})
        s = buf._summarize_chunk_heuristic(chunk, "dict", 0)
        assert "alpha" in s
        assert "beta" in s

    def test_text_summary_shows_lines(self) -> None:
        buf = ResultBuffer()
        s = buf._summarize_chunk_heuristic("first\nsecond\nthird", "text", 0)
        assert "3 lines" in s
