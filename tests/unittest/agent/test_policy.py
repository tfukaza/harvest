"""Tests for the agent policy system."""


import tempfile
from pathlib import Path

import pytest

from harvest.core.policy import AgentPolicy, ChildPolicyMode
from harvest.core.policy_registry import PolicyRegistry


def test_policy_defaults() -> None:
    policy = AgentPolicy(name="test")
    assert policy.can_send_messages is True
    assert policy.can_create_channel is False
    assert policy.can_create_agents is False
    assert policy.child_policy_mode == ChildPolicyMode.NONE
    assert policy.allowed_tools == frozenset()


def test_policy_frozen() -> None:
    policy = AgentPolicy(name="test")
    with pytest.raises(AttributeError):
        policy.name = "changed"  # type: ignore[misc]


def test_child_policy_modes() -> None:
    assert ChildPolicyMode.NONE.value == "none"
    assert ChildPolicyMode.CLONE.value == "clone"
    assert ChildPolicyMode.PREDEFINED.value == "predefined"
    assert ChildPolicyMode.DEFINE.value == "define"


def test_registry_load_yaml() -> None:
    yaml_content = """
policies:
  worker:
    allowed_tools:
      - get_username
    can_send_messages: true
    can_create_channel: false
    can_create_agents: false
    child_policy_mode: none
  supervisor:
    allowed_tools:
      - get_username
      - leave_channel
    can_send_messages: true
    can_create_channel: true
    can_create_agents: true
    child_policy_mode: predefined
    allowed_child_policies:
      - worker
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        registry = PolicyRegistry(config_path=f.name)

    worker = registry.get("worker")
    assert worker.name == "worker"
    assert "get_username" in worker.allowed_tools
    assert worker.can_send_messages is True
    assert worker.can_create_agents is False

    supervisor = registry.get("supervisor")
    assert supervisor.can_create_channel is True
    assert supervisor.child_policy_mode == ChildPolicyMode.PREDEFINED
    assert "worker" in supervisor.allowed_child_policies


def test_registry_get_missing_raises() -> None:
    registry = PolicyRegistry()
    with pytest.raises(KeyError):
        registry.get("nonexistent")


def test_registry_list_policies() -> None:
    registry = PolicyRegistry()
    registry.register(AgentPolicy(name="alpha"))
    registry.register(AgentPolicy(name="beta"))
    assert registry.list_policies() == ["alpha", "beta"]


def test_registry_programmatic_register() -> None:
    registry = PolicyRegistry()
    policy = AgentPolicy(name="custom", allowed_tools=frozenset(["tool_a"]))
    registry.register(policy)
    assert registry.get("custom") is policy


# ---------------------------------------------------------------------------
# Policy enforcement via HarvestAgent tool registration
# ---------------------------------------------------------------------------


def _make_sandbox_agent(
    agent_id: str = "a",
    policy: AgentPolicy | None = None,
) -> tuple:
    """Helper: create a sandbox + registered agent for policy tests."""
    from harvest.agent_sandbox.basic_sandbox import BasicSandbox
    from harvest.agent_sandbox.config import AgentSandboxConfig
    from harvest.harvest_agent import HarvestAgent, HarvestAgentConfig

    sandbox = BasicSandbox(
        config=AgentSandboxConfig(runner_id="test", display_name="test"),
    )
    config = HarvestAgentConfig(model="test-model", system_prompt="test")
    agent = HarvestAgent(config=config, agent_id=agent_id, policy=policy)
    sandbox.register_agent(agent_id, agent, policy=policy)
    return sandbox, agent


def test_policy_blocks_disallowed_tool() -> None:
    """Agent with a policy missing a tool gets an error when invoking it."""
    policy = AgentPolicy(
        name="restricted",
        allowed_tools=frozenset(["get_username"]),
        can_send_messages=False,
        can_create_channel=False,
    )
    _sandbox, agent = _make_sandbox_agent(policy=policy)

    # send_message should not be registered because can_send_messages=False
    assert "send_message" not in agent._tool_map
    # create_channel should not be registered because can_create_channel=False
    assert "create_channel" not in agent._tool_map


def test_policy_allows_permitted_tool() -> None:
    """Agent with a tool in allowed_tools can invoke it normally."""
    policy = AgentPolicy(
        name="sender",
        allowed_tools=frozenset(["get_username", "send_message"]),
        can_send_messages=True,
    )
    _sandbox, agent = _make_sandbox_agent(policy=policy)

    assert "send_message" in agent._tool_map
    assert "get_username" in agent._tool_map


def test_policy_receive_without_send() -> None:
    """Agent with can_send_messages=False can still read messages and list channels."""
    policy = AgentPolicy(name="reader", can_send_messages=False)
    _sandbox, agent = _make_sandbox_agent(policy=policy)

    assert "send_message" not in agent._tool_map
    assert "read_messages" in agent._tool_map
    assert "list_channels" in agent._tool_map


def test_policy_participate_without_create() -> None:
    """Agent with can_create_channel=False can still participate in existing channels."""
    from harvest.agent_sandbox.chat.channels import GroupChannel

    policy = AgentPolicy(name="participant", can_create_channel=False, can_send_messages=True)
    sandbox, agent = _make_sandbox_agent(policy=policy)

    assert "create_channel" not in agent._tool_map
    assert "send_message" in agent._tool_map
    assert "list_channels" in agent._tool_map

    # Can participate in a channel created externally
    group = GroupChannel(channel_id="grp", member_ids=["a", "b"])
    sandbox.chat_router.create_channel(group)
    channels = sandbox.chat_router.list_channels_for_agent("a")
    assert len(channels) == 1
