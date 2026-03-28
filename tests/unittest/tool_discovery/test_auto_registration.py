"""Tests for policy-driven auto-registration of interface tools.

At wire_agent_tools time, tools from permitted services are callable.
Tools from non-permitted services are not wired.
Empty policy gets no tools.
"""


import json
from typing import Any

import pytest

from harvest.agent_sandbox.service_router import SandboxServiceRouter
from harvest.interfaces.service import (
    ActionCommand,
    ActionResult,
    DataQuery,
    DataResult,
    Service,
    ServicePermission,
    ServiceRole,
)
from harvest.interfaces.tool_definition import InterfaceTool, ToolArgument
from harvest.core.policy import AgentPolicy


# ---------------------------------------------------------------------------
# Stub Service (DATA_SOURCE role)
# ---------------------------------------------------------------------------


class _StockDataService(Service):
    def __init__(self, service_id: str = "stock-data") -> None:
        self._id = service_id

    @property
    def service_id(self) -> str:
        return self._id

    @property
    def roles(self) -> frozenset[ServiceRole]:
        return frozenset({ServiceRole.DATA_SOURCE})

    def get_capabilities(self) -> list[str]:
        return ["price_lookup"]

    async def fetch(self, query: DataQuery) -> DataResult:
        return DataResult(request_id=query.request_id, source_id=self._id, payload={"price": 42.0})

    async def execute(self, command: ActionCommand) -> ActionResult:
        raise NotImplementedError

    async def start(self, event_bus: Any = None) -> None:
        pass

    async def stop(self) -> None:
        pass

    def health_check(self) -> dict[str, Any]:
        return {"status": "healthy"}

    def get_tools(self, role: ServiceRole | None = None) -> list[InterfaceTool]:
        if role is not None and role != ServiceRole.DATA_SOURCE:
            return []

        def _handler(agent_id: str, symbol: str) -> str:
            if hasattr(self, "_fetch_callback"):
                return self._fetch_callback(agent_id, self._id, "price", {"symbol": symbol})
            return json.dumps({"price": 99.0})

        return [
            InterfaceTool(
                name="get_stock_price",
                short_description="Get stock price.",
                full_description="Get the current price for a stock symbol.",
                arguments=[ToolArgument(name="symbol", type="string", description="Ticker")],
                returns_description="JSON with price.",
                service_id=self._id,
                service_type="data_source",
                handler=_handler,
            )
        ]


# ---------------------------------------------------------------------------
# Stub Service (ACTION role)
# ---------------------------------------------------------------------------


class _OrderService(Service):
    def __init__(self, service_id: str = "orders") -> None:
        self._id = service_id

    @property
    def service_id(self) -> str:
        return self._id

    @property
    def roles(self) -> frozenset[ServiceRole]:
        return frozenset({ServiceRole.ACTION})

    def get_capabilities(self) -> list[str]:
        return ["place_order"]

    async def fetch(self, query: DataQuery) -> DataResult:
        raise NotImplementedError

    async def execute(self, command: ActionCommand) -> ActionResult:
        return ActionResult(request_id=command.request_id, action_id=self._id, payload={"status": "ok"})

    async def start(self, event_bus: Any = None) -> None:
        pass

    async def stop(self) -> None:
        pass

    def health_check(self) -> dict[str, Any]:
        return {"status": "healthy"}

    def get_tools(self, role: ServiceRole | None = None) -> list[InterfaceTool]:
        if role is not None and role != ServiceRole.ACTION:
            return []

        def _handler(agent_id: str, symbol: str, quantity: int) -> str:
            if hasattr(self, "_execute_callback"):
                return self._execute_callback(
                    agent_id, self._id, "place_order",
                    {"symbol": symbol, "quantity": quantity}
                )
            return json.dumps({"order_id": "123"})

        return [
            InterfaceTool(
                name="place_market_order",
                short_description="Place a market order.",
                full_description="Place an immediate market order.",
                arguments=[
                    ToolArgument(name="symbol", type="string", description="Ticker"),
                    ToolArgument(name="quantity", type="integer", description="Shares"),
                ],
                returns_description="JSON with order_id.",
                service_id=self._id,
                service_type="action",
                handler=_handler,
            )
        ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_permitted_datasource_tools_are_wired() -> None:
    router = SandboxServiceRouter(sandbox_id="test")
    router.register_service(_StockDataService("stock-data"))

    policy = AgentPolicy(
        name="analyst",
        allowed_services=(ServicePermission("stock-data"),),
    )
    pairs = router.wire_agent_tools("agent-1", policy)
    names = [p[0]["function"]["name"] for p in pairs]
    assert "get_stock_price" in names


def test_non_permitted_datasource_tools_not_wired() -> None:
    router = SandboxServiceRouter(sandbox_id="test")
    router.register_service(_StockDataService("stock-data"))

    policy = AgentPolicy(
        name="restricted",
        allowed_services=(),
    )
    pairs = router.wire_agent_tools("agent-1", policy)
    names = [p[0]["function"]["name"] for p in pairs]
    assert "get_stock_price" not in names


def test_permitted_action_tools_are_wired() -> None:
    router = SandboxServiceRouter(sandbox_id="test")
    router.register_service(_OrderService("orders"))

    policy = AgentPolicy(
        name="trader",
        allowed_services=(ServicePermission("orders"),),
    )
    pairs = router.wire_agent_tools("agent-1", policy)
    names = [p[0]["function"]["name"] for p in pairs]
    assert "place_market_order" in names


def test_non_permitted_action_tools_not_wired() -> None:
    router = SandboxServiceRouter(sandbox_id="test")
    router.register_service(_OrderService("orders"))

    policy = AgentPolicy(
        name="read-only",
        allowed_services=(),
    )
    pairs = router.wire_agent_tools("agent-1", policy)
    names = [p[0]["function"]["name"] for p in pairs]
    assert "place_market_order" not in names


def test_empty_policy_gets_no_tools() -> None:
    router = SandboxServiceRouter(sandbox_id="test")
    router.register_service(_StockDataService("stock-data"))
    router.register_service(_OrderService("orders"))

    policy = AgentPolicy(
        name="empty",
        allowed_services=(),
    )
    pairs = router.wire_agent_tools("agent-1", policy)
    assert pairs == []


def test_admin_policy_none_gets_all_tools() -> None:
    router = SandboxServiceRouter(sandbox_id="test")
    router.register_service(_StockDataService("stock-data"))
    router.register_service(_OrderService("orders"))

    pairs = router.wire_agent_tools("agent-1", None)
    names = [p[0]["function"]["name"] for p in pairs]
    assert "get_stock_price" in names
    assert "place_market_order" in names


def test_wired_callable_injects_agent_id() -> None:
    """The wrapped callable injects agent_id so the handler can use it."""
    received_agent_ids: list[str] = []

    class _TrackingService(Service):
        @property
        def service_id(self) -> str:
            return "tracking"

        @property
        def roles(self) -> frozenset[ServiceRole]:
            return frozenset({ServiceRole.DATA_SOURCE})

        def get_capabilities(self) -> list[str]:
            return []

        async def fetch(self, query: DataQuery) -> DataResult:
            return DataResult(request_id=query.request_id, source_id=self.service_id, payload={})

        async def execute(self, command: ActionCommand) -> ActionResult:
            raise NotImplementedError

        async def start(self, event_bus: Any = None) -> None:
            pass

        async def stop(self) -> None:
            pass

        def health_check(self) -> dict[str, Any]:
            return {"status": "healthy"}

        def get_tools(self, role: ServiceRole | None = None) -> list[InterfaceTool]:
            if role is not None and role != ServiceRole.DATA_SOURCE:
                return []

            def _handler(agent_id: str, x: str) -> str:
                received_agent_ids.append(agent_id)
                return json.dumps({"x": x})

            return [
                InterfaceTool(
                    name="tracking_tool",
                    short_description="tracks agent_id",
                    full_description="tracks agent_id",
                    arguments=[ToolArgument(name="x", type="string", description="x")],
                    returns_description="x",
                    service_id="tracking",
                    service_type="data_source",
                    handler=_handler,
                )
            ]

    router = SandboxServiceRouter(sandbox_id="test")
    router.register_service(_TrackingService())

    policy = AgentPolicy(
        name="test-policy",
        allowed_services=(ServicePermission("tracking"),),
    )
    pairs = router.wire_agent_tools("my-agent-id", policy)
    assert len(pairs) == 1
    _, callable_ = pairs[0]
    callable_(x="hello")
    assert received_agent_ids == ["my-agent-id"]


def test_tools_auto_registered_event_emitted() -> None:
    """ToolsAutoRegistered is emitted when tools are wired."""
    import asyncio
    from harvest.events.event_bus import EventBus
    from harvest.events.base import ToolsAutoRegistered

    async def _run() -> list:
        bus = EventBus()
        emitted: list[ToolsAutoRegistered] = []

        def _handler(event: ToolsAutoRegistered) -> None:
            emitted.append(event)

        bus.on(ToolsAutoRegistered, _handler)

        router = SandboxServiceRouter(sandbox_id="test-sandbox", event_bus=bus)
        router.register_service(_StockDataService("stock-data"))

        policy = AgentPolicy(
            name="analyst",
            allowed_services=(ServicePermission("stock-data"),),
        )
        router.wire_agent_tools("agent-1", policy)

        await asyncio.sleep(0.1)
        await bus.stop()
        return emitted

    emitted = asyncio.run(_run())
    assert len(emitted) == 1
    assert emitted[0].agent_id == "agent-1"
    assert "get_stock_price" in emitted[0].tool_names
    assert emitted[0].sandbox_id == "test-sandbox"
