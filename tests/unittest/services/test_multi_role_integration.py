"""Multi-role integration test: all four services co-exist in one sandbox.

Registers AlpacaService (3 roles), PaperBrokerService (2 roles),
NewsAPIService (1 role), and PerplexityService (1 role) in the same
SandboxServiceRouter. Verifies policy-filtered tool wiring, discover_tools,
and that fetch/execute calls route correctly.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from harvest.agent_sandbox.service_router import SandboxServiceRouter
from harvest.interfaces.service import ServicePermission, ServiceRole
from harvest.policy import AgentPolicy
from harvest.services.paper_broker import PaperBrokerService


# ---------------------------------------------------------------------------
# Build stub NewsAPI and Perplexity (avoid real HTTP)
# ---------------------------------------------------------------------------


def _make_newsapi() -> Any:
    from harvest.services.newsapi import NewsAPIService
    svc = NewsAPIService(api_key="fake-key")
    # Pre-inject a mock session so no HTTP goes out
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"articles": []}
    mock_session.get.return_value = mock_resp
    svc._session = mock_session
    return svc


def _make_perplexity() -> Any:
    from harvest.services.perplexity import PerplexityService
    svc = PerplexityService(api_key="fake-key")
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "answer", "role": "assistant"}}],
        "citations": [],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }
    mock_session.post.return_value = mock_resp
    svc._session = mock_session
    return svc


def _make_alpaca() -> Any:
    from harvest.services.alpaca import AlpacaService
    svc = AlpacaService(api_key="fake-key", secret_key="fake-secret", paper=True)
    # Inject mock clients
    hist = MagicMock()
    trading = MagicMock()
    account = MagicMock()
    account.equity = "100000"
    account.cash = "100000"
    account.buying_power = "100000"
    account.portfolio_value = "100000"
    account.currency = "USD"
    account.status = "ACTIVE"
    account.pattern_day_trader = False
    trading.get_account.return_value = account
    trading.get_all_positions.return_value = []
    bars_resp = MagicMock()
    bars_resp.get.return_value = []
    hist.get_stock_bars.return_value = bars_resp
    svc._hist_client = hist
    svc._trading_client = trading

    # Minimal alpaca mock dict for _parse_timeframe etc.
    alpaca_mock = {
        "StockBarsRequest": MagicMock(return_value=MagicMock()),
        "StockLatestQuoteRequest": MagicMock(return_value=MagicMock()),
        "MarketOrderRequest": MagicMock(return_value=MagicMock()),
        "LimitOrderRequest": MagicMock(return_value=MagicMock()),
        "StopOrderRequest": MagicMock(return_value=MagicMock()),
        "StopLimitOrderRequest": MagicMock(return_value=MagicMock()),
        "GetOrderByIdRequest": MagicMock(return_value=MagicMock()),
        "OrderSide": MagicMock(BUY="buy", SELL="sell"),
        "TimeInForce": MagicMock(DAY="day", GTC="gtc", IOC="ioc", FOK="fok"),
        "OrderType": MagicMock(),
        "TimeFrame": MagicMock(Minute="1m", Hour="1h", Day="1d"),
        "TimeFrameUnit": MagicMock(Minute="Minute"),
    }
    svc._alpaca = alpaca_mock
    return svc


def _build_router() -> SandboxServiceRouter:
    router = SandboxServiceRouter(sandbox_id="integration-test")
    router.register_service(_make_alpaca())
    router.register_service(PaperBrokerService())
    router.register_service(_make_newsapi())
    router.register_service(_make_perplexity())
    return router


# ---------------------------------------------------------------------------
# Tests: service registration
# ---------------------------------------------------------------------------


def test_all_four_services_registered() -> None:
    router = _build_router()
    services = set(router.list_services())
    assert "alpaca" in services
    assert "paper" in services
    assert "newsapi" in services
    assert "perplexity" in services


# ---------------------------------------------------------------------------
# Tests: analyst policy — data sources only
# ---------------------------------------------------------------------------


def test_analyst_gets_data_tools_not_action_tools() -> None:
    router = _build_router()
    policy = AgentPolicy(
        name="analyst",
        allowed_services=(
            ServicePermission("alpaca", roles=frozenset({ServiceRole.DATA_SOURCE})),
            ServicePermission("newsapi"),
            ServicePermission("perplexity"),
        ),
    )
    pairs = router.wire_agent_tools("analyst-1", policy)
    names = {p[0]["function"]["name"] for p in pairs}

    # Should have alpaca data tools
    assert "alpaca_get_stock_bars" in names
    assert "alpaca_get_latest_quote" in names
    assert "alpaca_get_account" in names

    # Should NOT have alpaca action tools
    assert "alpaca_place_order" not in names
    assert "alpaca_cancel_order" not in names

    # Should have newsapi and perplexity data tools
    assert "newsapi_get_top_headlines" in names
    assert "perplexity_search" in names

    # Should NOT have paper broker tools (not in policy)
    assert "paper_get_price_history" not in names


# ---------------------------------------------------------------------------
# Tests: trader policy — data + action on paper broker
# ---------------------------------------------------------------------------


def test_trader_gets_paper_data_and_action_tools() -> None:
    router = _build_router()
    policy = AgentPolicy(
        name="trader",
        allowed_services=(
            ServicePermission("paper"),
            ServicePermission("newsapi"),
        ),
    )
    pairs = router.wire_agent_tools("trader-1", policy)
    names = {p[0]["function"]["name"] for p in pairs}

    assert "paper_get_price_history" in names
    assert "paper_place_order" in names
    assert "newsapi_get_top_headlines" in names

    # Alpaca and perplexity not in policy
    assert "alpaca_get_stock_bars" not in names
    assert "perplexity_search" not in names


# ---------------------------------------------------------------------------
# Tests: discover_tools catalogue respects policy
# ---------------------------------------------------------------------------


def test_discover_tools_catalogue_filters_by_policy() -> None:
    router = _build_router()
    policy = AgentPolicy(
        name="limited",
        allowed_services=(ServicePermission("newsapi"),),
    )
    _, discover = router.make_discovery_tool("agent-1", policy, inject_callback=lambda a, t: None)
    catalogue = json.loads(discover())
    names = {item["name"] for item in catalogue}

    assert "newsapi_get_top_headlines" in names
    assert "newsapi_search_articles" in names
    assert "alpaca_get_stock_bars" not in names
    assert "paper_get_price_history" not in names


# ---------------------------------------------------------------------------
# Tests: full policy (None) gets all tools
# ---------------------------------------------------------------------------


def test_admin_none_policy_gets_all_tools() -> None:
    router = _build_router()
    pairs = router.wire_agent_tools("admin", None)
    names = {p[0]["function"]["name"] for p in pairs}

    # All data tools present
    assert "alpaca_get_stock_bars" in names
    assert "paper_get_price_history" in names
    assert "newsapi_get_top_headlines" in names
    assert "perplexity_search" in names

    # All action tools present
    assert "alpaca_place_order" in names
    assert "paper_place_order" in names


# ---------------------------------------------------------------------------
# Tests: fetch_data routes to correct service
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_paper_price_history() -> None:
    from harvest.interfaces.service import DataQuery
    svc = PaperBrokerService()
    result = await svc.fetch(DataQuery(
        query_type="price_history",
        params={"symbol": "AAPL", "interval": "1d"},
        agent_id="a",
        request_id="r",
    ))
    assert result.error == ""
    assert len(result.payload["candles"]) > 0


@pytest.mark.asyncio
async def test_fetch_newsapi_top_headlines() -> None:
    from harvest.interfaces.service import DataQuery
    svc = _make_newsapi()
    result = await svc.fetch(DataQuery(
        query_type="top_headlines",
        params={"page_size": 5},
        agent_id="a",
        request_id="r",
    ))
    assert result.error == ""


@pytest.mark.asyncio
async def test_fetch_perplexity_search() -> None:
    from harvest.interfaces.service import DataQuery
    svc = _make_perplexity()
    result = await svc.fetch(DataQuery(
        query_type="search",
        params={"query": "test question"},
        agent_id="a",
        request_id="r",
    ))
    assert result.error == ""
    assert "answer" in result.payload


# ---------------------------------------------------------------------------
# Tests: execute_action routes to paper broker
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_paper_place_order() -> None:
    from harvest.interfaces.service import ActionCommand
    svc = PaperBrokerService()
    result = await svc.execute(ActionCommand(
        command_type="place_order",
        params={"symbol": "MSFT", "side": "buy", "qty": 5, "order_type": "market"},
        agent_id="a",
        request_id="r",
    ))
    assert result.error == ""
    assert result.payload["status"] == "filled"


# ---------------------------------------------------------------------------
# Tests: two agents with different policies
# ---------------------------------------------------------------------------


def test_two_agents_different_policies() -> None:
    router = _build_router()

    analyst_policy = AgentPolicy(
        name="analyst",
        allowed_services=(ServicePermission("newsapi"),),
    )
    trader_policy = AgentPolicy(
        name="trader",
        allowed_services=(ServicePermission("paper"),),
    )

    analyst_pairs = router.wire_agent_tools("analyst-1", analyst_policy)
    trader_pairs = router.wire_agent_tools("trader-1", trader_policy)

    analyst_names = {p[0]["function"]["name"] for p in analyst_pairs}
    trader_names = {p[0]["function"]["name"] for p in trader_pairs}

    assert "newsapi_get_top_headlines" in analyst_names
    assert "paper_place_order" not in analyst_names

    assert "paper_place_order" in trader_names
    assert "newsapi_get_top_headlines" not in trader_names


# ---------------------------------------------------------------------------
# Tests: discover_tools service_type field
# ---------------------------------------------------------------------------


def test_discover_tools_catalogue_service_type_correct() -> None:
    router = _build_router()
    policy = AgentPolicy(
        name="all",
        allowed_services=(
            ServicePermission("alpaca", roles=frozenset({ServiceRole.DATA_SOURCE, ServiceRole.ACTION})),
            ServicePermission("paper"),
            ServicePermission("newsapi"),
            ServicePermission("perplexity"),
        ),
    )
    _, discover = router.make_discovery_tool("agent-1", policy, inject_callback=lambda a, t: None)
    catalogue = json.loads(discover())

    by_name = {item["name"]: item for item in catalogue}

    # Alpaca data tools → data_source
    assert by_name["alpaca_get_stock_bars"]["service_type"] == "data_source"

    # Alpaca action tools → action
    assert by_name["alpaca_place_order"]["service_type"] == "action"

    # NewsAPI → data_source
    assert by_name["newsapi_get_top_headlines"]["service_type"] == "data_source"

    # Paper action → action
    assert by_name["paper_place_order"]["service_type"] == "action"
