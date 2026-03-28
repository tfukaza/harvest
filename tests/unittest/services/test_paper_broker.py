"""Unit tests for PaperBrokerService — deterministic pricing and simulated orders."""


import json

import pytest

from harvest.services.paper_broker import PaperBrokerService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _svc(starting_cash: float = 100_000.0) -> PaperBrokerService:
    return PaperBrokerService(starting_cash=starting_cash)


# ---------------------------------------------------------------------------
# Tests: identity
# ---------------------------------------------------------------------------


def test_service_id() -> None:
    assert _svc().service_id == "paper"


def test_roles() -> None:
    from harvest.interfaces.service import ServiceRole
    roles = _svc().roles
    assert ServiceRole.DATA_SOURCE in roles
    assert ServiceRole.ACTION in roles
    assert ServiceRole.EVENT_SOURCE not in roles


def test_get_capabilities() -> None:
    caps = _svc().get_capabilities()
    assert "price_history" in caps
    assert "place_order" in caps


# ---------------------------------------------------------------------------
# Tests: tools
# ---------------------------------------------------------------------------


def test_get_tools_all() -> None:
    tools = _svc().get_tools()
    names = {t.name for t in tools}
    assert "paper_get_price_history" in names
    assert "paper_get_latest_price" in names
    assert "paper_get_account" in names
    assert "paper_get_positions" in names
    assert "paper_place_order" in names
    assert "paper_cancel_order" in names
    assert "paper_get_order" in names


def test_get_tools_data_source_role() -> None:
    from harvest.interfaces.service import ServiceRole
    tools = _svc().get_tools(role=ServiceRole.DATA_SOURCE)
    names = {t.name for t in tools}
    assert "paper_get_price_history" in names
    assert "paper_place_order" not in names


def test_get_tools_action_role() -> None:
    from harvest.interfaces.service import ServiceRole
    tools = _svc().get_tools(role=ServiceRole.ACTION)
    names = {t.name for t in tools}
    assert "paper_place_order" in names
    assert "paper_get_price_history" not in names


# ---------------------------------------------------------------------------
# Tests: price generation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_price_history_returns_candles() -> None:
    from harvest.interfaces.service import DataQuery
    svc = _svc()
    result = await svc.fetch(DataQuery(
        query_type="price_history",
        params={"symbol": "AAPL", "interval": "1d"},
        agent_id="agent-1",
        request_id="req-1",
    ))
    assert result.error == ""
    candles = result.payload["candles"]
    assert len(candles) > 0
    candle = candles[0]
    assert "open" in candle
    assert "high" in candle
    assert "low" in candle
    assert "close" in candle
    assert "volume" in candle


@pytest.mark.asyncio
async def test_price_history_deterministic() -> None:
    """Same symbol + interval always produces the same data."""
    from harvest.interfaces.service import DataQuery
    svc = _svc()

    q = DataQuery(
        query_type="price_history",
        params={"symbol": "MSFT", "interval": "1d"},
        agent_id="a",
        request_id="r",
    )
    r1 = await svc.fetch(q)
    r2 = await svc.fetch(q)

    assert r1.payload["candles"][0]["close"] == r2.payload["candles"][0]["close"]


@pytest.mark.asyncio
async def test_latest_price_returns_single_candle() -> None:
    from harvest.interfaces.service import DataQuery
    svc = _svc()
    result = await svc.fetch(DataQuery(
        query_type="latest_price",
        params={"symbol": "TSLA", "interval": "1m"},
        agent_id="a",
        request_id="r",
    ))
    assert result.error == ""
    p = result.payload
    assert p["symbol"] == "TSLA"
    assert "close" in p


@pytest.mark.asyncio
async def test_invalid_interval_returns_error() -> None:
    from harvest.interfaces.service import DataQuery
    svc = _svc()
    result = await svc.fetch(DataQuery(
        query_type="price_history",
        params={"symbol": "AAPL", "interval": "bad"},
        agent_id="a",
        request_id="r",
    ))
    assert result.error != ""
    assert "bad" in result.error or "interval" in result.error.lower()


# ---------------------------------------------------------------------------
# Tests: account
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_account_initial_state() -> None:
    from harvest.interfaces.service import DataQuery
    svc = _svc(starting_cash=50_000.0)
    result = await svc.fetch(DataQuery(
        query_type="account",
        params={},
        agent_id="a",
        request_id="r",
    ))
    assert result.error == ""
    assert result.payload["cash"] == 50_000.0
    assert result.payload["equity"] == 50_000.0


# ---------------------------------------------------------------------------
# Tests: positions (empty initially)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_positions_empty_initially() -> None:
    from harvest.interfaces.service import DataQuery
    svc = _svc()
    result = await svc.fetch(DataQuery(
        query_type="positions",
        params={},
        agent_id="a",
        request_id="r",
    ))
    assert result.error == ""
    assert result.payload["positions"] == []


# ---------------------------------------------------------------------------
# Tests: order execution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_market_buy_order_fills_immediately() -> None:
    from harvest.interfaces.service import ActionCommand
    svc = _svc()
    result = await svc.execute(ActionCommand(
        command_type="place_order",
        params={"symbol": "AAPL", "side": "buy", "qty": 10, "order_type": "market"},
        agent_id="a",
        request_id="r",
    ))
    assert result.error == ""
    assert result.payload["status"] == "filled"
    assert result.payload["symbol"] == "AAPL"
    assert result.payload["qty"] == 10
    assert result.payload["filled_price"] is not None


@pytest.mark.asyncio
async def test_market_buy_reduces_cash() -> None:
    from harvest.interfaces.service import ActionCommand, DataQuery
    svc = _svc(starting_cash=100_000.0)
    await svc.execute(ActionCommand(
        command_type="place_order",
        params={"symbol": "AAPL", "side": "buy", "qty": 10, "order_type": "market"},
        agent_id="a",
        request_id="r",
    ))
    result = await svc.fetch(DataQuery(
        query_type="account", params={}, agent_id="a", request_id="r2"
    ))
    assert result.payload["cash"] < 100_000.0


@pytest.mark.asyncio
async def test_market_buy_creates_position() -> None:
    from harvest.interfaces.service import ActionCommand, DataQuery
    svc = _svc()
    await svc.execute(ActionCommand(
        command_type="place_order",
        params={"symbol": "GOOG", "side": "buy", "qty": 5, "order_type": "market"},
        agent_id="a",
        request_id="r",
    ))
    result = await svc.fetch(DataQuery(
        query_type="positions", params={}, agent_id="a", request_id="r2"
    ))
    positions = result.payload["positions"]
    assert any(p["symbol"] == "GOOG" and p["qty"] == 5 for p in positions)


@pytest.mark.asyncio
async def test_market_sell_closes_position() -> None:
    from harvest.interfaces.service import ActionCommand, DataQuery
    svc = _svc()
    # Buy first
    await svc.execute(ActionCommand(
        command_type="place_order",
        params={"symbol": "MSFT", "side": "buy", "qty": 10, "order_type": "market"},
        agent_id="a",
        request_id="r1",
    ))
    # Sell
    await svc.execute(ActionCommand(
        command_type="place_order",
        params={"symbol": "MSFT", "side": "sell", "qty": 10, "order_type": "market"},
        agent_id="a",
        request_id="r2",
    ))
    result = await svc.fetch(DataQuery(
        query_type="positions", params={}, agent_id="a", request_id="r3"
    ))
    assert all(p["symbol"] != "MSFT" for p in result.payload["positions"])


@pytest.mark.asyncio
async def test_insufficient_funds_returns_error() -> None:
    from harvest.interfaces.service import ActionCommand
    svc = _svc(starting_cash=1.0)
    result = await svc.execute(ActionCommand(
        command_type="place_order",
        params={"symbol": "AAPL", "side": "buy", "qty": 10, "order_type": "market"},
        agent_id="a",
        request_id="r",
    ))
    assert result.error != ""
    assert "insufficient" in result.error.lower()


@pytest.mark.asyncio
async def test_sell_without_position_returns_error() -> None:
    from harvest.interfaces.service import ActionCommand
    svc = _svc()
    result = await svc.execute(ActionCommand(
        command_type="place_order",
        params={"symbol": "AAPL", "side": "sell", "qty": 5, "order_type": "market"},
        agent_id="a",
        request_id="r",
    ))
    assert result.error != ""
    assert "insufficient" in result.error.lower() or "position" in result.error.lower()


@pytest.mark.asyncio
async def test_limit_order_stays_pending() -> None:
    from harvest.interfaces.service import ActionCommand
    svc = _svc()
    result = await svc.execute(ActionCommand(
        command_type="place_order",
        params={"symbol": "AAPL", "side": "buy", "qty": 5, "order_type": "limit", "limit_price": 0.01},
        agent_id="a",
        request_id="r",
    ))
    assert result.error == ""
    assert result.payload["status"] == "pending"
    assert result.payload["order_type"] == "limit"


@pytest.mark.asyncio
async def test_cancel_pending_order() -> None:
    from harvest.interfaces.service import ActionCommand
    svc = _svc()
    place = await svc.execute(ActionCommand(
        command_type="place_order",
        params={"symbol": "AAPL", "side": "buy", "qty": 5, "order_type": "limit", "limit_price": 0.01},
        agent_id="a",
        request_id="r1",
    ))
    order_id = place.payload["order_id"]

    cancel = await svc.execute(ActionCommand(
        command_type="cancel_order",
        params={"order_id": order_id},
        agent_id="a",
        request_id="r2",
    ))
    assert cancel.error == ""
    assert cancel.payload["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_filled_order_returns_error() -> None:
    from harvest.interfaces.service import ActionCommand
    svc = _svc()
    place = await svc.execute(ActionCommand(
        command_type="place_order",
        params={"symbol": "AAPL", "side": "buy", "qty": 1, "order_type": "market"},
        agent_id="a",
        request_id="r1",
    ))
    order_id = place.payload["order_id"]

    cancel = await svc.execute(ActionCommand(
        command_type="cancel_order",
        params={"order_id": order_id},
        agent_id="a",
        request_id="r2",
    ))
    assert cancel.error != ""
    assert "filled" in cancel.error.lower()


@pytest.mark.asyncio
async def test_get_order_returns_status() -> None:
    from harvest.interfaces.service import ActionCommand
    svc = _svc()
    place = await svc.execute(ActionCommand(
        command_type="place_order",
        params={"symbol": "AAPL", "side": "buy", "qty": 1, "order_type": "market"},
        agent_id="a",
        request_id="r1",
    ))
    order_id = place.payload["order_id"]

    get = await svc.execute(ActionCommand(
        command_type="get_order",
        params={"order_id": order_id},
        agent_id="a",
        request_id="r2",
    ))
    assert get.error == ""
    assert get.payload["order_id"] == order_id
    assert get.payload["status"] == "filled"


@pytest.mark.asyncio
async def test_get_nonexistent_order_returns_error() -> None:
    from harvest.interfaces.service import ActionCommand
    svc = _svc()
    result = await svc.execute(ActionCommand(
        command_type="get_order",
        params={"order_id": "no-such-order"},
        agent_id="a",
        request_id="r",
    ))
    assert result.error != ""
    assert "not found" in result.error.lower()


# ---------------------------------------------------------------------------
# Tests: health check
# ---------------------------------------------------------------------------


def test_health_check() -> None:
    svc = _svc(starting_cash=50_000.0)
    hc = svc.health_check()
    assert hc["status"] == "healthy"
    assert hc["cash"] == 50_000.0
    assert hc["open_positions"] == 0
    assert hc["pending_orders"] == 0
