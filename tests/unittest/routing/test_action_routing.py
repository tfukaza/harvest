"""Tests for ACTION routing through SandboxServiceRouter."""

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
# Stub Service (ACTION role)
# ---------------------------------------------------------------------------


class _EchoAction(Service):
    def __init__(self, service_id: str = "order-execution") -> None:
        self._id = service_id

    @property
    def service_id(self) -> str:
        return self._id

    @property
    def roles(self) -> frozenset[ServiceRole]:
        return frozenset({ServiceRole.ACTION})

    def get_capabilities(self) -> list[str]:
        return ["echo"]

    async def fetch(self, query: DataQuery) -> DataResult:
        raise NotImplementedError

    async def execute(self, command: ActionCommand) -> ActionResult:
        return ActionResult(
            request_id=command.request_id,
            action_id=self.service_id,
            payload={"echoed": command.params, "command_type": command.command_type},
        )

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


def test_execute_action_returns_result_when_allowed() -> None:
    router = SandboxServiceRouter(sandbox_id="test-sandbox")
    router.register_service(_EchoAction("order-execution"))

    policy = AgentPolicy(
        name="trader",
        allowed_services=(ServicePermission("order-execution"),),
    )
    tools, tool_map = router.make_service_tools("agent-1", policy)

    assert "execute_action" in tool_map
    result_json = tool_map["execute_action"](
        "order-execution", "place_order", {"symbol": "AAPL", "qty": 10}
    )
    result = json.loads(result_json)

    assert "error" not in result
    assert result["command_type"] == "place_order"
    assert result["echoed"] == {"symbol": "AAPL", "qty": 10}


# ---------------------------------------------------------------------------
# Routing: policy deny
# ---------------------------------------------------------------------------


def test_execute_action_not_registered_when_no_action_permission() -> None:
    router = SandboxServiceRouter()
    router.register_service(_EchoAction("broker"))

    policy = AgentPolicy(name="analyst", allowed_services=())
    _, tool_map = router.make_service_tools("agent-1", policy)

    assert "execute_action" not in tool_map


def test_execute_action_denied_when_service_not_in_policy() -> None:
    router = SandboxServiceRouter()
    router.register_service(_EchoAction("broker"))
    router.register_service(_EchoAction("mailer"))

    policy = AgentPolicy(
        name="limited",
        allowed_services=(ServicePermission("mailer"),),
    )
    _, tool_map = router.make_service_tools("agent-1", policy)

    result_json = tool_map["execute_action"]("broker", "place_order", {})
    result = json.loads(result_json)
    assert "policy_denied" in result["error"]


def test_execute_action_denied_when_role_restricted() -> None:
    """Policy with DATA_SOURCE-only role denies ACTION execute."""
    router = SandboxServiceRouter()
    router.register_service(_EchoAction("broker"))

    policy = AgentPolicy(
        name="reader-only",
        allowed_services=(
            ServicePermission("broker", roles=frozenset({ServiceRole.DATA_SOURCE})),
        ),
    )
    _, tool_map = router.make_service_tools("agent-1", policy)
    assert "execute_action" not in tool_map


# ---------------------------------------------------------------------------
# Routing: unknown service
# ---------------------------------------------------------------------------


def test_execute_action_error_when_not_registered() -> None:
    router = SandboxServiceRouter()
    policy = AgentPolicy(name="p", allowed_services=(ServicePermission("ghost"),))
    _, tool_map = router.make_service_tools("a", policy)

    result_json = tool_map["execute_action"]("ghost", "do_thing", {})
    result = json.loads(result_json)
    assert "unknown_action" in result["error"]


# ---------------------------------------------------------------------------
# Service registry
# ---------------------------------------------------------------------------


def test_register_duplicate_service_raises() -> None:
    router = SandboxServiceRouter()
    router.register_service(_EchoAction("dup"))
    with pytest.raises(ValueError, match="already registered"):
        router.register_service(_EchoAction("dup"))


def test_list_services() -> None:
    router = SandboxServiceRouter()
    router.register_service(_EchoAction("action-a"))
    router.register_service(_EchoAction("action-b"))
    assert set(router.list_services()) == {"action-a", "action-b"}


def test_execute_action_tool_spec_has_required_fields() -> None:
    router = SandboxServiceRouter()
    router.register_service(_EchoAction("act"))
    policy = AgentPolicy(name="p", allowed_services=(ServicePermission("act"),))
    tools, _ = router.make_service_tools("a", policy)
    spec = next(t for t in tools if t["function"]["name"] == "execute_action")
    params = spec["function"]["parameters"]
    assert "service_id" in params["properties"]
    assert "command_type" in params["properties"]
    assert "service_id" in params["required"]
    assert "command_type" in params["required"]
