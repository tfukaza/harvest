"""End-to-end tests: tool handlers route through the full service router pipeline.

- DataFetchRequested / DataFetchCompleted emitted
- Policy enforcement applies at the generic level (via fetch_data)
- Result returned correctly
"""


import json
from typing import Any

import pytest

from harvest.agent_sandbox.services.router import SandboxServiceRouter
from harvest.events.event_bus import EventBus
from harvest.events.base import DataFetchCompleted, DataFetchRequested
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


class _MockStockSource(Service):
    def __init__(self) -> None:
        self._fetch_calls: list[dict] = []

    @property
    def service_id(self) -> str:
        return "mock-stock"

    @property
    def roles(self) -> frozenset[ServiceRole]:
        return frozenset({ServiceRole.DATA_SOURCE})

    def get_capabilities(self) -> list[str]:
        return ["price"]

    async def fetch(self, query: DataQuery) -> DataResult:
        self._fetch_calls.append({"query_type": query.query_type, "params": query.params})
        return DataResult(
            request_id=query.request_id,
            source_id=self.service_id,
            payload={"symbol": query.params.get("symbol"), "price": 150.0},
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
            if hasattr(self, "_fetch_callback") and self._fetch_callback is not None:
                return self._fetch_callback(agent_id, self.service_id, "price", {"symbol": symbol})
            return json.dumps({"error": "no_callback"})

        return [
            InterfaceTool(
                name="get_stock_price",
                short_description="Get stock price.",
                full_description="Get the current market price for a symbol.",
                arguments=[ToolArgument(name="symbol", type="string", description="Ticker")],
                returns_description="JSON with price.",
                service_id=self.service_id,
                service_type="data_source",
                handler=_handler,
            )
        ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_tool_handler_routes_to_datasource() -> None:
    """Interface tool handler calls through to Service.fetch."""
    source = _MockStockSource()
    router = SandboxServiceRouter(sandbox_id="test")
    router.register_service(source)

    policy = AgentPolicy(
        name="analyst",
        allowed_services=(ServicePermission("mock-stock"),),
    )
    pairs = router.wire_agent_tools("agent-1", policy)
    assert len(pairs) == 1

    _, callable_ = pairs[0]
    result_str = callable_(symbol="AAPL")
    result = json.loads(result_str)

    assert result.get("price") == 150.0
    assert result.get("symbol") == "AAPL"
    assert len(source._fetch_calls) == 1
    assert source._fetch_calls[0]["query_type"] == "price"
    assert source._fetch_calls[0]["params"]["symbol"] == "AAPL"


def test_tool_handler_emits_data_fetch_events() -> None:
    """DataFetchRequested and DataFetchCompleted are emitted by the tool handler."""
    import asyncio

    async def _run() -> tuple:
        bus = EventBus()
        requested: list[DataFetchRequested] = []
        completed: list[DataFetchCompleted] = []

        def _on_requested(e: DataFetchRequested) -> None:
            requested.append(e)

        def _on_completed(e: DataFetchCompleted) -> None:
            completed.append(e)

        bus.on(DataFetchRequested, _on_requested)
        bus.on(DataFetchCompleted, _on_completed)

        source = _MockStockSource()
        router = SandboxServiceRouter(sandbox_id="test", event_bus=bus)
        router.register_service(source)

        policy = AgentPolicy(
            name="analyst",
            allowed_services=(ServicePermission("mock-stock"),),
        )
        pairs = router.wire_agent_tools("agent-1", policy)
        _, callable_ = pairs[0]
        callable_(symbol="MSFT")

        await asyncio.sleep(0.1)
        await bus.stop()
        return requested, completed

    requested, completed = asyncio.run(_run())
    assert len(requested) == 1
    assert len(completed) == 1
    assert requested[0].source_id == "mock-stock"
    assert completed[0].source_id == "mock-stock"
    assert completed[0].error == ""


def test_tool_handler_result_contains_payload() -> None:
    """Tool handler returns the Service payload as a JSON string."""
    source = _MockStockSource()
    router = SandboxServiceRouter(sandbox_id="test")
    router.register_service(source)

    policy = AgentPolicy(
        name="analyst",
        allowed_services=(ServicePermission("mock-stock"),),
    )
    pairs = router.wire_agent_tools("agent-1", policy)
    _, callable_ = pairs[0]
    result = json.loads(callable_(symbol="GOOG"))
    assert "price" in result
