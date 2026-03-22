"""Tests for BasicSandbox — agent hosting, threading, policy, event fan-out, manifest loading."""

from __future__ import annotations

import asyncio
import tempfile
import threading
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from harvest.agent import Agent
from harvest.agent_sandbox.basic_sandbox import BasicSandbox, _AgentHandle
from harvest.agent_sandbox.channels import DMChannel, GroupChannel, GatedProcessorChannel
from harvest.agent_sandbox.chat import ChatRouter
from harvest.agent_sandbox.config import AgentSandboxConfig
from harvest.agent_sandbox.manifest import load_manifest, SandboxManifest
from harvest.policy import AgentPolicy, ChildPolicyMode
from harvest.policy_registry import PolicyRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(name: str = "test-sandbox") -> AgentSandboxConfig:
    return AgentSandboxConfig(runner_id=name, display_name=name)


class _StubAgent(Agent):
    """Minimal Agent that records step() calls."""

    def __init__(self) -> None:
        self.step_calls: list[str] = []
        self._shutdown_called = False

    def step(self, input_data: Any) -> str:
        self.step_calls.append(str(input_data))
        return f"ack:{input_data}"

    def reset(self) -> None:
        self.step_calls.clear()

    def get_reasoning_history(self) -> list[Any]:
        return []

    def shutdown(self) -> None:
        self._shutdown_called = True


class _FailingAgent(Agent):
    """Agent whose step() always raises."""

    def step(self, input_data: Any) -> str:
        raise RuntimeError("deliberate failure")

    def reset(self) -> None:
        pass

    def get_reasoning_history(self) -> list[Any]:
        return []

    def shutdown(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Agent hosting and threading
# ---------------------------------------------------------------------------


def test_register_and_list_agents() -> None:
    sandbox = BasicSandbox(config=_make_config())
    sandbox.register_agent("a1", _StubAgent())
    sandbox.register_agent("a2", _StubAgent())
    assert sorted(sandbox.list_agents()) == ["a1", "a2"]


def test_duplicate_agent_id_raises() -> None:
    sandbox = BasicSandbox(config=_make_config())
    sandbox.register_agent("a1", _StubAgent())
    with pytest.raises(ValueError, match="already registered"):
        sandbox.register_agent("a1", _StubAgent())


def test_remove_agent_calls_shutdown() -> None:
    sandbox = BasicSandbox(config=_make_config())
    agent = _StubAgent()
    sandbox.register_agent("a1", agent)
    sandbox.remove_agent("a1")
    assert agent._shutdown_called
    assert "a1" not in sandbox.list_agents()


def test_remove_unknown_agent_raises() -> None:
    sandbox = BasicSandbox(config=_make_config())
    with pytest.raises(KeyError):
        sandbox.remove_agent("nonexistent")


def test_get_agent() -> None:
    sandbox = BasicSandbox(config=_make_config())
    agent = _StubAgent()
    sandbox.register_agent("a1", agent)
    assert sandbox.get_agent("a1") is agent


def test_get_unknown_agent_raises() -> None:
    sandbox = BasicSandbox(config=_make_config())
    with pytest.raises(KeyError):
        sandbox.get_agent("nonexistent")


def test_start_creates_threads() -> None:
    sandbox = BasicSandbox(config=_make_config())
    sandbox.register_agent("a1", _StubAgent())
    sandbox.register_agent("a2", _StubAgent())
    asyncio.run(sandbox.start())
    handle1 = sandbox.get_agent_handle("a1")
    handle2 = sandbox.get_agent_handle("a2")
    assert handle1.thread is not None and handle1.thread.is_alive()
    assert handle2.thread is not None and handle2.thread.is_alive()
    asyncio.run(sandbox.stop())


def test_stop_clears_agents() -> None:
    sandbox = BasicSandbox(config=_make_config())
    sandbox.register_agent("a1", _StubAgent())
    asyncio.run(sandbox.start())
    asyncio.run(sandbox.stop())
    assert sandbox.list_agents() == []


# ---------------------------------------------------------------------------
# Event fan-out
# ---------------------------------------------------------------------------


def test_handle_event_fans_out() -> None:
    sandbox = BasicSandbox(config=_make_config())
    a1 = _StubAgent()
    a2 = _StubAgent()
    sandbox.register_agent("a1", a1)
    sandbox.register_agent("a2", a2)
    results = sandbox.handle_event("test_event", {"key": "value"})
    assert "a1" in results
    assert "a2" in results
    assert len(a1.step_calls) == 1
    assert len(a2.step_calls) == 1


def test_handle_event_empty_sandbox() -> None:
    sandbox = BasicSandbox(config=_make_config())
    results = sandbox.handle_event("test_event", {})
    assert results == {}


def test_handle_event_records_errors() -> None:
    sandbox = BasicSandbox(config=_make_config())
    sandbox.register_agent("good", _StubAgent())
    sandbox.register_agent("bad", _FailingAgent())
    results = sandbox.handle_event("test_event", {})
    assert "error" in results["bad"]
    assert "good" in results  # good agent still executed


# ---------------------------------------------------------------------------
# Lifecycle and health
# ---------------------------------------------------------------------------


def test_health_check() -> None:
    sandbox = BasicSandbox(config=_make_config())
    sandbox.register_agent("a1", _StubAgent())
    health = sandbox.health_check()
    assert health["running"] is False
    assert health["agent_count"] == 1
    assert "a1" in health["agents"]


def test_config_property() -> None:
    cfg = _make_config("my-sandbox")
    sandbox = BasicSandbox(config=cfg)
    assert sandbox.config is cfg


def test_supported_delivery_modes() -> None:
    from harvest.agent_sandbox.endpoints import DeliveryMode
    sandbox = BasicSandbox(config=_make_config())
    modes = sandbox.get_supported_delivery_modes()
    assert DeliveryMode.PUSH in modes
    assert DeliveryMode.PULL in modes


# ---------------------------------------------------------------------------
# ChatRouter ownership
# ---------------------------------------------------------------------------


def test_chat_router_accessible() -> None:
    sandbox = BasicSandbox(config=_make_config())
    assert isinstance(sandbox.chat_router, ChatRouter)


def test_register_group_chat() -> None:
    from harvest.agent_sandbox.endpoints import EndpointAddress, EndpointKind, GroupChatDefinition
    sandbox = BasicSandbox(config=_make_config())
    group_def = GroupChatDefinition(
        address=EndpointAddress(endpoint_id="grp-1", kind=EndpointKind.GROUP_CHAT),
        member_ids=["a1", "a2"],
        description="test group",
    )
    sandbox.register_group_chat(group_def)
    assert "grp-1" in sandbox.list_group_chats()


# ---------------------------------------------------------------------------
# Manifest loading
# ---------------------------------------------------------------------------


_MINIMAL_MANIFEST = """\
sandbox:
  name: test-team

  policies:
    worker:
      allowed_tools:
        - get_username
      can_send_messages: true
      can_create_channel: false
      can_create_agents: false
      child_policy_mode: none

  agents:
    agent-a:
      policy: worker
      model: test-model
      system_prompt: "You are agent A."
    agent-b:
      policy: worker
      model: test-model
      system_prompt: "You are agent B."

  channels:
    team-chat:
      type: group
      description: "Team discussion"
      members:
        - agent-a
        - agent-b
"""


def _write_manifest(content: str) -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    f.write(content)
    f.flush()
    f.close()
    return Path(f.name)


def test_load_manifest_basic() -> None:
    path = _write_manifest(_MINIMAL_MANIFEST)
    manifest = load_manifest(path)
    assert manifest.name == "test-team"
    assert "agent-a" in manifest.agents
    assert "agent-b" in manifest.agents
    assert "team-chat" in manifest.channels
    assert "worker" in manifest.policies


def test_load_manifest_policy_from_registry() -> None:
    yaml_content = """\
sandbox:
  name: reg-test
  agents:
    agent-x:
      policy: shared-pol
      model: m
      system_prompt: "x"
  channels: {}
"""
    path = _write_manifest(yaml_content)
    registry = PolicyRegistry()
    registry.register(AgentPolicy(name="shared-pol"))
    manifest = load_manifest(path, registry=registry)
    assert "shared-pol" in manifest.policies


def test_load_manifest_undefined_policy_raises() -> None:
    yaml_content = """\
sandbox:
  name: bad
  agents:
    agent-x:
      policy: nonexistent
      model: m
      system_prompt: "x"
  channels: {}
"""
    path = _write_manifest(yaml_content)
    with pytest.raises(ValueError, match="undefined policy"):
        load_manifest(path)


def test_load_manifest_undefined_agent_in_channel_raises() -> None:
    yaml_content = """\
sandbox:
  name: bad
  agents:
    agent-a:
      policy: ""
      model: m
      system_prompt: "a"
  channels:
    ch1:
      type: group
      members:
        - agent-a
        - agent-z
"""
    path = _write_manifest(yaml_content)
    with pytest.raises(ValueError, match="undefined agent"):
        load_manifest(path)


def test_load_manifest_dm_wrong_member_count() -> None:
    yaml_content = """\
sandbox:
  name: bad
  agents:
    a:
      model: m
      system_prompt: "a"
    b:
      model: m
      system_prompt: "b"
    c:
      model: m
      system_prompt: "c"
  channels:
    bad-dm:
      type: dm
      members:
        - a
        - b
        - c
"""
    path = _write_manifest(yaml_content)
    with pytest.raises(ValueError, match="exactly 2 members"):
        load_manifest(path)


def test_load_manifest_processor_no_publishers() -> None:
    yaml_content = """\
sandbox:
  name: bad
  agents:
    a:
      model: m
      system_prompt: "a"
  channels:
    proc:
      type: processor_gated
      publishers: []
      subscribers:
        - a
"""
    path = _write_manifest(yaml_content)
    with pytest.raises(ValueError, match="at least 1 publisher"):
        load_manifest(path)


def test_load_manifest_processor_no_subscribers() -> None:
    yaml_content = """\
sandbox:
  name: bad
  agents:
    a:
      model: m
      system_prompt: "a"
  channels:
    proc:
      type: processor_gated
      publishers:
        - a
      subscribers: []
"""
    path = _write_manifest(yaml_content)
    with pytest.raises(ValueError, match="at least 1 subscriber"):
        load_manifest(path)


def test_from_manifest_creates_sandbox() -> None:
    path = _write_manifest(_MINIMAL_MANIFEST)
    sandbox = BasicSandbox.from_manifest(path)
    assert sorted(sandbox.list_agents()) == ["agent-a", "agent-b"]
    channels = sandbox.chat_router.list_channels()
    channel_ids = [ch.channel_id for ch in channels]
    assert "team-chat" in channel_ids


def test_from_manifest_not_started() -> None:
    path = _write_manifest(_MINIMAL_MANIFEST)
    sandbox = BasicSandbox.from_manifest(path)
    health = sandbox.health_check()
    assert health["running"] is False


def test_from_manifest_with_dm_channel() -> None:
    yaml_content = """\
sandbox:
  name: dm-test
  agents:
    alice:
      model: m
      system_prompt: "alice"
    bob:
      model: m
      system_prompt: "bob"
  channels:
    dm-ab:
      type: dm
      members:
        - alice
        - bob
"""
    path = _write_manifest(yaml_content)
    sandbox = BasicSandbox.from_manifest(path)
    channels = sandbox.chat_router.list_channels()
    assert len(channels) == 1
    assert channels[0].channel_id == "dm-ab"


def test_from_manifest_with_gated_channel() -> None:
    yaml_content = """\
sandbox:
  name: gated-test
  agents:
    pub:
      model: m
      system_prompt: "pub"
    sub:
      model: m
      system_prompt: "sub"
  channels:
    pipeline:
      type: processor_gated
      publishers:
        - pub
      subscribers:
        - sub
"""
    path = _write_manifest(yaml_content)
    sandbox = BasicSandbox.from_manifest(path)
    channels = sandbox.chat_router.list_channels()
    assert len(channels) == 1
    assert channels[0].channel_id == "pipeline"


def test_from_manifest_with_aggregation_channel() -> None:
    yaml_content = """\
sandbox:
  name: agg-test
  agents:
    pub:
      model: m
      system_prompt: "pub"
    sub:
      model: m
      system_prompt: "sub"
  channels:
    agg:
      type: processor_aggregation
      publishers:
        - pub
      subscribers:
        - sub
      batch_threshold: 3
"""
    path = _write_manifest(yaml_content)
    sandbox = BasicSandbox.from_manifest(path)
    channels = sandbox.chat_router.list_channels()
    assert len(channels) == 1
    from harvest.agent_sandbox.channels import AggregationProcessorChannel
    assert isinstance(channels[0], AggregationProcessorChannel)
    assert channels[0].batch_threshold == 3


# ---------------------------------------------------------------------------
# Policy enforcement at sandbox level
# ---------------------------------------------------------------------------


def _make_harvest_agent(
    agent_id: str,
    chat_router: ChatRouter,
    policy: AgentPolicy | None = None,
) -> Any:
    """Create a HarvestAgent for testing."""
    from harvest.harvest_agent import HarvestAgent, HarvestAgentConfig
    config = HarvestAgentConfig(model="test-model", system_prompt="test")
    return HarvestAgent(
        config=config,
        agent_id=agent_id,
        chat_router=chat_router,
        policy=policy,
    )


def test_policy_no_send_message_tool() -> None:
    sandbox = BasicSandbox(config=_make_config())
    policy = AgentPolicy(name="mute", can_send_messages=False)
    agent = _make_harvest_agent("a1", sandbox.chat_router, policy)
    sandbox.register_agent("a1", agent, policy=policy)
    tool_names = [t["function"]["name"] for t in agent._tools]
    assert "send_message" not in tool_names


def test_policy_no_create_channel_tool() -> None:
    sandbox = BasicSandbox(config=_make_config())
    policy = AgentPolicy(name="limited", can_create_channel=False)
    agent = _make_harvest_agent("a1", sandbox.chat_router, policy)
    sandbox.register_agent("a1", agent, policy=policy)
    tool_names = [t["function"]["name"] for t in agent._tools]
    assert "create_channel" not in tool_names


def test_create_agent_denied_when_policy_forbids() -> None:
    sandbox = BasicSandbox(config=_make_config())
    policy = AgentPolicy(name="no-spawn", can_create_agents=False)
    agent = _make_harvest_agent("parent", sandbox.chat_router, policy)
    agent._sandbox = sandbox
    sandbox.register_agent("parent", agent, policy=policy)
    tool_names = [t["function"]["name"] for t in agent._tools]
    assert "create_agent" not in tool_names


def test_create_agent_clone_mode() -> None:
    registry = PolicyRegistry()
    sandbox = BasicSandbox(config=_make_config(), policy_registry=registry)
    policy = AgentPolicy(
        name="cloner",
        can_create_agents=True,
        can_send_messages=True,
        child_policy_mode=ChildPolicyMode.CLONE,
        allowed_tools=frozenset(["get_username"]),
    )
    agent = _make_harvest_agent("parent", sandbox.chat_router, policy)
    agent._sandbox = sandbox
    agent._policy = policy
    sandbox.register_agent("parent", agent, policy=policy)

    result = agent._tool_map["create_agent"](agent_id="child-1")
    import json
    data = json.loads(result)
    assert data["status"] == "created"
    assert "child-1" in sandbox.list_agents()

    # Child should have same permissions as parent
    child_handle = sandbox.get_agent_handle("child-1")
    assert child_handle.policy is not None
    assert child_handle.policy.can_send_messages == policy.can_send_messages
    assert child_handle.policy.allowed_tools == policy.allowed_tools


def test_create_agent_predefined_mode() -> None:
    registry = PolicyRegistry()
    worker_pol = AgentPolicy(name="worker", allowed_tools=frozenset(["get_username"]))
    registry.register(worker_pol)

    sandbox = BasicSandbox(config=_make_config(), policy_registry=registry)
    policy = AgentPolicy(
        name="supervisor",
        can_create_agents=True,
        child_policy_mode=ChildPolicyMode.PREDEFINED,
        allowed_child_policies=("worker",),
    )
    agent = _make_harvest_agent("parent", sandbox.chat_router, policy)
    agent._sandbox = sandbox
    agent._policy = policy
    sandbox.register_agent("parent", agent, policy=policy)

    result = agent._tool_map["create_agent"](agent_id="child-1", policy_name="worker")
    import json
    data = json.loads(result)
    assert data["status"] == "created"
    child_handle = sandbox.get_agent_handle("child-1")
    assert child_handle.policy is not None
    assert child_handle.policy.name == "worker"


def test_create_agent_predefined_rejects_unlisted() -> None:
    registry = PolicyRegistry()
    registry.register(AgentPolicy(name="secret"))
    sandbox = BasicSandbox(config=_make_config(), policy_registry=registry)
    policy = AgentPolicy(
        name="supervisor",
        can_create_agents=True,
        child_policy_mode=ChildPolicyMode.PREDEFINED,
        allowed_child_policies=("worker",),
    )
    agent = _make_harvest_agent("parent", sandbox.chat_router, policy)
    agent._sandbox = sandbox
    agent._policy = policy
    sandbox.register_agent("parent", agent, policy=policy)

    result = agent._tool_map["create_agent"](agent_id="child-1", policy_name="secret")
    import json
    data = json.loads(result)
    assert "error" in data


def test_create_agent_define_mode() -> None:
    sandbox = BasicSandbox(config=_make_config())
    policy = AgentPolicy(
        name="orchestrator",
        can_create_agents=True,
        child_policy_mode=ChildPolicyMode.DEFINE,
    )
    agent = _make_harvest_agent("parent", sandbox.chat_router, policy)
    agent._sandbox = sandbox
    agent._policy = policy
    sandbox.register_agent("parent", agent, policy=policy)

    custom_policy = {
        "name": "custom-child",
        "allowed_tools": ["get_username"],
        "can_send_messages": True,
        "can_create_channel": False,
    }
    result = agent._tool_map["create_agent"](agent_id="child-1", policy=custom_policy)
    import json
    data = json.loads(result)
    assert data["status"] == "created"
    child_handle = sandbox.get_agent_handle("child-1")
    assert child_handle.policy is not None
    assert child_handle.policy.name == "custom-child"
