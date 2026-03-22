"""Tests for HarvestAgent channel tool wiring."""

from __future__ import annotations

from harvest.agent_sandbox.channels import DMChannel, GroupChannel
from harvest.agent_sandbox.chat import ChatRouter
from harvest.harvest_agent import HarvestAgent, HarvestAgentConfig
from harvest.policy import AgentPolicy


def _make_agent(
    agent_id: str = "agent-a",
    chat_router: ChatRouter | None = None,
    policy: AgentPolicy | None = None,
) -> HarvestAgent:
    """Create a HarvestAgent for testing."""
    config = HarvestAgentConfig(model="test-model", system_prompt="test")
    return HarvestAgent(
        config=config,
        agent_id=agent_id,
        chat_router=chat_router,
        policy=policy,
    )


def test_channel_tools_not_registered_without_router() -> None:
    agent = _make_agent()
    tool_names = [t["function"]["name"] for t in agent._tools]
    assert "send_message" not in tool_names
    assert "read_messages" not in tool_names
    assert "list_channels" not in tool_names


def test_channel_tools_registered_with_router() -> None:
    router = ChatRouter()
    agent = _make_agent(chat_router=router)
    tool_names = [t["function"]["name"] for t in agent._tools]
    assert "send_message" in tool_names
    assert "read_messages" in tool_names
    assert "list_channels" in tool_names
    assert "leave_channel" in tool_names


def test_send_message_tool(router=None) -> None:
    router = ChatRouter()
    agent_a = _make_agent(agent_id="agent-a", chat_router=router)
    agent_b = _make_agent(agent_id="agent-b", chat_router=router)

    dm = DMChannel(channel_id="dm:agent-a:agent-b", member_ids=["agent-a", "agent-b"])
    router.create_channel(dm)

    result = agent_a._tool_map["send_message"](channel_id="dm:agent-a:agent-b", content="hello")
    assert "sent" in result

    inbox = router.read_inbox("agent-b")
    assert len(inbox) == 1
    assert inbox[0].content == "hello"


def test_read_messages_tool() -> None:
    router = ChatRouter()
    agent_a = _make_agent(agent_id="agent-a", chat_router=router)
    agent_b = _make_agent(agent_id="agent-b", chat_router=router)

    dm = DMChannel(channel_id="dm:agent-a:agent-b", member_ids=["agent-a", "agent-b"])
    router.create_channel(dm)

    router.send_message("agent-a", "dm:agent-a:agent-b", "hello", "msg-1")

    result = agent_b._tool_map["read_messages"]()
    assert "unread" in result


def test_list_channels_tool() -> None:
    router = ChatRouter()
    agent = _make_agent(agent_id="agent-a", chat_router=router)

    group = GroupChannel(channel_id="group-1", member_ids=["agent-a", "agent-b"])
    router.create_channel(group)

    result = agent._tool_map["list_channels"]()
    assert "group-1" in result


def test_leave_channel_tool() -> None:
    router = ChatRouter()
    agent = _make_agent(agent_id="agent-a", chat_router=router)

    group = GroupChannel(channel_id="group-1", member_ids=["agent-a", "agent-b"])
    router.create_channel(group)

    result = agent._tool_map["leave_channel"](channel_id="group-1")
    assert "left" in result

    channels = router.list_channels_for_agent("agent-a")
    assert len(channels) == 0


def test_shutdown_unregisters_from_router() -> None:
    router = ChatRouter()
    agent = _make_agent(agent_id="agent-a", chat_router=router)
    assert "agent-a" in router.list_agents()

    agent.shutdown()
    assert "agent-a" not in router.list_agents()
    assert agent._history == []


def test_policy_can_send_messages_false() -> None:
    router = ChatRouter()
    policy = AgentPolicy(name="restricted", can_send_messages=False)
    agent = _make_agent(chat_router=router, policy=policy)
    tool_names = [t["function"]["name"] for t in agent._tools]
    assert "send_message" not in tool_names
    assert "read_messages" in tool_names
    assert "list_channels" in tool_names


def test_policy_can_create_channel_false() -> None:
    router = ChatRouter()
    policy = AgentPolicy(name="basic")
    agent = _make_agent(chat_router=router, policy=policy)
    tool_names = [t["function"]["name"] for t in agent._tools]
    assert "create_channel" not in tool_names


def test_policy_can_create_channel_true() -> None:
    router = ChatRouter()
    policy = AgentPolicy(name="creator", can_create_channel=True)
    agent = _make_agent(chat_router=router, policy=policy)
    tool_names = [t["function"]["name"] for t in agent._tools]
    assert "create_channel" in tool_names


def test_create_channel_tool() -> None:
    router = ChatRouter()
    policy = AgentPolicy(name="creator", can_create_channel=True)
    agent = _make_agent(agent_id="agent-a", chat_router=router, policy=policy)

    result = agent._tool_map["create_channel"](
        channel_id="new-group",
        channel_type="group",
        member_ids=["agent-a", "agent-b"],
        title="Test Group",
    )
    assert "created" in result
    assert len(router.list_channels()) == 1


def test_leave_channel_auto_cleanup() -> None:
    router = ChatRouter()
    agent_a = _make_agent(agent_id="agent-a", chat_router=router)
    agent_b = _make_agent(agent_id="agent-b", chat_router=router)

    dm = DMChannel(channel_id="dm:agent-a:agent-b", member_ids=["agent-a", "agent-b"])
    router.create_channel(dm)

    agent_a._tool_map["leave_channel"](channel_id="dm:agent-a:agent-b")
    agent_b._tool_map["leave_channel"](channel_id="dm:agent-a:agent-b")
    assert router.list_channels() == []


def test_message_delivered_to_inbox() -> None:
    router = ChatRouter()
    _make_agent(agent_id="agent-a", chat_router=router)
    _make_agent(agent_id="agent-b", chat_router=router)

    dm = DMChannel(channel_id="dm:agent-a:agent-b", member_ids=["agent-a", "agent-b"])
    router.create_channel(dm)

    router.send_message("agent-a", "dm:agent-a:agent-b", "hello", "msg-1")

    # agent-b should have a message in its inbox
    inbox = router.peek_inbox("agent-b")
    assert len(inbox) == 1
    assert inbox[0].content == "hello"
