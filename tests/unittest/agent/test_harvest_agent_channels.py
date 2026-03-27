"""Tests for HarvestAgent channel tool wiring (event-driven path)."""

from __future__ import annotations

import json

from harvest.agent_sandbox.basic_sandbox import BasicSandbox
from harvest.agent_sandbox.channels import DMChannel, GroupChannel
from harvest.agent_sandbox.config import AgentSandboxConfig
from harvest.harvest_agent import HarvestAgent, HarvestAgentConfig
from harvest.policy import AgentPolicy


def _make_config() -> AgentSandboxConfig:
    return AgentSandboxConfig(runner_id="test", display_name="test")


def _make_agent(agent_id: str = "agent-a", policy: AgentPolicy | None = None) -> HarvestAgent:
    """Create a HarvestAgent for testing (no chat_router)."""
    config = HarvestAgentConfig(model="test-model", system_prompt="test")
    return HarvestAgent(config=config, agent_id=agent_id, policy=policy)


def _make_sandbox_with_agent(
    agent_id: str = "agent-a",
    policy: AgentPolicy | None = None,
) -> tuple[BasicSandbox, HarvestAgent]:
    """Create a sandbox and register a single agent."""
    sandbox = BasicSandbox(config=_make_config())
    agent = _make_agent(agent_id=agent_id, policy=policy)
    sandbox.register_agent(agent_id, agent, policy=policy)
    return sandbox, agent


def test_channel_tools_not_registered_without_sandbox() -> None:
    agent = _make_agent()
    tool_names = [t["function"]["name"] for t in agent._tools]
    assert "send_message" not in tool_names
    assert "read_messages" not in tool_names
    assert "list_channels" not in tool_names


def test_channel_tools_registered_with_sandbox() -> None:
    _sandbox, agent = _make_sandbox_with_agent()
    tool_names = [t["function"]["name"] for t in agent._tools]
    assert "send_message" in tool_names
    assert "read_messages" in tool_names
    assert "list_channels" in tool_names
    assert "leave_channel" in tool_names


def test_send_message_tool() -> None:
    sandbox = BasicSandbox(config=_make_config())
    agent_a = _make_agent(agent_id="agent-a")
    agent_b = _make_agent(agent_id="agent-b")
    sandbox.register_agent("agent-a", agent_a)
    sandbox.register_agent("agent-b", agent_b)

    dm = DMChannel(channel_id="dm:agent-a:agent-b", member_ids=["agent-a", "agent-b"])
    sandbox.chat_router.create_channel(dm)

    result = agent_a._tool_map["send_message"](channel_id="dm:agent-a:agent-b", content="hello")
    assert "sent" in result or "status" in result


def test_read_messages_tool() -> None:
    sandbox = BasicSandbox(config=_make_config())
    agent_a = _make_agent(agent_id="agent-a")
    agent_b = _make_agent(agent_id="agent-b")
    sandbox.register_agent("agent-a", agent_a)
    sandbox.register_agent("agent-b", agent_b)

    dm = DMChannel(channel_id="dm:agent-a:agent-b", member_ids=["agent-a", "agent-b"])
    sandbox.chat_router.create_channel(dm)

    sandbox.chat_router.send_message("agent-a", "dm:agent-a:agent-b", "hello", "msg-1")

    result = agent_b._tool_map["read_messages"]()
    assert "messages" in result


def test_list_channels_tool() -> None:
    sandbox, agent = _make_sandbox_with_agent(agent_id="agent-a")

    group = GroupChannel(channel_id="group-1", member_ids=["agent-a", "agent-b"])
    sandbox.chat_router.create_channel(group)

    result = agent._tool_map["list_channels"]()
    assert "group-1" in result


def test_leave_channel_tool() -> None:
    sandbox, agent = _make_sandbox_with_agent(agent_id="agent-a")

    group = GroupChannel(channel_id="group-1", member_ids=["agent-a", "agent-b"])
    sandbox.chat_router.create_channel(group)

    result = agent._tool_map["leave_channel"](channel_id="group-1")
    assert "left" in result

    channels = sandbox.chat_router.list_channels_for_agent("agent-a")
    assert len(channels) == 0


def test_shutdown_cleans_up() -> None:
    sandbox, agent = _make_sandbox_with_agent(agent_id="agent-a")
    agent.shutdown()
    assert agent._history == []


def test_policy_can_send_messages_false() -> None:
    policy = AgentPolicy(name="restricted", can_send_messages=False)
    _sandbox, agent = _make_sandbox_with_agent(policy=policy)
    tool_names = [t["function"]["name"] for t in agent._tools]
    assert "send_message" not in tool_names
    assert "read_messages" in tool_names
    assert "list_channels" in tool_names


def test_policy_can_create_channel_false() -> None:
    policy = AgentPolicy(name="basic")
    _sandbox, agent = _make_sandbox_with_agent(policy=policy)
    tool_names = [t["function"]["name"] for t in agent._tools]
    assert "create_channel" not in tool_names


def test_policy_can_create_channel_true() -> None:
    policy = AgentPolicy(name="creator", can_create_channel=True)
    _sandbox, agent = _make_sandbox_with_agent(policy=policy)
    tool_names = [t["function"]["name"] for t in agent._tools]
    assert "create_channel" in tool_names


def test_create_channel_tool() -> None:
    policy = AgentPolicy(name="creator", can_create_channel=True)
    sandbox, agent = _make_sandbox_with_agent(agent_id="agent-a", policy=policy)

    result = agent._tool_map["create_channel"](
        channel_id="new-group",
        channel_type="group",
        member_ids=["agent-a", "agent-b"],
    )
    assert "created" in result or "status" in result
    assert len(sandbox.chat_router.list_channels()) >= 1


def test_leave_channel_auto_cleanup() -> None:
    sandbox = BasicSandbox(config=_make_config())
    agent_a = _make_agent(agent_id="agent-a")
    agent_b = _make_agent(agent_id="agent-b")
    sandbox.register_agent("agent-a", agent_a)
    sandbox.register_agent("agent-b", agent_b)

    dm = DMChannel(channel_id="dm:agent-a:agent-b", member_ids=["agent-a", "agent-b"])
    sandbox.chat_router.create_channel(dm)

    agent_a._tool_map["leave_channel"](channel_id="dm:agent-a:agent-b")
    agent_b._tool_map["leave_channel"](channel_id="dm:agent-a:agent-b")
    assert sandbox.chat_router.list_channels() == []


def test_message_delivered_to_inbox() -> None:
    sandbox = BasicSandbox(config=_make_config())
    agent_a = _make_agent(agent_id="agent-a")
    agent_b = _make_agent(agent_id="agent-b")
    sandbox.register_agent("agent-a", agent_a)
    sandbox.register_agent("agent-b", agent_b)

    dm = DMChannel(channel_id="dm:agent-a:agent-b", member_ids=["agent-a", "agent-b"])
    sandbox.chat_router.create_channel(dm)

    sandbox.chat_router.send_message("agent-a", "dm:agent-a:agent-b", "hello", "msg-1")

    inbox = sandbox.chat_router.peek_inbox("agent-b")
    assert len(inbox) == 1
    assert inbox[0].content == "hello"
