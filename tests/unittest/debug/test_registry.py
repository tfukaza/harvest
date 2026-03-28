"""Tests for SandboxRegistry."""


from typing import Any
from unittest.mock import MagicMock

import pytest

from harvest.agent_sandbox.basic_sandbox import BasicSandbox
from harvest.agent_sandbox.channels import GroupChannel
from harvest.agent_sandbox.chat import ChatRouter
from harvest.agent_sandbox.config import AgentSandboxConfig
from harvest.debug.registry import SandboxRegistry
from harvest.debug.snapshot import SandboxSnapshot


def _make_sandbox(name: str = "test") -> BasicSandbox:
    config = AgentSandboxConfig(runner_id=name, display_name=name)
    return BasicSandbox(config=config)


def test_register_and_list() -> None:
    registry = SandboxRegistry()
    sb = _make_sandbox("sb-1")
    registry.register("sb-1", sb)
    assert "sb-1" in registry.list_sandbox_ids()


def test_unregister() -> None:
    registry = SandboxRegistry()
    sb = _make_sandbox("sb-1")
    registry.register("sb-1", sb)
    registry.unregister("sb-1")
    assert "sb-1" not in registry.list_sandbox_ids()


def test_duplicate_register_raises() -> None:
    registry = SandboxRegistry()
    sb = _make_sandbox("sb-1")
    registry.register("sb-1", sb)
    with pytest.raises(ValueError, match="already registered"):
        registry.register("sb-1", sb)


def test_get_sandbox() -> None:
    registry = SandboxRegistry()
    sb = _make_sandbox("sb-1")
    registry.register("sb-1", sb)
    assert registry.get_sandbox("sb-1") is sb


def test_get_unknown_raises() -> None:
    registry = SandboxRegistry()
    with pytest.raises(KeyError):
        registry.get_sandbox("nonexistent")


def test_snapshot_all_empty() -> None:
    registry = SandboxRegistry()
    assert registry.snapshot_all() == []


def test_snapshot_basic() -> None:
    registry = SandboxRegistry()
    sb = _make_sandbox("sb-1")

    # Add a stub agent
    from harvest.core.agent import Agent

    class _Stub(Agent):
        def step(self, input_data: Any) -> str:
            return ""
        def reset(self) -> None:
            pass
        def get_reasoning_history(self) -> list[Any]:
            return []

    sb.register_agent("a1", _Stub())

    # Add a channel
    group = GroupChannel(channel_id="ch-1", member_ids=["a1"])
    sb.chat_router.create_channel(group)

    registry.register("sb-1", sb)
    snapshots = registry.snapshot_all()
    assert len(snapshots) == 1
    snap = snapshots[0]
    assert snap.sandbox_id == "sb-1"
    assert len(snap.agents) == 1
    assert snap.agents[0].agent_id == "a1"
    assert len(snap.channels) == 1
    assert snap.channels[0].channel_id == "ch-1"


def test_snapshot_multiple_sandboxes() -> None:
    registry = SandboxRegistry()
    registry.register("sb-1", _make_sandbox("sb-1"))
    registry.register("sb-2", _make_sandbox("sb-2"))
    snapshots = registry.snapshot_all()
    ids = {s.sandbox_id for s in snapshots}
    assert ids == {"sb-1", "sb-2"}
