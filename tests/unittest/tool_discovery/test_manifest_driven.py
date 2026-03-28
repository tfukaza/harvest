"""Integration tests: manifest-driven tool wiring and discovery.

Tests that:
- Agents receive correct callable tool sets at startup
- Correct specs injected after discover_tools(name)
- Correct event notification on event delivery
- Different agents with different policies get different tools
"""


import json
from typing import Any

import pytest

from harvest.agent_sandbox.service_router import SandboxServiceRouter
from harvest.agent_sandbox.system_prompt_builder import SystemPromptBuilder
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
# Stub services
# ---------------------------------------------------------------------------


class _MarketDataService(Service):
    @property
    def service_id(self) -> str:
        return "market-data"

    @property
    def roles(self) -> frozenset[ServiceRole]:
        return frozenset({ServiceRole.DATA_SOURCE})

    def get_capabilities(self) -> list[str]:
        return ["price"]

    async def fetch(self, query: DataQuery) -> DataResult:
        return DataResult(
            request_id=query.request_id,
            source_id=self.service_id,
            payload={"price": 100.0},
        )

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
                return self._fetch_callback(agent_id, self.service_id, "price", {"symbol": symbol})
            return json.dumps({"price": 100.0})

        return [
            InterfaceTool(
                name="get_market_price",
                short_description="Get market price.",
                full_description="Get the current market price for a symbol.",
                arguments=[ToolArgument(name="symbol", type="string", description="Symbol")],
                returns_description="JSON with price.",
                service_id=self.service_id,
                service_type="data_source",
                handler=_handler,
            )
        ]


class _OrdersService(Service):
    @property
    def service_id(self) -> str:
        return "order-execution"

    @property
    def roles(self) -> frozenset[ServiceRole]:
        return frozenset({ServiceRole.ACTION})

    def get_capabilities(self) -> list[str]:
        return ["place_order"]

    async def fetch(self, query: DataQuery) -> DataResult:
        raise NotImplementedError

    async def execute(self, command: ActionCommand) -> ActionResult:
        return ActionResult(
            request_id=command.request_id,
            action_id=self.service_id,
            payload={"order_id": "ord-123", "status": "filled"},
        )

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
                    agent_id, self.service_id, "place_order",
                    {"symbol": symbol, "quantity": quantity}
                )
            return json.dumps({"order_id": "ord-123"})

        return [
            InterfaceTool(
                name="place_market_order_v2",
                short_description="Place a market order.",
                full_description="Place an immediate market order.",
                arguments=[
                    ToolArgument(name="symbol", type="string", description="Symbol"),
                    ToolArgument(name="quantity", type="integer", description="Shares"),
                ],
                returns_description="JSON with order_id.",
                service_id=self.service_id,
                service_type="action",
                handler=_handler,
            )
        ]


class _AlertsService(Service):
    def __init__(self) -> None:
        self._bus = None

    @property
    def service_id(self) -> str:
        return "price-alerts"

    @property
    def roles(self) -> frozenset[ServiceRole]:
        return frozenset({ServiceRole.EVENT_SOURCE})

    def get_capabilities(self) -> list[str]:
        return ["alerts"]

    async def fetch(self, query: DataQuery) -> DataResult:
        raise NotImplementedError

    async def execute(self, command: ActionCommand) -> ActionResult:
        raise NotImplementedError

    async def start(self, event_bus: Any = None) -> None:
        self._bus = event_bus

    async def stop(self) -> None:
        self._bus = None

    def health_check(self) -> dict[str, Any]:
        return {"status": "healthy"}

    def get_tools(self, role: ServiceRole | None = None) -> list[InterfaceTool]:
        return []


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def _build_router() -> SandboxServiceRouter:
    router = SandboxServiceRouter(sandbox_id="test-sandbox")
    router.register_service(_MarketDataService())
    router.register_service(_OrdersService())
    router.register_service(_AlertsService())
    return router


def test_analyst_gets_datasource_tools_not_action_tools() -> None:
    """Analyst policy: allowed data sources but no actions."""
    router = _build_router()

    analyst_policy = AgentPolicy(
        name="analyst",
        allowed_services=(ServicePermission("market-data"),),
    )
    pairs = router.wire_agent_tools("analyst-1", analyst_policy)
    names = {p[0]["function"]["name"] for p in pairs}

    assert "get_market_price" in names
    assert "place_market_order_v2" not in names


def test_trader_gets_both_datasource_and_action_tools() -> None:
    """Trader policy: allowed data sources and actions."""
    router = _build_router()

    trader_policy = AgentPolicy(
        name="trader",
        allowed_services=(
            ServicePermission("market-data"),
            ServicePermission("order-execution"),
        ),
    )
    pairs = router.wire_agent_tools("trader-1", trader_policy)
    names = {p[0]["function"]["name"] for p in pairs}

    assert "get_market_price" in names
    assert "place_market_order_v2" in names


def test_discover_tools_respects_analyst_policy() -> None:
    """discover_tools() only lists tools the analyst is permitted to use."""
    router = _build_router()

    analyst_policy = AgentPolicy(
        name="analyst",
        allowed_services=(ServicePermission("market-data"),),
    )
    _, discover = router.make_discovery_tool("analyst-1", analyst_policy, inject_callback=lambda aid, t: None)
    catalogue = json.loads(discover())
    names = {item["name"] for item in catalogue}

    assert "get_market_price" in names
    assert "place_market_order_v2" not in names


def test_discover_tools_activation_injects_correct_spec() -> None:
    """discover_tools(name) injects the full spec via the callback."""
    router = _build_router()
    injected: list[tuple] = []

    analyst_policy = AgentPolicy(
        name="analyst",
        allowed_services=(ServicePermission("market-data"),),
    )
    _, discover = router.make_discovery_tool(
        "analyst-1", analyst_policy,
        inject_callback=lambda aid, tool: injected.append((aid, tool))
    )
    result = json.loads(discover(tool_name="get_market_price"))

    assert result["name"] == "get_market_price"
    assert len(injected) == 1
    assert injected[0][0] == "analyst-1"
    assert injected[0][1].name == "get_market_price"


def test_event_notification_injected_on_delivery() -> None:
    """When an event is delivered, the notification appears in the system prompt."""
    builder = SystemPromptBuilder()

    def _add_notification(aid: str, src_id: str, evt_type: str) -> None:
        block = (
            f"## Pending Event Notification\n\n"
            f"A new event has arrived from source '{src_id}' "
            f"(type: '{evt_type}'). Call read_event_notifications() to read it."
        )
        builder.append("event_notifications", block)

    router = _build_router()
    router.register_event_notification_callback(_add_notification)

    agent_id = "analyst-1"
    router.register_agent_wake_callback(agent_id, wake_fn=lambda: None)
    router.subscribe_agent(agent_id, "price-alerts")

    router.deliver_external_event("price-alerts", "threshold_crossed", {"symbol": "AAPL"})

    result = builder.build("Base prompt.")
    assert "price-alerts" in result
    assert "threshold_crossed" in result
    assert "read_event_notifications()" in result


def test_two_agents_with_different_policies_get_different_tools() -> None:
    """Two agents registered on the same router but with different policies."""
    router = _build_router()

    analyst_policy = AgentPolicy(
        name="analyst",
        allowed_services=(ServicePermission("market-data"),),
    )
    trader_policy = AgentPolicy(
        name="trader",
        allowed_services=(
            ServicePermission("market-data"),
            ServicePermission("order-execution"),
        ),
    )

    analyst_pairs = router.wire_agent_tools("analyst-1", analyst_policy)
    trader_pairs = router.wire_agent_tools("trader-1", trader_policy)

    analyst_names = {p[0]["function"]["name"] for p in analyst_pairs}
    trader_names = {p[0]["function"]["name"] for p in trader_pairs}

    assert "place_market_order_v2" not in analyst_names
    assert "place_market_order_v2" in trader_names
    assert "get_market_price" in analyst_names
    assert "get_market_price" in trader_names
