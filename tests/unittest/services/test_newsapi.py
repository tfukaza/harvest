"""Unit tests for NewsAPIService — mocks the HTTP layer."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from harvest.services.newsapi import NewsAPIService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _mock_session(status_code: int = 200, json_body: dict | None = None):
    sess = MagicMock()
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body or {}
    resp.text = json.dumps(json_body or {})
    sess.get.return_value = resp
    return sess


def _headlines_response() -> dict:
    return {
        "status": "ok",
        "totalResults": 2,
        "articles": [
            {
                "title": "Markets Rally",
                "description": "Stocks up.",
                "url": "https://example.com/1",
                "publishedAt": "2024-01-01T12:00:00Z",
                "source": {"name": "Reuters"},
                "author": "Jane Doe",
            },
            {
                "title": "Fed Holds Rates",
                "description": "No change.",
                "url": "https://example.com/2",
                "publishedAt": "2024-01-01T11:00:00Z",
                "source": {"name": "Bloomberg"},
                "author": None,
            },
        ],
    }


def _search_response() -> dict:
    return {
        "status": "ok",
        "totalResults": 1,
        "articles": [
            {
                "title": "Tech Earnings Beat",
                "description": "Q4 results.",
                "url": "https://example.com/3",
                "publishedAt": "2024-01-02T09:00:00Z",
                "source": {"name": "CNBC"},
                "content": "Tech companies reported...[+200 chars]",
            }
        ],
    }


# ---------------------------------------------------------------------------
# Tests: identity
# ---------------------------------------------------------------------------


def test_service_id() -> None:
    svc = NewsAPIService(api_key="test-key")
    assert svc.service_id == "newsapi"


def test_roles() -> None:
    from harvest.interfaces.service import ServiceRole
    svc = NewsAPIService(api_key="test-key")
    assert svc.roles == frozenset({ServiceRole.DATA_SOURCE})


def test_get_capabilities() -> None:
    svc = NewsAPIService(api_key="test-key")
    caps = svc.get_capabilities()
    assert "top_headlines" in caps
    assert "article_search" in caps


# ---------------------------------------------------------------------------
# Tests: tools
# ---------------------------------------------------------------------------


def test_get_tools_returns_two_tools() -> None:
    svc = NewsAPIService(api_key="test-key")
    tools = svc.get_tools()
    names = {t.name for t in tools}
    assert "newsapi_get_top_headlines" in names
    assert "newsapi_search_articles" in names


def test_get_tools_data_source_role_returns_tools() -> None:
    from harvest.interfaces.service import ServiceRole
    svc = NewsAPIService(api_key="test-key")
    tools = svc.get_tools(role=ServiceRole.DATA_SOURCE)
    assert len(tools) == 2


def test_get_tools_action_role_returns_empty() -> None:
    from harvest.interfaces.service import ServiceRole
    svc = NewsAPIService(api_key="test-key")
    tools = svc.get_tools(role=ServiceRole.ACTION)
    assert tools == []


# ---------------------------------------------------------------------------
# Tests: fetch — top headlines
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_top_headlines_returns_articles() -> None:
    from harvest.interfaces.service import DataQuery
    svc = NewsAPIService(api_key="test-key")
    svc._session = _mock_session(200, _headlines_response())

    result = await svc.fetch(DataQuery(
        query_type="top_headlines",
        params={"query": "market", "page_size": 10},
        agent_id="agent-1",
        request_id="req-1",
    ))

    assert result.error == ""
    articles = result.payload["articles"]
    assert len(articles) == 2
    assert articles[0]["title"] == "Markets Rally"
    assert articles[0]["source_name"] == "Reuters"


@pytest.mark.asyncio
async def test_fetch_top_headlines_unknown_query_type() -> None:
    from harvest.interfaces.service import DataQuery
    svc = NewsAPIService(api_key="test-key")

    result = await svc.fetch(DataQuery(
        query_type="unknown_type",
        params={},
        agent_id="agent-1",
        request_id="req-2",
    ))

    assert result.error != ""
    assert "unknown_type" in result.error.lower() or "Unknown" in result.error


@pytest.mark.asyncio
async def test_fetch_search_articles() -> None:
    from harvest.interfaces.service import DataQuery
    svc = NewsAPIService(api_key="test-key")
    svc._session = _mock_session(200, _search_response())

    result = await svc.fetch(DataQuery(
        query_type="search_articles",
        params={"query": "tech earnings", "page_size": 5},
        agent_id="agent-1",
        request_id="req-3",
    ))

    assert result.error == ""
    assert result.payload["total_results"] == 1
    assert result.payload["articles"][0]["title"] == "Tech Earnings Beat"


# ---------------------------------------------------------------------------
# Tests: HTTP error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_401_returns_error() -> None:
    from harvest.interfaces.service import DataQuery
    svc = NewsAPIService(api_key="bad-key")
    svc._session = _mock_session(401, {"message": "apiKeyInvalid"})

    result = await svc.fetch(DataQuery(
        query_type="top_headlines",
        params={},
        agent_id="agent-1",
        request_id="req-4",
    ))

    assert result.error != ""
    assert "authentication" in result.error.lower() or "401" in result.error


@pytest.mark.asyncio
async def test_fetch_429_returns_error() -> None:
    from harvest.interfaces.service import DataQuery
    svc = NewsAPIService(api_key="test-key")
    svc._session = _mock_session(429, {"message": "rateLimited"})

    result = await svc.fetch(DataQuery(
        query_type="top_headlines",
        params={},
        agent_id="agent-1",
        request_id="req-5",
    ))

    assert result.error != ""
    assert "rate" in result.error.lower()


@pytest.mark.asyncio
async def test_execute_raises_not_implemented() -> None:
    from harvest.interfaces.service import ActionCommand
    svc = NewsAPIService(api_key="test-key")
    with pytest.raises(NotImplementedError):
        await svc.execute(ActionCommand(
            command_type="x", params={}, agent_id="a", request_id="r"
        ))


# ---------------------------------------------------------------------------
# Tests: health check
# ---------------------------------------------------------------------------


def test_health_check_stopped() -> None:
    svc = NewsAPIService(api_key="test-key")
    hc = svc.health_check()
    assert hc["status"] == "stopped"


def test_health_check_running() -> None:
    svc = NewsAPIService(api_key="test-key")
    svc._session = MagicMock()
    hc = svc.health_check()
    assert hc["status"] == "healthy"
