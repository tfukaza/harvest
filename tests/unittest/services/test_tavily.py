"""Unit tests for TavilyService — mocks the HTTP layer."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from harvest.services.tavily import TavilyService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _mock_session(status_code: int = 200, json_body: dict | None = None, headers: dict | None = None):
    sess = MagicMock()
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body or {}
    resp.text = json.dumps(json_body or {})
    resp.headers = headers or {}
    sess.post.return_value = resp
    return sess


def _search_response(answer: str = "Tavily is a search API.", results: list | None = None) -> dict:
    return {
        "answer": answer,
        "results": results or [
            {"title": "Tavily Docs", "url": "https://tavily.com/docs", "content": "API documentation", "score": 0.95},
        ],
        "response_time": 0.5,
    }


def _extract_response(results: list | None = None, failed: list | None = None) -> dict:
    return {
        "results": results or [
            {"url": "https://example.com", "raw_content": "# Example\n\nPage content here."},
        ],
        "failed_results": failed or [],
        "response_time": 0.3,
    }


def _crawl_response(base_url: str = "https://example.com", results: list | None = None) -> dict:
    return {
        "base_url": base_url,
        "results": results or [
            {"url": "https://example.com", "raw_content": "# Home\n\nWelcome."},
            {"url": "https://example.com/about", "raw_content": "# About\n\nAbout us."},
        ],
        "response_time": 2.1,
    }


# ---------------------------------------------------------------------------
# Tests: identity
# ---------------------------------------------------------------------------


def test_service_id() -> None:
    svc = TavilyService(api_key="test-key")
    assert svc.service_id == "tavily"


def test_roles() -> None:
    from harvest.interfaces.service import ServiceRole
    svc = TavilyService(api_key="test-key")
    assert svc.roles == frozenset({ServiceRole.DATA_SOURCE})


def test_get_capabilities() -> None:
    svc = TavilyService(api_key="test-key")
    caps = svc.get_capabilities()
    assert "web_search" in caps
    assert "extract" in caps
    assert "crawl" in caps


# ---------------------------------------------------------------------------
# Tests: tools
# ---------------------------------------------------------------------------


def test_get_tools_returns_three() -> None:
    svc = TavilyService(api_key="test-key")
    tools = svc.get_tools()
    names = {t.name for t in tools}
    assert names == {"tavily_search", "tavily_extract", "tavily_crawl"}


def test_get_tools_action_role_returns_empty() -> None:
    from harvest.interfaces.service import ServiceRole
    svc = TavilyService(api_key="test-key")
    tools = svc.get_tools(role=ServiceRole.ACTION)
    assert tools == []


def test_get_tools_data_source_role_returns_tools() -> None:
    from harvest.interfaces.service import ServiceRole
    svc = TavilyService(api_key="test-key")
    tools = svc.get_tools(role=ServiceRole.DATA_SOURCE)
    assert len(tools) == 3


# ---------------------------------------------------------------------------
# Tests: search
# ---------------------------------------------------------------------------


def test_search_basic() -> None:
    svc = TavilyService(api_key="test-key")
    svc._session = _mock_session(200, _search_response())

    result = svc._search(query="What is Tavily?")
    assert result["answer"] == "Tavily is a search API."
    assert len(result["results"]) == 1
    assert result["results"][0]["title"] == "Tavily Docs"
    assert "response_time" in result


def test_search_request_body() -> None:
    svc = TavilyService(api_key="test-key")
    svc._session = _mock_session(200, _search_response())

    svc._search(query="test query", search_depth="advanced", topic="news", max_results=10, time_range="week")

    call_args = svc._session.post.call_args
    body = call_args.kwargs.get("json") or call_args[1].get("json")
    assert body["query"] == "test query"
    assert body["search_depth"] == "advanced"
    assert body["topic"] == "news"
    assert body["max_results"] == 10
    assert body["time_range"] == "week"


def test_search_clamps_max_results() -> None:
    svc = TavilyService(api_key="test-key")
    svc._session = _mock_session(200, _search_response())

    svc._search(query="test", max_results=100)
    call_args = svc._session.post.call_args
    body = call_args.kwargs.get("json") or call_args[1].get("json")
    assert body["max_results"] == 20


def test_search_invalid_depth_defaults_to_basic() -> None:
    svc = TavilyService(api_key="test-key")
    svc._session = _mock_session(200, _search_response())

    svc._search(query="test", search_depth="invalid")
    call_args = svc._session.post.call_args
    body = call_args.kwargs.get("json") or call_args[1].get("json")
    assert body["search_depth"] == "basic"


# ---------------------------------------------------------------------------
# Tests: extract
# ---------------------------------------------------------------------------


def test_extract_single_url() -> None:
    svc = TavilyService(api_key="test-key")
    svc._session = _mock_session(200, _extract_response())

    result = svc._extract(urls="https://example.com")
    assert len(result["results"]) == 1
    assert result["results"][0]["url"] == "https://example.com"
    assert "raw_content" in result["results"][0]


def test_extract_multiple_urls() -> None:
    svc = TavilyService(api_key="test-key")
    resp = _extract_response(results=[
        {"url": "https://a.com", "raw_content": "A"},
        {"url": "https://b.com", "raw_content": "B"},
    ])
    svc._session = _mock_session(200, resp)

    result = svc._extract(urls="https://a.com, https://b.com")
    assert len(result["results"]) == 2


def test_extract_with_failures() -> None:
    svc = TavilyService(api_key="test-key")
    resp = _extract_response(
        results=[{"url": "https://a.com", "raw_content": "A"}],
        failed=[{"url": "https://b.com", "error": "timeout"}],
    )
    svc._session = _mock_session(200, resp)

    result = svc._extract(urls="https://a.com, https://b.com")
    assert len(result["results"]) == 1
    assert len(result["failed_results"]) == 1


def test_extract_empty_urls() -> None:
    svc = TavilyService(api_key="test-key")
    result = svc._extract(urls="")
    assert "error" in result


def test_extract_request_body() -> None:
    svc = TavilyService(api_key="test-key")
    svc._session = _mock_session(200, _extract_response())

    svc._extract(urls="https://example.com", extract_depth="advanced")
    call_args = svc._session.post.call_args
    body = call_args.kwargs.get("json") or call_args[1].get("json")
    assert body["urls"] == "https://example.com"
    assert body["extract_depth"] == "advanced"
    assert body["format"] == "markdown"


# ---------------------------------------------------------------------------
# Tests: crawl
# ---------------------------------------------------------------------------


def test_crawl_basic() -> None:
    svc = TavilyService(api_key="test-key")
    svc._session = _mock_session(200, _crawl_response())

    result = svc._crawl(url="https://example.com")
    assert result["base_url"] == "https://example.com"
    assert len(result["results"]) == 2


def test_crawl_with_instructions() -> None:
    svc = TavilyService(api_key="test-key")
    svc._session = _mock_session(200, _crawl_response())

    svc._crawl(url="https://example.com", instructions="Focus on team page")
    call_args = svc._session.post.call_args
    body = call_args.kwargs.get("json") or call_args[1].get("json")
    assert body["instructions"] == "Focus on team page"


def test_crawl_clamps_depth() -> None:
    svc = TavilyService(api_key="test-key")
    svc._session = _mock_session(200, _crawl_response())

    svc._crawl(url="https://example.com", max_depth=10)
    call_args = svc._session.post.call_args
    body = call_args.kwargs.get("json") or call_args[1].get("json")
    assert body["max_depth"] == 5


def test_crawl_request_body() -> None:
    svc = TavilyService(api_key="test-key")
    svc._session = _mock_session(200, _crawl_response())

    svc._crawl(url="https://example.com", max_depth=2, max_breadth=10, limit=25)
    call_args = svc._session.post.call_args
    body = call_args.kwargs.get("json") or call_args[1].get("json")
    assert body["url"] == "https://example.com"
    assert body["max_depth"] == 2
    assert body["max_breadth"] == 10
    assert body["limit"] == 25
    assert body["format"] == "markdown"


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------


def test_auth_failure() -> None:
    svc = TavilyService(api_key="bad-key")
    svc._session = _mock_session(401)

    with pytest.raises(RuntimeError, match="authentication failed"):
        svc._search(query="test")


def test_rate_limit() -> None:
    svc = TavilyService(api_key="test-key")
    svc._session = _mock_session(429, headers={"Retry-After": "30"})

    with pytest.raises(RuntimeError, match="rate limit"):
        svc._search(query="test")


def test_bad_request() -> None:
    svc = TavilyService(api_key="test-key")
    svc._session = _mock_session(400, {"detail": "Invalid query"})

    with pytest.raises(RuntimeError, match="bad request"):
        svc._search(query="")


def test_server_error() -> None:
    svc = TavilyService(api_key="test-key")
    svc._session = _mock_session(500, {"detail": "Internal error"})

    with pytest.raises(RuntimeError, match="error 500"):
        svc._search(query="test")
