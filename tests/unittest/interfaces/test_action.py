"""Tests for Service with ACTION role (replaces Action ABC tests)."""


from typing import Any

import pytest

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
# Concrete stubs
# ---------------------------------------------------------------------------


class _EchoActionService(Service):
    """Service with ACTION role that echoes command params."""

    @property
    def service_id(self) -> str:
        return "echo-action"

    @property
    def roles(self) -> frozenset[ServiceRole]:
        return frozenset({ServiceRole.ACTION})

    def get_capabilities(self) -> list[str]:
        return ["echo"]

    async def fetch(self, query: DataQuery) -> DataResult:
        raise NotImplementedError("ACTION only")

    async def execute(self, command: ActionCommand) -> ActionResult:
        return ActionResult(
            request_id=command.request_id,
            action_id=self.service_id,
            payload={"echoed": command.params},
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
        return []


class _FailingActionService(Service):
    """Service with ACTION role that always returns an error."""

    @property
    def service_id(self) -> str:
        return "failing-action"

    @property
    def roles(self) -> frozenset[ServiceRole]:
        return frozenset({ServiceRole.ACTION})

    def get_capabilities(self) -> list[str]:
        return []

    async def fetch(self, query: DataQuery) -> DataResult:
        raise NotImplementedError("ACTION only")

    async def execute(self, command: ActionCommand) -> ActionResult:
        return ActionResult(
            request_id=command.request_id,
            action_id=self.service_id,
            payload={},
            error="always_fails",
        )

    async def start(self, event_bus: Any = None) -> None:
        pass

    async def stop(self) -> None:
        pass

    def health_check(self) -> dict[str, Any]:
        return {"status": "degraded"}

    def get_tools(self, role: ServiceRole | None = None) -> list[InterfaceTool]:
        return []


# ---------------------------------------------------------------------------
# Contract compliance tests
# ---------------------------------------------------------------------------


def test_service_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        Service()  # type: ignore[abstract]


def test_concrete_subclass_satisfies_contract() -> None:
    svc = _EchoActionService()
    assert svc.service_id == "echo-action"
    assert ServiceRole.ACTION in svc.roles
    assert "echo" in svc.get_capabilities()
    assert svc.health_check()["status"] == "healthy"


def test_execute_returns_action_result() -> None:
    import asyncio

    svc = _EchoActionService()
    command = ActionCommand(
        command_type="post_request",
        params={"url": "https://example.com"},
        agent_id="agent-1",
        request_id="cmd-abc",
    )
    result = asyncio.run(svc.execute(command))

    assert isinstance(result, ActionResult)
    assert result.request_id == "cmd-abc"
    assert result.action_id == "echo-action"
    assert result.payload == {"echoed": {"url": "https://example.com"}}
    assert result.error == ""


def test_failing_action_returns_error_result() -> None:
    import asyncio

    svc = _FailingActionService()
    command = ActionCommand(
        command_type="place_order",
        params={},
        agent_id="agent-1",
        request_id="cmd-xyz",
    )
    result = asyncio.run(svc.execute(command))

    assert result.error == "always_fails"
    assert result.payload == {}


def test_action_command_is_a_dataclass() -> None:
    c = ActionCommand(
        command_type="update_doc",
        params={"doc_id": "123"},
        agent_id="a",
        request_id="r",
    )
    assert c.command_type == "update_doc"
    assert c.params == {"doc_id": "123"}


def test_action_result_default_error_is_empty() -> None:
    r = ActionResult(request_id="r", action_id="a", payload={"ok": True})
    assert r.error == ""


# ---------------------------------------------------------------------------
# get_tools() contract tests
# ---------------------------------------------------------------------------


def test_get_tools_returns_empty_list() -> None:
    svc = _EchoActionService()
    assert svc.get_tools() == []


def test_get_tools_filtered_by_role() -> None:
    """get_tools(role=ACTION) returns action tools."""

    class _TooledActionService(Service):
        @property
        def service_id(self) -> str:
            return "tooled-action"

        @property
        def roles(self) -> frozenset[ServiceRole]:
            return frozenset({ServiceRole.ACTION})

        def get_capabilities(self) -> list[str]:
            return ["do_thing"]

        async def fetch(self, query: DataQuery) -> DataResult:
            raise NotImplementedError

        async def execute(self, command: ActionCommand) -> ActionResult:
            return ActionResult(request_id=command.request_id, action_id=self.service_id, payload={})

        async def start(self, event_bus: Any = None) -> None:
            pass

        async def stop(self) -> None:
            pass

        def health_check(self) -> dict[str, Any]:
            return {"status": "healthy"}

        def get_tools(self, role: ServiceRole | None = None) -> list[InterfaceTool]:
            if role is not None and role != ServiceRole.ACTION:
                return []
            return [
                InterfaceTool(
                    name="do_thing",
                    short_description="Do a thing.",
                    full_description="Do a thing with some params.",
                    arguments=[
                        ToolArgument(name="param1", type="string", description="First param"),
                    ],
                    returns_description="Result of doing the thing.",
                    service_id="tooled-action",
                    service_type="action",
                    handler=lambda agent_id, param1: "{}",
                )
            ]

    svc = _TooledActionService()
    tools = svc.get_tools(role=ServiceRole.ACTION)
    assert len(tools) == 1
    assert tools[0].name == "do_thing"
    assert tools[0].service_type == "action"

    # Wrong role returns empty
    assert svc.get_tools(role=ServiceRole.DATA_SOURCE) == []


def test_service_roles_declared() -> None:
    svc = _EchoActionService()
    assert ServiceRole.ACTION in svc.roles
    assert ServiceRole.DATA_SOURCE not in svc.roles
    assert ServiceRole.EVENT_SOURCE not in svc.roles


def test_bind_execute_callback_stores_callback() -> None:
    svc = _EchoActionService()
    callback_called_with: list = []

    def _cb(agent_id: str, service_id: str, command_type: str, params: dict) -> str:
        callback_called_with.append((agent_id, service_id, command_type, params))
        return "{}"

    svc.bind_execute_callback(_cb)
    assert hasattr(svc, "_execute_callback")
    assert svc._execute_callback is _cb
