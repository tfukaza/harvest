"""PaperBrokerService — DATA_SOURCE + ACTION service for simulated trading.

Phase 16 concrete service implementation.
Generates synthetic market data via ``generate_ticker_frame`` and simulates
order execution against those prices. No network, no credentials.
"""

from __future__ import annotations

import datetime as dt
import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from harvest.enum import Interval
from harvest.interfaces.service import (
    ActionCommand,
    ActionResult,
    DataQuery,
    DataResult,
    Service,
    ServiceRole,
)
from harvest.interfaces.tool_definition import InterfaceTool, ToolArgument
from harvest.util.helper import generate_ticker_frame

# ---------------------------------------------------------------------------
# Internal data models
# ---------------------------------------------------------------------------

_INTERVAL_MAP: dict[str, Interval] = {
    "1m": Interval.MIN_1,
    "5m": Interval.MIN_5,
    "15m": Interval.MIN_15,
    "30m": Interval.MIN_30,
    "1h": Interval.HR_1,
    "1d": Interval.DAY_1,
}


@dataclass
class _Position:
    symbol: str
    qty: int
    avg_entry_price: float
    market_value: float = 0.0
    unrealized_pl: float = 0.0

    def update_market_value(self, current_price: float) -> None:
        self.market_value = self.qty * current_price
        self.unrealized_pl = (current_price - self.avg_entry_price) * self.qty


@dataclass
class _Order:
    order_id: str
    symbol: str
    side: str  # "buy" | "sell"
    qty: int
    order_type: str  # "market" | "limit"
    limit_price: float | None
    status: str  # "filled" | "pending" | "cancelled"
    filled_price: float | None = None
    filled_at: str | None = None
    submitted_at: str = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())


class PaperBrokerService(Service):
    """Simulated trading service with synthetic market data.

    DATA_SOURCE tools: price history, latest price, account, positions.
    ACTION tools: place order, cancel order, get order.

    Args:
        starting_cash: Initial cash balance (default $100,000).
        commission_fee: Per-trade flat fee in dollars (default $0).
        realistic_time: If True, honour real timestamps. Currently unused
            (placeholder for future time-simulation mode).
    """

    def __init__(
        self,
        starting_cash: float = 100_000.0,
        commission_fee: float = 0.0,
        realistic_time: bool = False,
    ) -> None:
        self._starting_cash = starting_cash
        self._cash = starting_cash
        self._commission_fee = commission_fee
        self._realistic_time = realistic_time
        self._positions: dict[str, _Position] = {}
        self._orders: dict[str, _Order] = {}

    # ------------------------------------------------------------------
    # Service identity
    # ------------------------------------------------------------------

    @property
    def service_id(self) -> str:
        return "paper"

    @property
    def roles(self) -> frozenset[ServiceRole]:
        return frozenset({ServiceRole.DATA_SOURCE, ServiceRole.ACTION})

    def get_capabilities(self) -> list[str]:
        return ["price_history", "latest_price", "account", "positions", "place_order", "cancel_order", "get_order"]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self, event_bus: Any = None) -> None:
        pass  # No external connections needed

    async def stop(self) -> None:
        pass

    def health_check(self) -> dict[str, Any]:
        return {
            "status": "healthy",
            "cash": self._cash,
            "equity": self._equity(),
            "open_positions": len(self._positions),
            "pending_orders": sum(1 for o in self._orders.values() if o.status == "pending"),
        }

    # ------------------------------------------------------------------
    # DATA_SOURCE: fetch
    # ------------------------------------------------------------------

    async def fetch(self, query: DataQuery) -> DataResult:
        return await self._dispatch_fetch(query, {
            "price_history": self._price_history,
            "latest_price": self._latest_price,
            "account": self._account_info,
            "positions": self._positions_info,
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
                self._price_history_tool(),
                self._latest_price_tool(),
                self._account_tool(),
                self._positions_tool(),
            ]
        if role is None or role == ServiceRole.ACTION:
            tools += [
                self._place_order_tool(),
                self._cancel_order_tool(),
                self._get_order_tool(),
            ]
        return tools

    # DATA_SOURCE tools ------------------------------------------------

    def _price_history_tool(self) -> InterfaceTool:
        def _handler(agent_id: str, symbol: str, interval: str, start: str = "", end: str = "") -> str:
            params: dict[str, Any] = {"symbol": symbol, "interval": interval}
            if start:
                params["start"] = start
            if end:
                params["end"] = end
            return self._fetch_callback(agent_id, self.service_id, "price_history", params)  # type: ignore[attr-defined]

        return InterfaceTool(
            name="paper_get_price_history",
            short_description="Get synthetic OHLCV price history.",
            full_description="Returns synthetic OHLCV candles for a symbol over a time range.",
            arguments=[
                ToolArgument(name="symbol", type="string", description="Ticker symbol e.g. 'AAPL'"),
                ToolArgument(name="interval", type="string", description="1m|5m|15m|30m|1h|1d"),
                ToolArgument(name="start", type="string", description="ISO datetime string (default 30 days ago)", required=False),
                ToolArgument(name="end", type="string", description="ISO datetime string (default now)", required=False),
            ],
            returns_description="JSON array of {timestamp, open, high, low, close, volume}",
            service_id=self.service_id,
            service_type="data_source",
            handler=_handler,
        )

    def _latest_price_tool(self) -> InterfaceTool:
        def _handler(agent_id: str, symbol: str, interval: str = "1m") -> str:
            return self._fetch_callback(agent_id, self.service_id, "latest_price", {"symbol": symbol, "interval": interval})  # type: ignore[attr-defined]

        return InterfaceTool(
            name="paper_get_latest_price",
            short_description="Get the most recent synthetic price candle.",
            full_description="Returns the most recent synthetic candle for a symbol.",
            arguments=[
                ToolArgument(name="symbol", type="string", description="Ticker symbol e.g. 'AAPL'"),
                ToolArgument(name="interval", type="string", description="Candle interval (default 1m)", required=False, default="1m"),
            ],
            returns_description="JSON object {symbol, timestamp, open, high, low, close, volume}",
            service_id=self.service_id,
            service_type="data_source",
            handler=_handler,
        )

    def _account_tool(self) -> InterfaceTool:
        def _handler(agent_id: str) -> str:
            return self._fetch_callback(agent_id, self.service_id, "account", {})  # type: ignore[attr-defined]

        return InterfaceTool(
            name="paper_get_account",
            short_description="Get paper trading account balances.",
            full_description="Returns the paper trading account balance and portfolio value.",
            arguments=[],
            returns_description="JSON object {equity, cash, buying_power, portfolio_value}",
            service_id=self.service_id,
            service_type="data_source",
            handler=_handler,
        )

    def _positions_tool(self) -> InterfaceTool:
        def _handler(agent_id: str) -> str:
            return self._fetch_callback(agent_id, self.service_id, "positions", {})  # type: ignore[attr-defined]

        return InterfaceTool(
            name="paper_get_positions",
            short_description="Get all current paper positions.",
            full_description="Returns all current open paper trading positions.",
            arguments=[],
            returns_description="JSON array of {symbol, qty, avg_entry_price, market_value, unrealized_pl}",
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
            qty: int,
            order_type: str = "market",
            limit_price: float = 0.0,
        ) -> str:
            params: dict[str, Any] = {
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "order_type": order_type,
            }
            if limit_price:
                params["limit_price"] = limit_price
            return self._execute_callback(agent_id, self.service_id, "place_order", params)  # type: ignore[attr-defined]

        return InterfaceTool(
            name="paper_place_order",
            short_description="Place a simulated paper trade order.",
            full_description="Place a simulated market or limit order. Market orders fill immediately.",
            arguments=[
                ToolArgument(name="symbol", type="string", description="Ticker symbol"),
                ToolArgument(name="side", type="string", description="buy|sell"),
                ToolArgument(name="qty", type="integer", description="Number of shares"),
                ToolArgument(name="order_type", type="string", description="market|limit (default market)", required=False, default="market"),
                ToolArgument(name="limit_price", type="float", description="Required for limit orders", required=False),
            ],
            returns_description="JSON object {order_id, status, symbol, side, qty, order_type, filled_price}",
            service_id=self.service_id,
            service_type="action",
            handler=_handler,
        )

    def _cancel_order_tool(self) -> InterfaceTool:
        def _handler(agent_id: str, order_id: str) -> str:
            return self._execute_callback(agent_id, self.service_id, "cancel_order", {"order_id": order_id})  # type: ignore[attr-defined]

        return InterfaceTool(
            name="paper_cancel_order",
            short_description="Cancel a pending paper limit order.",
            full_description="Cancel a pending limit order by order_id.",
            arguments=[
                ToolArgument(name="order_id", type="string", description="Order ID to cancel"),
            ],
            returns_description="JSON object {order_id, status: 'cancelled'} or error",
            service_id=self.service_id,
            service_type="action",
            handler=_handler,
        )

    def _get_order_tool(self) -> InterfaceTool:
        def _handler(agent_id: str, order_id: str) -> str:
            return self._execute_callback(agent_id, self.service_id, "get_order", {"order_id": order_id})  # type: ignore[attr-defined]

        return InterfaceTool(
            name="paper_get_order",
            short_description="Check status of a paper order.",
            full_description="Returns the current status of an order by ID.",
            arguments=[
                ToolArgument(name="order_id", type="string", description="Order ID to check"),
            ],
            returns_description="JSON object {order_id, status, symbol, side, qty, filled_price, filled_at}",
            service_id=self.service_id,
            service_type="action",
            handler=_handler,
        )

    # ------------------------------------------------------------------
    # Internal data methods
    # ------------------------------------------------------------------

    def _get_current_price(self, symbol: str, interval: str = "1m") -> float:
        iv = _INTERVAL_MAP.get(interval, Interval.MIN_1)
        candles = generate_ticker_frame(symbol, iv, count=1)
        row = candles.df.row(0, named=True)
        return float(row["close"])

    def _price_history(
        self,
        symbol: str,
        interval: str,
        start: str = "",
        end: str = "",
    ) -> dict:
        iv = _INTERVAL_MAP.get(interval)
        if iv is None:
            raise ValueError(f"Unknown interval '{interval}'. Valid values: {list(_INTERVAL_MAP)}")

        # Determine count from date range
        end_dt = dt.datetime.fromisoformat(end) if end else dt.datetime.now(dt.timezone.utc)
        start_dt = dt.datetime.fromisoformat(start) if start else end_dt - dt.timedelta(days=30)

        delta_minutes = (end_dt - start_dt).total_seconds() / 60
        interval_minutes = {
            "1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "1d": 1440,
        }.get(interval, 1)
        count = max(1, min(int(delta_minutes / interval_minutes), 1000))

        candles = generate_ticker_frame(symbol, iv, count=count, start=start_dt.replace(tzinfo=None))
        rows = []
        for row in candles.df.iter_rows(named=True):
            ts = row["timestamp"]
            rows.append({
                "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                "open": round(float(row["open"]), 4),
                "high": round(float(row["high"]), 4),
                "low": round(float(row["low"]), 4),
                "close": round(float(row["close"]), 4),
                "volume": int(row["volume"]),
            })
        return {"symbol": symbol, "interval": interval, "candles": rows}

    def _latest_price(self, symbol: str, interval: str = "1m") -> dict:
        iv = _INTERVAL_MAP.get(interval, Interval.MIN_1)
        candles = generate_ticker_frame(symbol, iv, count=1)
        row = candles.df.row(0, named=True)
        ts = row["timestamp"]
        return {
            "symbol": symbol,
            "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
            "open": round(float(row["open"]), 4),
            "high": round(float(row["high"]), 4),
            "low": round(float(row["low"]), 4),
            "close": round(float(row["close"]), 4),
            "volume": int(row["volume"]),
        }

    def _equity(self) -> float:
        total_market_value = sum(p.market_value for p in self._positions.values())
        return self._cash + total_market_value

    def _account_info(self) -> dict:
        equity = self._equity()
        return {
            "equity": round(equity, 2),
            "cash": round(self._cash, 2),
            "buying_power": round(self._cash, 2),
            "portfolio_value": round(equity, 2),
        }

    def _positions_info(self) -> dict:
        result = []
        for sym, pos in self._positions.items():
            current_price = self._get_current_price(sym)
            pos.update_market_value(current_price)
            result.append({
                "symbol": sym,
                "qty": pos.qty,
                "avg_entry_price": round(pos.avg_entry_price, 4),
                "market_value": round(pos.market_value, 2),
                "unrealized_pl": round(pos.unrealized_pl, 2),
            })
        return {"positions": result}

    def _place_order(
        self,
        symbol: str,
        side: str,
        qty: int,
        order_type: str = "market",
        limit_price: float = 0.0,
    ) -> dict:
        if side not in ("buy", "sell"):
            raise ValueError(f"Invalid side '{side}'. Must be 'buy' or 'sell'.")
        if qty <= 0:
            raise ValueError("qty must be a positive integer.")
        if order_type not in ("market", "limit"):
            raise ValueError(f"Invalid order_type '{order_type}'. Must be 'market' or 'limit'.")

        current_price = self._get_current_price(symbol)
        order_id = str(uuid.uuid4())
        now = dt.datetime.now(dt.timezone.utc).isoformat()

        if order_type == "market":
            fill_price = current_price
            cost = fill_price * qty + self._commission_fee
            if side == "buy":
                if self._cash < cost:
                    raise RuntimeError(
                        f"Insufficient funds: need ${cost:.2f}, have ${self._cash:.2f}"
                    )
                self._cash -= cost
                if symbol in self._positions:
                    pos = self._positions[symbol]
                    total_cost = pos.avg_entry_price * pos.qty + fill_price * qty
                    pos.qty += qty
                    pos.avg_entry_price = total_cost / pos.qty
                else:
                    self._positions[symbol] = _Position(
                        symbol=symbol,
                        qty=qty,
                        avg_entry_price=fill_price,
                    )
            else:  # sell
                pos = self._positions.get(symbol)
                if pos is None or pos.qty < qty:
                    held = pos.qty if pos else 0
                    raise RuntimeError(f"Insufficient position: need {qty} shares, hold {held}")
                self._cash += fill_price * qty - self._commission_fee
                pos.qty -= qty
                if pos.qty == 0:
                    del self._positions[symbol]

            order = _Order(
                order_id=order_id,
                symbol=symbol,
                side=side,
                qty=qty,
                order_type="market",
                limit_price=None,
                status="filled",
                filled_price=fill_price,
                filled_at=now,
                submitted_at=now,
            )
            self._orders[order_id] = order
            return {
                "order_id": order_id,
                "status": "filled",
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "order_type": "market",
                "filled_price": round(fill_price, 4),
            }
        else:  # limit
            if not limit_price:
                raise ValueError("limit_price is required for limit orders.")
            order = _Order(
                order_id=order_id,
                symbol=symbol,
                side=side,
                qty=qty,
                order_type="limit",
                limit_price=limit_price,
                status="pending",
                submitted_at=now,
            )
            self._orders[order_id] = order
            return {
                "order_id": order_id,
                "status": "pending",
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "order_type": "limit",
                "limit_price": limit_price,
            }

    def _cancel_order(self, order_id: str) -> dict:
        order = self._orders.get(order_id)
        if order is None:
            raise ValueError(f"Order '{order_id}' not found.")
        if order.status == "filled":
            raise RuntimeError(f"Cannot cancel order '{order_id}': already filled.")
        if order.status == "cancelled":
            raise RuntimeError(f"Order '{order_id}' is already cancelled.")
        order.status = "cancelled"
        return {"order_id": order_id, "status": "cancelled"}

    def _get_order(self, order_id: str) -> dict:
        order = self._orders.get(order_id)
        if order is None:
            raise ValueError(f"Order '{order_id}' not found.")
        return {
            "order_id": order.order_id,
            "status": order.status,
            "symbol": order.symbol,
            "side": order.side,
            "qty": order.qty,
            "filled_price": order.filled_price,
            "filled_at": order.filled_at,
        }
