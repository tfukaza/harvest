"""Tests for DebugMonitorServer (Flask app, no WebSocket in unit tests)."""


import json
from typing import Any

import pytest

from harvest.agent_sandbox.basic_sandbox import BasicSandbox
from harvest.agent_sandbox.channels import GroupChannel
from harvest.agent_sandbox.config import AgentSandboxConfig
from harvest.debug.registry import SandboxRegistry

# flask and flask-sock are optional; skip if not installed
flask = pytest.importorskip("flask")
flask_sock = pytest.importorskip("flask_sock")

from harvest.debug.server import DebugMonitorServer


def _make_sandbox(name: str = "test") -> BasicSandbox:
    config = AgentSandboxConfig(runner_id=name, display_name=name)
    return BasicSandbox(config=config)


@pytest.fixture
def registry() -> SandboxRegistry:
    return SandboxRegistry()


@pytest.fixture
def server(registry: SandboxRegistry) -> DebugMonitorServer:
    return DebugMonitorServer(registry=registry)


@pytest.fixture
def client(server: DebugMonitorServer) -> Any:
    server.app.config["TESTING"] = True
    return server.app.test_client()


def test_api_snapshot_empty(client: Any) -> None:
    resp = client.get("/api/snapshot")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["type"] == "snapshot"
    assert data["sandboxes"] == []


def test_api_snapshot_with_sandbox(registry: SandboxRegistry, client: Any) -> None:
    sb = _make_sandbox("sb-1")
    registry.register("sb-1", sb)
    resp = client.get("/api/snapshot")
    data = json.loads(resp.data)
    assert len(data["sandboxes"]) == 1
    assert data["sandboxes"][0]["sandbox_id"] == "sb-1"


def test_api_snapshot_with_agents(registry: SandboxRegistry, client: Any) -> None:
    from harvest.core.agent import Agent

    class _Stub(Agent):
        def step(self, input_data: Any) -> str:
            return ""
        def reset(self) -> None:
            pass
        def get_reasoning_history(self) -> list[Any]:
            return []

    sb = _make_sandbox("sb-1")
    sb.register_agent("agent-x", _Stub())
    registry.register("sb-1", sb)

    resp = client.get("/api/snapshot")
    data = json.loads(resp.data)
    agents = data["sandboxes"][0]["agents"]
    assert len(agents) == 1
    assert agents[0]["agent_id"] == "agent-x"


def test_api_snapshot_with_channels(registry: SandboxRegistry, client: Any) -> None:
    sb = _make_sandbox("sb-1")
    group = GroupChannel(channel_id="grp-1", member_ids=["a", "b"])
    sb.chat_router.create_channel(group)
    registry.register("sb-1", sb)

    resp = client.get("/api/snapshot")
    data = json.loads(resp.data)
    channels = data["sandboxes"][0]["channels"]
    assert len(channels) == 1
    assert channels[0]["channel_id"] == "grp-1"


def test_server_creates_cleanly(registry: SandboxRegistry) -> None:
    server = DebugMonitorServer(registry=registry, port=8199)
    assert server.app is not None
