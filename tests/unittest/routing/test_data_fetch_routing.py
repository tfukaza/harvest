"""Tests for DATA_SOURCE routing through SandboxServiceRouter."""

from __future__ import annotations

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
from harvest.interfaces.tool_definition import InterfaceTool
from harvest.policy import AgentPolicy


# ---------------------------------------------------------------------------
# Stub Service (DATA_SOURCE role)
# ---------------------------------------------------------------------------


class _EchoSource(Service):
    def __init__(self, service_id: str = "market-data") -> None:
        self._id = service_id

    @property
    def service_id(self) -> str:
        return self._id

    @property
    def roles(self) -> frozenset[ServiceRole]:
        return frozenset({ServiceRole.DATA_SOURCE})

    def get_capabilities(self) -> list[str]:
        return ["echo"]

    async def fetch(self, query: DataQuery) -> DataResult:
        return DataResult(
            request_id=query.request_id,
            source_id=self.service_id,
            payload={"echoed": query.params, "query_type": query.query_type},
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
        return []


# ---------------------------------------------------------------------------
# Routing: happy path
# ---------------------------------------------------------------------------


def test_fetch_data_returns_result_when_allowed() -> None:
    router = SandboxServiceRouter(sandbox_id="test-sandbox")
    router.register_service(_EchoSource("market-data"))

    policy = AgentPolicy(
        name="analyst",
        allowed_services=(ServicePermission("market-data"),),
    )
    tools, tool_map = router.make_service_tools("agent-1", policy)

    assert "fetch_data" in tool_map
    result_json = tool_map["fetch_data"]("market-data", "price", {"symbol": "AAPL"})
    result = json.loads(result_json)

    assert "error" not in result
    assert result["query_type"] == "price"
    assert result["echoed"] == {"symbol": "AAPL"}


def test_fetch_data_empty_params_defaults_to_empty_dict() -> None:
    router = SandboxServiceRouter(sandbox_id="test-sandbox")
    router.register_service(_EchoSource("market-data"))

    policy = AgentPolicy(name="analyst", allowed_services=(ServicePermission("market-data"),))
    _, tool_map = router.make_service_tools("agent-1", policy)

    result_json = tool_map["fetch_data"]("market-data", "price")
    result = json.loads(result_json)
    assert result["echoed"] == {}


# ---------------------------------------------------------------------------
# Routing: policy deny
# ---------------------------------------------------------------------------


def test_fetch_data_tool_absent_when_no_data_source_permission() -> None:
    router = SandboxServiceRouter(sandbox_id="test-sandbox")
    router.register_service(_EchoSource("market-data"))

    policy = AgentPolicy(
        name="restricted",
        allowed_services=(),  # no access
    )
    _, tool_map = router.make_service_tools("agent-1", policy)

    assert "fetch_data" not in tool_map


def test_fetch_data_denied_when_service_id_not_in_policy() -> None:
    router = SandboxServiceRouter(sandbox_id="test-sandbox")
    router.register_service(_EchoSource("market-data"))
    router.register_service(_EchoSource("news-feed"))

    policy = AgentPolicy(
        name="limited",
        allowed_services=(ServicePermission("news-feed"),),
    )
    _, tool_map = router.make_service_tools("agent-1", policy)

    result_json = tool_map["fetch_data"]("market-data", "price", {})
    result = json.loads(result_json)
    assert "policy_denied" in result["error"]


def test_fetch_data_denied_when_role_restricted() -> None:
    """Policy with ACTION-only role for a service denies DATA_SOURCE fetch."""
    router = SandboxServiceRouter(sandbox_id="test-sandbox")
    router.register_service(_EchoSource("market-data"))

    policy = AgentPolicy(
        name="action-only",
        allowed_services=(
            ServicePermission("market-data", roles=frozenset({ServiceRole.ACTION})),
        ),
    )
    _, tool_map = router.make_service_tools("agent-1", policy)
    # No DATA_SOURCE permission → no fetch_data tool
    assert "fetch_data" not in tool_map


# ---------------------------------------------------------------------------
# Routing: unknown service
# ---------------------------------------------------------------------------


def test_fetch_data_error_when_service_not_registered() -> None:
    router = SandboxServiceRouter(sandbox_id="test-sandbox")
    policy = AgentPolicy(
        name="analyst",
        allowed_services=(ServicePermission("ghost-source"),),
    )
    _, tool_map = router.make_service_tools("agent-1", policy)

    result_json = tool_map["fetch_data"]("ghost-source", "price", {})
    result = json.loads(result_json)
    assert "unknown_source" in result["error"]


# ---------------------------------------------------------------------------
# Service registry
# ---------------------------------------------------------------------------


def test_register_duplicate_service_raises() -> None:
    router = SandboxServiceRouter()
    router.register_service(_EchoSource("dup"))
    with pytest.raises(ValueError, match="already registered"):
        router.register_service(_EchoSource("dup"))


def test_list_services() -> None:
    router = SandboxServiceRouter()
    router.register_service(_EchoSource("source-a"))
    router.register_service(_EchoSource("source-b"))
    assert set(router.list_services()) == {"source-a", "source-b"}


# ---------------------------------------------------------------------------
# Tool spec
# ---------------------------------------------------------------------------


def test_no_policy_registers_fetch_data_tool() -> None:
    """No policy (sandbox admin mode) gets all generic tools."""
    router = SandboxServiceRouter()
    router.register_service(_EchoSource("any"))
    tools, tool_map = router.make_service_tools("admin", policy=None)
    names = [t["function"]["name"] for t in tools]
    assert "fetch_data" in names
    assert "fetch_data" in tool_map


def test_fetch_data_tool_spec_has_required_fields() -> None:
    router = SandboxServiceRouter()
    router.register_service(_EchoSource("ds"))
    policy = AgentPolicy(name="p", allowed_services=(ServicePermission("ds"),))
    tools, _ = router.make_service_tools("a", policy)
    fetch_spec = next(t for t in tools if t["function"]["name"] == "fetch_data")
    params = fetch_spec["function"]["parameters"]
    assert "service_id" in params["properties"]
    assert "query_type" in params["properties"]
    assert "service_id" in params["required"]
    assert "query_type" in params["required"]
