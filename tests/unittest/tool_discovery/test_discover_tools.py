"""Tests for the discover_tools callable.

- No args → lightweight catalogue, no injection
- tool_name → full spec + injection
- Duplicate calls don't re-inject
- Unknown tool name → error
- Policy-denied tool → error
- ToolSpecsInjected event emitted only on activation
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


class _StockService(Service):
    def __init__(self, service_id: str = "stock-data") -> None:
        self._id = service_id

    @property
    def service_id(self) -> str:
        return self._id

    @property
    def roles(self) -> frozenset[ServiceRole]:
        return frozenset({ServiceRole.DATA_SOURCE})

    def get_capabilities(self) -> list[str]:
        return ["price"]

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
        return [
            InterfaceTool(
                name="get_stock_price",
                short_description="Get stock price.",
                full_description="Get the current market price for a stock symbol.",
                arguments=[ToolArgument(name="symbol", type="string", description="Ticker")],
                returns_description="JSON with price.",
                service_id=self._id,
                service_type="data_source",
                handler=lambda agent_id, symbol: json.dumps({"price": 42.0}),
            )
        ]


def _make_router_with_stock() -> SandboxServiceRouter:
    router = SandboxServiceRouter(sandbox_id="test")
    router.register_service(_StockService("stock-data"))
    return router


def _make_policy(sources=("stock-data",)):
    return AgentPolicy(
        name="test",
        allowed_services=tuple(ServicePermission(s) for s in sources),
    )


# ---------------------------------------------------------------------------
# Catalogue mode (no args)
# ---------------------------------------------------------------------------


def test_discover_tools_no_args_returns_lightweight_list() -> None:
    router = _make_router_with_stock()
    policy = _make_policy()
    injected: list = []

    _, discover = router.make_discovery_tool("agent-1", policy, inject_callback=lambda aid, tool: injected.append(tool))
    result = json.loads(discover())

    assert isinstance(result, list)
    assert len(result) == 1
    item = result[0]
    assert item["name"] == "get_stock_price"
    assert "short_description" in item
    assert "service_id" in item
    assert "service_type" in item
    assert "full_description" not in item
    assert "arguments" not in item


def test_discover_tools_no_args_does_not_inject() -> None:
    router = _make_router_with_stock()
    policy = _make_policy()
    injected: list = []

    _, discover = router.make_discovery_tool("agent-1", policy, inject_callback=lambda aid, tool: injected.append(tool))
    discover()

    assert injected == []


def test_discover_tools_no_args_respects_policy() -> None:
    router = _make_router_with_stock()
    policy = _make_policy(sources=())
    injected: list = []

    _, discover = router.make_discovery_tool("agent-1", policy, inject_callback=lambda aid, tool: injected.append(tool))
    result = json.loads(discover())

    assert result == []


# ---------------------------------------------------------------------------
# Activation mode (with tool_name)
# ---------------------------------------------------------------------------


def test_discover_tools_with_name_returns_full_spec() -> None:
    router = _make_router_with_stock()
    policy = _make_policy()
    _, discover = router.make_discovery_tool("agent-1", policy, inject_callback=lambda aid, tool: None)

    result = json.loads(discover(tool_name="get_stock_price"))
    assert result["name"] == "get_stock_price"
    assert "full_description" in result
    assert "arguments" in result
    assert "returns_description" in result
    assert "service_id" in result
    assert "service_type" in result


def test_discover_tools_with_name_calls_inject_callback() -> None:
    router = _make_router_with_stock()
    policy = _make_policy()
    injected: list = []

    _, discover = router.make_discovery_tool("agent-1", policy, inject_callback=lambda aid, tool: injected.append((aid, tool)))
    discover(tool_name="get_stock_price")

    assert len(injected) == 1
    assert injected[0][0] == "agent-1"
    assert injected[0][1].name == "get_stock_price"


def test_discover_tools_with_name_duplicate_does_not_reinject() -> None:
    router = _make_router_with_stock()
    policy = _make_policy()
    injected: list = []

    _, discover = router.make_discovery_tool("agent-1", policy, inject_callback=lambda aid, tool: injected.append(tool))
    discover(tool_name="get_stock_price")
    discover(tool_name="get_stock_price")

    assert len(injected) == 1


def test_discover_tools_unknown_name_returns_error() -> None:
    router = _make_router_with_stock()
    policy = _make_policy()
    _, discover = router.make_discovery_tool("agent-1", policy, inject_callback=lambda aid, tool: None)

    result = json.loads(discover(tool_name="nonexistent_tool"))
    assert "error" in result
    assert result["error"] == "unknown_tool"


def test_discover_tools_policy_denied_tool_returns_error() -> None:
    router = _make_router_with_stock()
    policy = _make_policy(sources=())

    _, discover = router.make_discovery_tool("agent-1", policy, inject_callback=lambda aid, tool: None)
    result = json.loads(discover(tool_name="get_stock_price"))
    assert "error" in result
    assert result["error"] == "unknown_tool"


def test_tool_specs_injected_event_emitted_on_activation() -> None:
    import asyncio
    from harvest.events.event_bus import EventBus
    from harvest.events.base import ToolSpecsInjected

    async def _run() -> list:
        bus = EventBus()
        emitted: list[ToolSpecsInjected] = []

        def _handler(event: ToolSpecsInjected) -> None:
            emitted.append(event)

        bus.on(ToolSpecsInjected, _handler)

        router = SandboxServiceRouter(sandbox_id="test", event_bus=bus)
        router.register_service(_StockService("stock-data"))

        policy = _make_policy()
        _, discover = router.make_discovery_tool("agent-1", policy, inject_callback=lambda aid, tool: None)
        discover(tool_name="get_stock_price")

        await asyncio.sleep(0.1)
        await bus.stop()
        return emitted

    emitted = asyncio.run(_run())
    assert len(emitted) == 1
    assert emitted[0].agent_id == "agent-1"
    assert "get_stock_price" in emitted[0].tool_names


def test_tool_specs_injected_event_not_emitted_on_catalogue() -> None:
    import asyncio
    from harvest.events.event_bus import EventBus
    from harvest.events.base import ToolSpecsInjected

    async def _run() -> list:
        bus = EventBus()
        emitted: list[ToolSpecsInjected] = []

        def _handler(event: ToolSpecsInjected) -> None:
            emitted.append(event)

        bus.on(ToolSpecsInjected, _handler)

        router = SandboxServiceRouter(sandbox_id="test", event_bus=bus)
        router.register_service(_StockService("stock-data"))

        policy = _make_policy()
        _, discover = router.make_discovery_tool("agent-1", policy, inject_callback=lambda aid, tool: None)
        discover()

        await asyncio.sleep(0.1)
        await bus.stop()
        return emitted

    emitted = asyncio.run(_run())
    assert emitted == []


def test_tool_specs_injected_event_not_emitted_on_duplicate_activation() -> None:
    import asyncio
    from harvest.events.event_bus import EventBus
    from harvest.events.base import ToolSpecsInjected

    async def _run() -> list:
        bus = EventBus()
        emitted: list[ToolSpecsInjected] = []

        def _handler(event: ToolSpecsInjected) -> None:
            emitted.append(event)

        bus.on(ToolSpecsInjected, _handler)

        router = SandboxServiceRouter(sandbox_id="test", event_bus=bus)
        router.register_service(_StockService("stock-data"))

        policy = _make_policy()
        _, discover = router.make_discovery_tool("agent-1", policy, inject_callback=lambda aid, tool: None)
        discover(tool_name="get_stock_price")
        discover(tool_name="get_stock_price")

        await asyncio.sleep(0.1)
        await bus.stop()
        return emitted

    emitted = asyncio.run(_run())
    assert len(emitted) == 1
