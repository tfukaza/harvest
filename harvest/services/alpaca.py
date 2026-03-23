"""AlpacaService — DATA_SOURCE + EVENT_SOURCE + ACTION service for Alpaca Markets.

Phase 16 concrete service implementation.
Package: ``alpaca-py`` (NOT the deprecated ``alpaca_trade_api``).
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Any

from harvest.interfaces.service import (
    ActionCommand,
    ActionResult,
    DataQuery,
    DataResult,
    Service,
    ServiceRole,
)
from harvest.interfaces.tool_definition import InterfaceTool, ToolArgument

# ---------------------------------------------------------------------------
# Lazy alpaca-py imports — wrapped to give a helpful error if not installed
# ---------------------------------------------------------------------------


def _import_alpaca():
    try:
        from alpaca.data import StockHistoricalDataClient, StockDataStream
        from alpaca.data.requests import (
            StockBarsRequest,
            StockLatestQuoteRequest,
        )
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import (
            MarketOrderRequest,
            LimitOrderRequest,
            StopOrderRequest,
            StopLimitOrderRequest,
            GetOrderByIdRequest,
        )
        from alpaca.trading.enums import OrderSide, TimeInForce, OrderType
    except ImportError as exc:
        raise ImportError(
            "alpaca-py is required for AlpacaService. "
            "Install with: pip install alpaca-py"
        ) from exc
    return {
        "StockHistoricalDataClient": StockHistoricalDataClient,
        "StockDataStream": StockDataStream,
        "StockBarsRequest": StockBarsRequest,
        "StockLatestQuoteRequest": StockLatestQuoteRequest,
        "TimeFrame": TimeFrame,
        "TimeFrameUnit": TimeFrameUnit,
        "TradingClient": TradingClient,
        "MarketOrderRequest": MarketOrderRequest,
        "LimitOrderRequest": LimitOrderRequest,
        "StopOrderRequest": StopOrderRequest,
        "StopLimitOrderRequest": StopLimitOrderRequest,
        "GetOrderByIdRequest": GetOrderByIdRequest,
        "OrderSide": OrderSide,
        "TimeInForce": TimeInForce,
        "OrderType": OrderType,
    }


# ---------------------------------------------------------------------------
# Timeframe mapping helper
# ---------------------------------------------------------------------------


def _parse_timeframe(timeframe_str: str, alpaca: dict):
    TF = alpaca["TimeFrame"]
    TFU = alpaca["TimeFrameUnit"]
    mapping = {
        "1m": TF.Minute,
        "5m": alpaca["TimeFrame"].__class__(5, TFU.Minute) if hasattr(TF, "__class__") else None,
        "15m": None,
        "1h": TF.Hour,
        "1d": TF.Day,
    }
    # The TimeFrame class in alpaca-py is a bit unusual; construct explicitly.
    try:
        if timeframe_str == "1m":
            return TF.Minute
        elif timeframe_str == "5m":
            from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
            return TimeFrame(5, TimeFrameUnit.Minute)
        elif timeframe_str == "15m":
            from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
            return TimeFrame(15, TimeFrameUnit.Minute)
        elif timeframe_str == "1h":
            return TF.Hour
        elif timeframe_str == "1d":
            return TF.Day
        else:
            return None
    except Exception:
        return None


class AlpacaService(Service):
    """Alpaca brokerage API service covering all three roles.

    DATA_SOURCE: historical bars, latest quote, account info, positions.
    ACTION: place/cancel/get orders.
    EVENT_SOURCE: real-time bar updates and trade updates via StockDataStream.

    Args:
        api_key: Alpaca API key.
        secret_key: Alpaca secret key.
        paper: If True (default), routes to the paper trading endpoint.
        watchlist: Symbols to subscribe to for real-time bar streaming.
    """

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        paper: bool = True,
        watchlist: list[str] | None = None,
    ) -> None:
        self._api_key = api_key
        self._secret_key = secret_key
        self._paper = paper
        self._watchlist = watchlist or []
        self._event_bus: Any = None
        self._hist_client: Any = None
        self._trading_client: Any = None
        self._stream: Any = None
        self._stream_thread: threading.Thread | None = None
        self._alpaca: dict | None = None

    # ------------------------------------------------------------------
    # Service identity
    # ------------------------------------------------------------------

    @property
    def service_id(self) -> str:
        return "alpaca"

    @property
    def roles(self) -> frozenset[ServiceRole]:
        return frozenset({ServiceRole.DATA_SOURCE, ServiceRole.EVENT_SOURCE, ServiceRole.ACTION})

    def get_capabilities(self) -> list[str]:
        return [
            "stock_bars", "latest_quote", "account", "positions",
            "place_order", "cancel_order", "get_order",
            "bar_stream", "trade_updates",
        ]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self, event_bus: Any = None) -> None:
        self._event_bus = event_bus
        a = _import_alpaca()
        self._alpaca = a

        self._hist_client = a["StockHistoricalDataClient"](
            api_key=self._api_key,
            secret_key=self._secret_key,
        )
        self._trading_client = a["TradingClient"](
            api_key=self._api_key,
            secret_key=self._secret_key,
            paper=self._paper,
        )
        # Validate credentials
        self._trading_client.get_account()

        # Start stream if watchlist is configured and event bus is available
        if self._watchlist and event_bus:
            self._start_stream()

    async def stop(self) -> None:
        if self._stream:
            try:
                self._stream.stop()
            except Exception:
                pass
            self._stream = None
        if self._stream_thread and self._stream_thread.is_alive():
            self._stream_thread.join(timeout=5)
            self._stream_thread = None

    def health_check(self) -> dict[str, Any]:
        status = "healthy" if self._trading_client else "stopped"
        return {"status": status, "paper": self._paper}

    # ------------------------------------------------------------------
    # Stream management (EVENT_SOURCE)
    # ------------------------------------------------------------------

    def _start_stream(self) -> None:
        if not self._alpaca:
            return
        a = self._alpaca
        stream = a["StockDataStream"](
            api_key=self._api_key,
            secret_key=self._secret_key,
        )

        async def _on_bar(bar) -> None:
            if self._event_bus:
                from harvest.events.base import ExternalEventFired
                self._event_bus.dispatch(ExternalEventFired(
                    source_id=self.service_id,
                    event_type="bar_update",
                    payload={
                        "symbol": bar.symbol,
                        "open": float(bar.open),
                        "high": float(bar.high),
                        "low": float(bar.low),
                        "close": float(bar.close),
                        "volume": int(bar.volume),
                        "timestamp": str(bar.timestamp),
                    },
                ))

        async def _on_trade_update(update) -> None:
            if self._event_bus:
                from harvest.events.base import ExternalEventFired
                order = update.order
                self._event_bus.dispatch(ExternalEventFired(
                    source_id=self.service_id,
                    event_type="trade_update",
                    payload={
                        "order_id": str(order.id),
                        "event": update.event,
                        "symbol": order.symbol,
                        "qty": str(order.qty),
                        "price": str(getattr(order, "filled_avg_price", "") or ""),
                        "timestamp": str(update.timestamp),
                    },
                ))

        stream.subscribe_bars(_on_bar, *self._watchlist)
        stream.subscribe_trade_updates(_on_trade_update)
        self._stream = stream

        def _run():
            stream.run()

        self._stream_thread = threading.Thread(target=_run, daemon=True)
        self._stream_thread.start()

    # ------------------------------------------------------------------
    # DATA_SOURCE: fetch
    # ------------------------------------------------------------------

    async def fetch(self, query: DataQuery) -> DataResult:
        return await self._dispatch_fetch(query, {
            "stock_bars": self._get_stock_bars,
            "latest_quote": self._get_latest_quote,
            "account": self._get_account,
            "positions": self._get_positions,
        })

    # ------------------------------------------------------------------
    # ACTION: execute
    # ------------------------------------------------------------------

    async def execute(self, command: ActionCommand) -> ActionResult:
        return await self._dispatch_execute(command, {
            "place_order": self._place_order,
            "cancel_order": self._cancel_order,
            "get_order": self._get_order,
        })

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    def get_tools(self, role: ServiceRole | None = None) -> list[InterfaceTool]:
        tools = []
        if role is None or role == ServiceRole.DATA_SOURCE:
            tools += [
                self._bars_tool(),
                self._quote_tool(),
                self._account_tool(),
                self._positions_tool(),
            ]
        if role is None or role == ServiceRole.ACTION:
            tools += [
                self._place_order_tool(),
                self._cancel_order_tool(),
                self._get_order_tool(),
            ]
        # EVENT_SOURCE returns no tools (inbox model)
        return tools

    # DATA_SOURCE tools ------------------------------------------------

    def _bars_tool(self) -> InterfaceTool:
        def _handler(
            agent_id: str,
            symbol: str,
            timeframe: str,
            start: str = "",
            end: str = "",
            limit: int = 100,
        ) -> str:
            params: dict[str, Any] = {"symbol": symbol, "timeframe": timeframe, "limit": limit}
            if start:
                params["start"] = start
            if end:
                params["end"] = end
            return self._fetch_callback(agent_id, self.service_id, "stock_bars", params)  # type: ignore[attr-defined]

        return InterfaceTool(
            name="alpaca_get_stock_bars",
            short_description="Get historical OHLCV bars for a stock.",
            full_description="Fetch historical OHLCV bars for a stock symbol from Alpaca.",
            arguments=[
                ToolArgument(name="symbol", type="string", description="Ticker e.g. 'AAPL'"),
                ToolArgument(name="timeframe", type="string", description="1m|5m|15m|1h|1d"),
                ToolArgument(name="start", type="string", description="ISO date/datetime string", required=False),
                ToolArgument(name="end", type="string", description="ISO date/datetime string", required=False),
                ToolArgument(name="limit", type="integer", description="Max bars to return (default 100)", required=False, default=100),
            ],
            returns_description="JSON array of {timestamp, open, high, low, close, volume, vwap, trade_count}",
            service_id=self.service_id,
            service_type="data_source",
            handler=_handler,
        )

    def _quote_tool(self) -> InterfaceTool:
        def _handler(agent_id: str, symbol: str) -> str:
            return self._fetch_callback(agent_id, self.service_id, "latest_quote", {"symbol": symbol})  # type: ignore[attr-defined]

        return InterfaceTool(
            name="alpaca_get_latest_quote",
            short_description="Get latest bid/ask quote for a stock.",
            full_description="Returns the latest bid/ask snapshot for a stock from Alpaca.",
            arguments=[
                ToolArgument(name="symbol", type="string", description="Ticker e.g. 'AAPL'"),
            ],
            returns_description="JSON object {symbol, bid_price, bid_size, ask_price, ask_size, timestamp}",
            service_id=self.service_id,
            service_type="data_source",
            handler=_handler,
        )

    def _account_tool(self) -> InterfaceTool:
        def _handler(agent_id: str) -> str:
            return self._fetch_callback(agent_id, self.service_id, "account", {})  # type: ignore[attr-defined]

        return InterfaceTool(
            name="alpaca_get_account",
            short_description="Get Alpaca account balances and status.",
            full_description="Returns account equity, cash, buying power, and status.",
            arguments=[],
            returns_description="JSON object {equity, cash, buying_power, portfolio_value, currency, status, pattern_day_trader}",
            service_id=self.service_id,
            service_type="data_source",
            handler=_handler,
        )

    def _positions_tool(self) -> InterfaceTool:
        def _handler(agent_id: str) -> str:
            return self._fetch_callback(agent_id, self.service_id, "positions", {})  # type: ignore[attr-defined]

        return InterfaceTool(
            name="alpaca_get_positions",
            short_description="Get all current Alpaca positions.",
            full_description="Returns all currently open positions from Alpaca.",
            arguments=[],
            returns_description="JSON array of {symbol, qty, market_value, avg_entry_price, unrealized_pl, unrealized_plpc, side}",
            service_id=self.service_id,
            service_type="data_source",
            handler=_handler,
        )

    # ACTION tools -----------------------------------------------------

    def _place_order_tool(self) -> InterfaceTool:
        def _handler(
            agent_id: str,
            symbol: str,
            side: str,
            qty: float,
            order_type: str = "market",
            limit_price: float = 0.0,
            stop_price: float = 0.0,
            time_in_force: str = "day",
        ) -> str:
            params: dict[str, Any] = {
                "symbol": symbol, "side": side, "qty": qty,
                "order_type": order_type, "time_in_force": time_in_force,
            }
            if limit_price:
                params["limit_price"] = limit_price
            if stop_price:
                params["stop_price"] = stop_price
            return self._execute_callback(agent_id, self.service_id, "place_order", params)  # type: ignore[attr-defined]

        return InterfaceTool(
            name="alpaca_place_order",
            short_description="Place a stock order on Alpaca.",
            full_description="Place a market, limit, stop, or stop-limit order on Alpaca.",
            arguments=[
                ToolArgument(name="symbol", type="string", description="Ticker e.g. 'AAPL'"),
                ToolArgument(name="side", type="string", description="buy|sell"),
                ToolArgument(name="qty", type="float", description="Number of shares (fractional allowed)"),
                ToolArgument(name="order_type", type="string", description="market|limit|stop|stop_limit (default market)", required=False, default="market"),
                ToolArgument(name="limit_price", type="float", description="Required for limit and stop_limit orders", required=False),
                ToolArgument(name="stop_price", type="float", description="Required for stop and stop_limit orders", required=False),
                ToolArgument(name="time_in_force", type="string", description="day|gtc|ioc|fok (default day)", required=False, default="day"),
            ],
            returns_description="JSON object {order_id, status, symbol, side, qty, order_type, submitted_at}",
            service_id=self.service_id,
            service_type="action",
            handler=_handler,
        )

    def _cancel_order_tool(self) -> InterfaceTool:
        def _handler(agent_id: str, order_id: str) -> str:
            return self._execute_callback(agent_id, self.service_id, "cancel_order", {"order_id": order_id})  # type: ignore[attr-defined]

        return InterfaceTool(
            name="alpaca_cancel_order",
            short_description="Cancel an open Alpaca order.",
            full_description="Cancel an open order by order_id.",
            arguments=[
                ToolArgument(name="order_id", type="string", description="Order ID to cancel"),
            ],
            returns_description="JSON object {order_id, status: 'cancelled'}",
            service_id=self.service_id,
            service_type="action",
            handler=_handler,
        )

    def _get_order_tool(self) -> InterfaceTool:
        def _handler(agent_id: str, order_id: str) -> str:
            return self._execute_callback(agent_id, self.service_id, "get_order", {"order_id": order_id})  # type: ignore[attr-defined]

        return InterfaceTool(
            name="alpaca_get_order",
            short_description="Check status of an Alpaca order.",
            full_description="Returns the current status of an order by ID.",
            arguments=[
                ToolArgument(name="order_id", type="string", description="Order ID to check"),
            ],
            returns_description="JSON object {order_id, status, symbol, side, qty, filled_qty, filled_avg_price, submitted_at, filled_at}",
            service_id=self.service_id,
            service_type="action",
            handler=_handler,
        )

    # ------------------------------------------------------------------
    # Internal SDK calls
    # ------------------------------------------------------------------

    def _get_stock_bars(
        self,
        symbol: str,
        timeframe: str,
        start: str = "",
        end: str = "",
        limit: int = 100,
    ) -> dict:
        a = self._alpaca
        if not a:
            raise RuntimeError("Service not started")
        tf = _parse_timeframe(timeframe, a)
        if tf is None:
            return {"error": f"Invalid timeframe '{timeframe}'", "code": "invalid_timeframe"}

        req_kwargs: dict[str, Any] = {
            "symbol_or_symbols": symbol,
            "timeframe": tf,
            "limit": limit,
        }
        if start:
            req_kwargs["start"] = start
        if end:
            req_kwargs["end"] = end

        req = a["StockBarsRequest"](**req_kwargs)
        bars_resp = self._hist_client.get_stock_bars(req)
        bars = bars_resp.get(symbol, []) if hasattr(bars_resp, "get") else []
        result = []
        for bar in bars:
            result.append({
                "timestamp": str(bar.timestamp),
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": float(bar.close),
                "volume": int(bar.volume),
                "vwap": float(bar.vwap) if bar.vwap else None,
                "trade_count": int(bar.trade_count) if bar.trade_count else None,
            })
        return {"symbol": symbol, "bars": result}

    def _get_latest_quote(self, symbol: str) -> dict:
        a = self._alpaca
        if not a:
            raise RuntimeError("Service not started")
        req = a["StockLatestQuoteRequest"](symbol_or_symbols=symbol)
        resp = self._hist_client.get_stock_latest_quote(req)
        quote = resp.get(symbol) if hasattr(resp, "get") else None
        if quote is None:
            return {"error": f"No quote for {symbol}", "code": "no_data"}
        return {
            "symbol": symbol,
            "bid_price": float(quote.bid_price) if quote.bid_price else None,
            "bid_size": int(quote.bid_size) if quote.bid_size else None,
            "ask_price": float(quote.ask_price) if quote.ask_price else None,
            "ask_size": int(quote.ask_size) if quote.ask_size else None,
            "timestamp": str(quote.timestamp),
        }

    def _get_account(self) -> dict:
        if not self._trading_client:
            raise RuntimeError("Service not started")
        acct = self._trading_client.get_account()
        return {
            "equity": str(acct.equity),
            "cash": str(acct.cash),
            "buying_power": str(acct.buying_power),
            "portfolio_value": str(acct.portfolio_value),
            "currency": acct.currency,
            "status": str(acct.status),
            "pattern_day_trader": acct.pattern_day_trader,
        }

    def _get_positions(self) -> dict:
        if not self._trading_client:
            raise RuntimeError("Service not started")
        positions = self._trading_client.get_all_positions()
        result = []
        for pos in positions:
            result.append({
                "symbol": pos.symbol,
                "qty": str(pos.qty),
                "market_value": str(pos.market_value),
                "avg_entry_price": str(pos.avg_entry_price),
                "unrealized_pl": str(pos.unrealized_pl),
                "unrealized_plpc": str(pos.unrealized_plpc),
                "side": str(pos.side),
            })
        return {"positions": result}

    def _place_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        order_type: str = "market",
        limit_price: float = 0.0,
        stop_price: float = 0.0,
        time_in_force: str = "day",
    ) -> dict:
        a = self._alpaca
        if not a:
            raise RuntimeError("Service not started")
        OrderSide = a["OrderSide"]
        TimeInForce = a["TimeInForce"]

        alpaca_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        alpaca_tif_map = {
            "day": TimeInForce.DAY,
            "gtc": TimeInForce.GTC,
            "ioc": TimeInForce.IOC,
            "fok": TimeInForce.FOK,
        }
        alpaca_tif = alpaca_tif_map.get(time_in_force.lower(), TimeInForce.DAY)

        if order_type == "market":
            req = a["MarketOrderRequest"](
                symbol=symbol, qty=qty, side=alpaca_side, time_in_force=alpaca_tif
            )
        elif order_type == "limit":
            req = a["LimitOrderRequest"](
                symbol=symbol, qty=qty, side=alpaca_side,
                time_in_force=alpaca_tif, limit_price=limit_price
            )
        elif order_type == "stop":
            req = a["StopOrderRequest"](
                symbol=symbol, qty=qty, side=alpaca_side,
                time_in_force=alpaca_tif, stop_price=stop_price
            )
        elif order_type == "stop_limit":
            req = a["StopLimitOrderRequest"](
                symbol=symbol, qty=qty, side=alpaca_side,
                time_in_force=alpaca_tif, limit_price=limit_price, stop_price=stop_price
            )
        else:
            return {"error": f"Invalid order_type '{order_type}'", "code": "invalid_order_type"}

        order = self._trading_client.submit_order(req)
        return {
            "order_id": str(order.id),
            "status": str(order.status),
            "symbol": order.symbol,
            "side": str(order.side),
            "qty": str(order.qty),
            "order_type": str(order.order_type),
            "submitted_at": str(order.submitted_at),
        }

    def _cancel_order(self, order_id: str) -> dict:
        if not self._trading_client:
            raise RuntimeError("Service not started")
        self._trading_client.cancel_order_by_id(order_id)
        return {"order_id": order_id, "status": "cancelled"}

    def _get_order(self, order_id: str) -> dict:
        if not self._trading_client:
            raise RuntimeError("Service not started")
        order = self._trading_client.get_order_by_id(order_id)
        return {
            "order_id": str(order.id),
            "status": str(order.status),
            "symbol": order.symbol,
            "side": str(order.side),
            "qty": str(order.qty),
            "filled_qty": str(order.filled_qty),
            "filled_avg_price": str(order.filled_avg_price),
            "submitted_at": str(order.submitted_at),
            "filled_at": str(order.filled_at),
        }


# ---------------------------------------------------------------------------
