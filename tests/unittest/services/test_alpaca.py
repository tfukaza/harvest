"""Unit tests for AlpacaService — mocks alpaca-py SDK clients."""


import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harvest.services.alpaca import AlpacaService


# ---------------------------------------------------------------------------
# Mock SDK factory
# ---------------------------------------------------------------------------


def _make_alpaca_mocks():
    """Build mock alpaca-py classes/instances."""

    class _MockBar:
        def __init__(self):
            self.symbol = "AAPL"
            self.timestamp = "2024-01-01T09:30:00Z"
            self.open = 180.0
            self.high = 182.0
            self.low = 179.0
            self.close = 181.0
            self.volume = 5000
            self.vwap = 180.5
            self.trade_count = 200

    class _MockQuote:
        def __init__(self):
            self.bid_price = 180.90
            self.bid_size = 100
            self.ask_price = 181.10
            self.ask_size = 150
            self.timestamp = "2024-01-01T09:30:00Z"

    class _MockAccount:
        equity = "100000.00"
        cash = "90000.00"
        buying_power = "90000.00"
        portfolio_value = "100000.00"
        currency = "USD"
        status = "ACTIVE"
        pattern_day_trader = False

    class _MockPosition:
        symbol = "AAPL"
        qty = "10"
        market_value = "1810.00"
        avg_entry_price = "175.00"
        unrealized_pl = "60.00"
        unrealized_plpc = "0.034"
        side = "long"

    class _MockOrder:
        id = "order-123"
        status = "filled"
        symbol = "AAPL"
        side = "buy"
        qty = "10"
        order_type = "market"
        submitted_at = "2024-01-01T09:30:00Z"
        filled_qty = "10"
        filled_avg_price = "181.00"
        filled_at = "2024-01-01T09:30:01Z"

    hist_client = MagicMock()
    trading_client = MagicMock()

    # Set up bar response
    bars_response = MagicMock()
    bars_response.get.return_value = [_MockBar()]
    hist_client.get_stock_bars.return_value = bars_response

    # Set up quote response
    quote_response = MagicMock()
    quote_response.get.return_value = _MockQuote()
    hist_client.get_stock_latest_quote.return_value = quote_response

    # Set up account
    trading_client.get_account.return_value = _MockAccount()

    # Set up positions
    trading_client.get_all_positions.return_value = [_MockPosition()]

    # Set up order submit
    trading_client.submit_order.return_value = _MockOrder()

    # Set up get order
    trading_client.get_order_by_id.return_value = _MockOrder()

    # cancel order returns None (no-op)
    trading_client.cancel_order_by_id.return_value = None

    return hist_client, trading_client


def _make_svc_with_mocks() -> AlpacaService:
    svc = AlpacaService(api_key="test-key", secret_key="test-secret", paper=True)
    hist, trading = _make_alpaca_mocks()
    svc._hist_client = hist
    svc._trading_client = trading

    # Import alpaca for TimeFrame etc. (mocked)
    from unittest.mock import MagicMock
    import sys

    # Build a minimal alpaca mock module so _parse_timeframe works
    alpaca_mock = {
        "StockHistoricalDataClient": MagicMock,
        "StockDataStream": MagicMock,
        "StockBarsRequest": MagicMock(return_value=MagicMock()),
        "StockLatestQuoteRequest": MagicMock(return_value=MagicMock()),
        "TradingClient": MagicMock,
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
    return svc, hist, trading


# ---------------------------------------------------------------------------
# Tests: identity
# ---------------------------------------------------------------------------


def test_service_id() -> None:
    svc = AlpacaService(api_key="k", secret_key="s")
    assert svc.service_id == "alpaca"


def test_roles() -> None:
    from harvest.interfaces.service import ServiceRole
    svc = AlpacaService(api_key="k", secret_key="s")
    assert ServiceRole.DATA_SOURCE in svc.roles
    assert ServiceRole.ACTION in svc.roles
    assert ServiceRole.EVENT_SOURCE in svc.roles


def test_get_capabilities() -> None:
    svc = AlpacaService(api_key="k", secret_key="s")
    caps = svc.get_capabilities()
    assert "stock_bars" in caps
    assert "place_order" in caps
    assert "bar_stream" in caps


# ---------------------------------------------------------------------------
# Tests: tools
# ---------------------------------------------------------------------------


def test_get_tools_all() -> None:
    svc = AlpacaService(api_key="k", secret_key="s")
    tools = svc.get_tools()
    names = {t.name for t in tools}
    assert "alpaca_get_stock_bars" in names
    assert "alpaca_get_latest_quote" in names
    assert "alpaca_get_account" in names
    assert "alpaca_get_positions" in names
    assert "alpaca_place_order" in names
    assert "alpaca_cancel_order" in names
    assert "alpaca_get_order" in names


def test_get_tools_data_source_only() -> None:
    from harvest.interfaces.service import ServiceRole
    svc = AlpacaService(api_key="k", secret_key="s")
    tools = svc.get_tools(role=ServiceRole.DATA_SOURCE)
    names = {t.name for t in tools}
    assert "alpaca_get_stock_bars" in names
    assert "alpaca_place_order" not in names


def test_get_tools_action_only() -> None:
    from harvest.interfaces.service import ServiceRole
    svc = AlpacaService(api_key="k", secret_key="s")
    tools = svc.get_tools(role=ServiceRole.ACTION)
    names = {t.name for t in tools}
    assert "alpaca_place_order" in names
    assert "alpaca_get_stock_bars" not in names


def test_get_tools_event_source_returns_empty() -> None:
    from harvest.interfaces.service import ServiceRole
    svc = AlpacaService(api_key="k", secret_key="s")
    tools = svc.get_tools(role=ServiceRole.EVENT_SOURCE)
    assert tools == []


# ---------------------------------------------------------------------------
# Tests: DATA_SOURCE fetch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_stock_bars() -> None:
    from harvest.interfaces.service import DataQuery
    svc, hist, _ = _make_svc_with_mocks()

    result = await svc.fetch(DataQuery(
        query_type="stock_bars",
        params={"symbol": "AAPL", "timeframe": "1d", "limit": 10},
        agent_id="a",
        request_id="r",
    ))

    assert result.error == ""
    assert result.payload["symbol"] == "AAPL"
    bars = result.payload["bars"]
    assert len(bars) == 1
    assert bars[0]["close"] == 181.0


@pytest.mark.asyncio
async def test_fetch_latest_quote() -> None:
    from harvest.interfaces.service import DataQuery
    svc, hist, _ = _make_svc_with_mocks()

    result = await svc.fetch(DataQuery(
        query_type="latest_quote",
        params={"symbol": "AAPL"},
        agent_id="a",
        request_id="r",
    ))

    assert result.error == ""
    assert result.payload["bid_price"] == 180.90
    assert result.payload["ask_price"] == 181.10


@pytest.mark.asyncio
async def test_fetch_account() -> None:
    from harvest.interfaces.service import DataQuery
    svc, _, _ = _make_svc_with_mocks()

    result = await svc.fetch(DataQuery(
        query_type="account",
        params={},
        agent_id="a",
        request_id="r",
    ))

    assert result.error == ""
    assert result.payload["equity"] == "100000.00"
    assert result.payload["currency"] == "USD"


@pytest.mark.asyncio
async def test_fetch_positions() -> None:
    from harvest.interfaces.service import DataQuery
    svc, _, _ = _make_svc_with_mocks()

    result = await svc.fetch(DataQuery(
        query_type="positions",
        params={},
        agent_id="a",
        request_id="r",
    ))

    assert result.error == ""
    positions = result.payload["positions"]
    assert len(positions) == 1
    assert positions[0]["symbol"] == "AAPL"


@pytest.mark.asyncio
async def test_fetch_unknown_query_type_returns_error() -> None:
    from harvest.interfaces.service import DataQuery
    svc, _, _ = _make_svc_with_mocks()

    result = await svc.fetch(DataQuery(
        query_type="unknown",
        params={},
        agent_id="a",
        request_id="r",
    ))

    assert result.error != ""


# ---------------------------------------------------------------------------
# Tests: ACTION execute
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_place_market_order() -> None:
    from harvest.interfaces.service import ActionCommand
    svc, _, trading = _make_svc_with_mocks()

    result = await svc.execute(ActionCommand(
        command_type="place_order",
        params={"symbol": "AAPL", "side": "buy", "qty": 10, "order_type": "market"},
        agent_id="a",
        request_id="r",
    ))

    assert result.error == ""
    assert result.payload["order_id"] == "order-123"
    assert trading.submit_order.called


@pytest.mark.asyncio
async def test_execute_cancel_order() -> None:
    from harvest.interfaces.service import ActionCommand
    svc, _, trading = _make_svc_with_mocks()

    result = await svc.execute(ActionCommand(
        command_type="cancel_order",
        params={"order_id": "order-123"},
        agent_id="a",
        request_id="r",
    ))

    assert result.error == ""
    assert result.payload["status"] == "cancelled"
    trading.cancel_order_by_id.assert_called_once_with("order-123")


@pytest.mark.asyncio
async def test_execute_get_order() -> None:
    from harvest.interfaces.service import ActionCommand
    svc, _, trading = _make_svc_with_mocks()

    result = await svc.execute(ActionCommand(
        command_type="get_order",
        params={"order_id": "order-123"},
        agent_id="a",
        request_id="r",
    ))

    assert result.error == ""
    assert result.payload["order_id"] == "order-123"
    assert result.payload["status"] == "filled"


@pytest.mark.asyncio
async def test_execute_unknown_command_returns_error() -> None:
    from harvest.interfaces.service import ActionCommand
    svc, _, _ = _make_svc_with_mocks()

    result = await svc.execute(ActionCommand(
        command_type="unknown_cmd",
        params={},
        agent_id="a",
        request_id="r",
    ))

    assert result.error != ""


# ---------------------------------------------------------------------------
# Tests: health check
# ---------------------------------------------------------------------------


def test_health_check_stopped() -> None:
    svc = AlpacaService(api_key="k", secret_key="s")
    assert svc.health_check()["status"] == "stopped"


def test_health_check_started() -> None:
    svc, _, _ = _make_svc_with_mocks()
    assert svc.health_check()["status"] == "healthy"
