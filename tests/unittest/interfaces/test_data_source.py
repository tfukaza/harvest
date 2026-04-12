"""Tests for Service with DATA_SOURCE role (replaces DataSource ABC tests)."""


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


class _EchoDataService(Service):
    """Service with DATA_SOURCE role that echoes query params."""

    @property
    def service_id(self) -> str:
        return "echo-source"

    @property
    def roles(self) -> frozenset[ServiceRole]:
        return frozenset({ServiceRole.DATA_SOURCE})

    def get_capabilities(self) -> list[str]:
        return ["echo"]

    async def fetch(self, query: DataQuery) -> DataResult:
        return DataResult(
            request_id=query.request_id,
            source_id=self.service_id,
            payload={"echoed": query.params},
        )

    async def execute(self, command: ActionCommand) -> ActionResult:
        raise NotImplementedError("DATA_SOURCE only")

    async def start(self, event_bus: Any = None) -> None:
        pass

    async def stop(self) -> None:
        pass

    def health_check(self) -> dict[str, Any]:
        return {"status": "healthy"}

    def get_tools(self, role: ServiceRole | None = None) -> list[InterfaceTool]:
        if role is not None and role != ServiceRole.DATA_SOURCE:
            return []
        return []


class _FailingDataService(Service):
    """Service with DATA_SOURCE role that always returns an error."""

    @property
    def service_id(self) -> str:
        return "failing-source"

    @property
    def roles(self) -> frozenset[ServiceRole]:
        return frozenset({ServiceRole.DATA_SOURCE})

    def get_capabilities(self) -> list[str]:
        return []

    async def fetch(self, query: DataQuery) -> DataResult:
        return DataResult(
            request_id=query.request_id,
            source_id=self.service_id,
            payload={},
            error="always_fails",
        )

    async def execute(self, command: ActionCommand) -> ActionResult:
        raise NotImplementedError("DATA_SOURCE only")

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
    svc = _EchoDataService()
    assert svc.service_id == "echo-source"
    assert ServiceRole.DATA_SOURCE in svc.roles
    assert "echo" in svc.get_capabilities()
    assert svc.health_check()["status"] == "healthy"


def test_fetch_returns_data_result() -> None:
    import asyncio

    svc = _EchoDataService()
    query = DataQuery(
        query_type="search",
        params={"term": "hello"},
        agent_id="agent-1",
        request_id="req-abc",
    )
    result = asyncio.run(svc.fetch(query))

    assert isinstance(result, DataResult)
    assert result.request_id == "req-abc"
    assert result.source_id == "echo-source"
    assert result.payload == {"echoed": {"term": "hello"}}
    assert result.error == ""


def test_failing_source_returns_error_result() -> None:
    import asyncio

    svc = _FailingDataService()
    query = DataQuery(
        query_type="price",
        params={},
        agent_id="agent-1",
        request_id="req-xyz",
    )
    result = asyncio.run(svc.fetch(query))

    assert result.error == "always_fails"
    assert result.payload == {}


def test_data_query_is_a_dataclass() -> None:
    q = DataQuery(query_type="news", params={"k": "v"}, agent_id="a", request_id="r")
    assert q.query_type == "news"
    assert q.params == {"k": "v"}
    assert q.agent_id == "a"
    assert q.request_id == "r"


def test_data_result_default_error_is_empty() -> None:
    r = DataResult(request_id="r", source_id="s", payload={"x": 1})
    assert r.error == ""


def test_data_result_error_field() -> None:
    r = DataResult(request_id="r", source_id="s", payload={}, error="oops")
    assert r.error == "oops"


# ---------------------------------------------------------------------------
# get_tools() contract tests
# ---------------------------------------------------------------------------


def test_get_tools_returns_empty_list() -> None:
    svc = _EchoDataService()
    assert svc.get_tools() == []


def test_get_tools_filtered_by_role() -> None:
    """get_tools(role=DATA_SOURCE) returns data source tools."""

    class _TooledService(Service):
        @property
        def service_id(self) -> str:
            return "tooled-source"

        @property
        def roles(self) -> frozenset[ServiceRole]:
            return frozenset({ServiceRole.DATA_SOURCE})

        def get_capabilities(self) -> list[str]:
            return ["lookup"]

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
            return [
                InterfaceTool(
                    name="lookup_thing",
                    short_description="Look up a thing.",
                    full_description="Look up a thing by ID.",
                    arguments=[
                        ToolArgument(name="thing_id", type="string", description="The thing ID"),
                    ],
                    returns_description="The thing data.",
                    service_id="tooled-source",
                    service_type="data_source",
                    handler=lambda agent_id, thing_id: "{}",
                )
            ]

    svc = _TooledService()
    tools = svc.get_tools(role=ServiceRole.DATA_SOURCE)
    assert len(tools) == 1
    assert tools[0].name == "lookup_thing"
    assert tools[0].service_type == "data_source"

    # Wrong role returns empty
    assert svc.get_tools(role=ServiceRole.ACTION) == []


def test_service_roles_declared() -> None:
    svc = _EchoDataService()
    assert ServiceRole.DATA_SOURCE in svc.roles
    assert ServiceRole.ACTION not in svc.roles
    assert ServiceRole.EVENT_SOURCE not in svc.roles


def test_bind_fetch_callback_stores_callback() -> None:
    svc = _EchoDataService()
    callback_called_with: list = []

    def _cb(agent_id: str, service_id: str, query_type: str, params: dict) -> str:
        callback_called_with.append((agent_id, service_id, query_type, params))
        return "{}"

    svc.bind_fetch_callback(_cb)
    assert hasattr(svc, "_fetch_callback")
    assert svc._fetch_callback is _cb
