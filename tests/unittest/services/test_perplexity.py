"""Unit tests for PerplexityService — mocks the HTTP layer."""


import json
from unittest.mock import MagicMock

import pytest

from harvest.services.perplexity import PerplexityService


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


def _search_response(answer: str = "Nuclear energy is clean.", citations: list | None = None) -> dict:
    return {
        "choices": [{"message": {"content": answer, "role": "assistant"}}],
        "citations": citations or ["https://iaea.org/example"],
        "usage": {"prompt_tokens": 10, "completion_tokens": 50},
    }


# ---------------------------------------------------------------------------
# Tests: identity
# ---------------------------------------------------------------------------


def test_service_id() -> None:
    svc = PerplexityService(api_key="test-key")
    assert svc.service_id == "perplexity"


def test_roles() -> None:
    from harvest.interfaces.service import ServiceRole
    svc = PerplexityService(api_key="test-key")
    assert svc.roles == frozenset({ServiceRole.DATA_SOURCE})


def test_get_capabilities() -> None:
    svc = PerplexityService(api_key="test-key")
    caps = svc.get_capabilities()
    assert "web_search" in caps
    assert "focused_search" in caps


# ---------------------------------------------------------------------------
# Tests: tools
# ---------------------------------------------------------------------------


def test_get_tools_returns_two_tools() -> None:
    svc = PerplexityService(api_key="test-key")
    tools = svc.get_tools()
    names = {t.name for t in tools}
    assert "perplexity_search" in names
    assert "perplexity_search_focused" in names


def test_get_tools_action_role_returns_empty() -> None:
    from harvest.interfaces.service import ServiceRole
    svc = PerplexityService(api_key="test-key")
    tools = svc.get_tools(role=ServiceRole.ACTION)
    assert tools == []


def test_get_tools_data_source_role_returns_tools() -> None:
    from harvest.interfaces.service import ServiceRole
    svc = PerplexityService(api_key="test-key")
    tools = svc.get_tools(role=ServiceRole.DATA_SOURCE)
    assert len(tools) == 2


# ---------------------------------------------------------------------------
# Tests: fetch — search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_search_returns_answer_and_citations() -> None:
    from harvest.interfaces.service import DataQuery
    svc = PerplexityService(api_key="test-key")
    svc._session = _mock_session(200, _search_response())

    result = await svc.fetch(DataQuery(
        query_type="search",
        params={"query": "Is nuclear energy clean?"},
        agent_id="agent-1",
        request_id="req-1",
    ))

    assert result.error == ""
    assert result.payload["answer"] == "Nuclear energy is clean."
    assert len(result.payload["citations"]) == 1
    assert result.payload["model"] == "sonar"
    assert "prompt_tokens" in result.payload["usage"]


@pytest.mark.asyncio
async def test_fetch_search_focused_uses_search_focus() -> None:
    from harvest.interfaces.service import DataQuery
    svc = PerplexityService(api_key="test-key")
    svc._session = _mock_session(200, _search_response("Finance answer."))

    result = await svc.fetch(DataQuery(
        query_type="search_focused",
        params={"query": "Gold prices 2024", "search_focus": "finance"},
        agent_id="agent-1",
        request_id="req-2",
    ))

    assert result.error == ""
    assert result.payload["answer"] == "Finance answer."
    # Verify the POST was called with the right system prompt adjustment
    call_kwargs = svc._session.post.call_args
    body = call_kwargs[1]["json"]
    # Should include a system message about finance
    system_messages = [m for m in body["messages"] if m["role"] == "system"]
    assert any("financial" in m["content"].lower() or "finance" in m["content"].lower()
               for m in system_messages)


@pytest.mark.asyncio
async def test_fetch_unknown_query_type_returns_error() -> None:
    from harvest.interfaces.service import DataQuery
    svc = PerplexityService(api_key="test-key")

    result = await svc.fetch(DataQuery(
        query_type="invalid_type",
        params={},
        agent_id="agent-1",
        request_id="req-3",
    ))

    assert result.error != ""


@pytest.mark.asyncio
async def test_fetch_with_custom_model() -> None:
    from harvest.interfaces.service import DataQuery
    svc = PerplexityService(api_key="test-key")
    svc._session = _mock_session(200, _search_response())

    result = await svc.fetch(DataQuery(
        query_type="search",
        params={"query": "test", "model": "sonar-pro"},
        agent_id="agent-1",
        request_id="req-4",
    ))

    assert result.error == ""
    assert result.payload["model"] == "sonar-pro"
    call_kwargs = svc._session.post.call_args
    assert call_kwargs[1]["json"]["model"] == "sonar-pro"


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_401_returns_auth_error() -> None:
    from harvest.interfaces.service import DataQuery
    svc = PerplexityService(api_key="bad-key")
    svc._session = _mock_session(401)

    result = await svc.fetch(DataQuery(
        query_type="search",
        params={"query": "test"},
        agent_id="agent-1",
        request_id="req-5",
    ))

    assert result.error != ""
    assert "authentication" in result.error.lower()


@pytest.mark.asyncio
async def test_fetch_429_returns_rate_limit_error() -> None:
    from harvest.interfaces.service import DataQuery
    svc = PerplexityService(api_key="test-key")
    svc._session = _mock_session(429, headers={"Retry-After": "30"})

    result = await svc.fetch(DataQuery(
        query_type="search",
        params={"query": "test"},
        agent_id="agent-1",
        request_id="req-6",
    ))

    assert result.error != ""
    assert "rate" in result.error.lower()


@pytest.mark.asyncio
async def test_execute_raises_not_implemented() -> None:
    from harvest.interfaces.service import ActionCommand
    svc = PerplexityService(api_key="test-key")
    with pytest.raises(NotImplementedError):
        await svc.execute(ActionCommand(
            command_type="x", params={}, agent_id="a", request_id="r"
        ))


# ---------------------------------------------------------------------------
# Tests: health check
# ---------------------------------------------------------------------------


def test_health_check_stopped() -> None:
    svc = PerplexityService(api_key="test-key")
    assert svc.health_check()["status"] == "stopped"


def test_health_check_running() -> None:
    svc = PerplexityService(api_key="test-key")
    svc._session = MagicMock()
    assert svc.health_check()["status"] == "healthy"
