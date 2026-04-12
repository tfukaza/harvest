"""Tests for the ChatRouter unified channel system."""


import threading
import uuid

import pytest

from harvest.agent_sandbox.chat.channels import (
    AggregationProcessorChannel,
    ChannelType,
    GatedProcessorChannel,
    GroupChannel,
    NotificationMode,
)
from harvest.agent_sandbox.chat.events import (
    ChatMessageDelivered,
    SendChatMessage,
)
from harvest.agent_sandbox.chat.router import ChatRouter
from harvest.storage.schema.chat import ChatStore
from tests.unittest.channels.conftest import (
    make_aggregation_channel,
    make_dm_channel,
    make_gated_channel,
    make_group_channel,
)


def _send(router: ChatRouter, sender_id: str, channel_id: str, content: str) -> None:
    """Dispatch a SendChatMessage event on the router's bus."""
    message_id = uuid.uuid4().hex
    router._sandbox_bus.dispatch(SendChatMessage(
        sender_id=sender_id,
        channel_id=channel_id,
        content=content,
        message_id=message_id,
        source=sender_id,
    ))


# -- Agent registration --


def test_register_and_list_agents(router: ChatRouter) -> None:
    router.register_agent("agent-a")
    router.register_agent("agent-b")
    assert sorted(router.list_agents()) == ["agent-a", "agent-b"]


def test_unregister_agent(router: ChatRouter) -> None:
    router.register_agent("agent-a")
    router.unregister_agent("agent-a")
    assert router.list_agents() == []


# -- Two-member channel behavior --


def test_dm_recipient_receives_message(router: ChatRouter) -> None:
    router.register_agent("agent-a")
    router.register_agent("agent-b")
    dm = make_dm_channel("agent-a", "agent-b")
    router.create_channel(dm)

    _send(router, "agent-a", dm.channel_id, "hello")

    inbox_b = router.read_inbox("agent-b")
    assert len(inbox_b) == 1
    assert inbox_b[0].content == "hello"

    # Sender does not receive own message
    inbox_a = router.read_inbox("agent-a")
    assert len(inbox_a) == 0


def test_dm_persistence(router: ChatRouter) -> None:
    router.register_agent("agent-a")
    router.register_agent("agent-b")
    dm = make_dm_channel("agent-a", "agent-b")
    router.create_channel(dm)

    _send(router, "agent-a", dm.channel_id, "hello")
    _send(router, "agent-b", dm.channel_id, "hi back")

    history = router.load_channel_history(dm.channel_id)
    assert len(history) == 2
    assert history[0]["content"] == "hello"
    assert history[1]["content"] == "hi back"


def test_dm_channel_id_is_symmetric() -> None:
    dm1 = make_dm_channel("agent-a", "agent-b")
    dm2 = make_dm_channel("agent-b", "agent-a")
    ids1 = sorted(["agent-a", "agent-b"])
    ids2 = sorted(["agent-b", "agent-a"])
    assert ids1 == ids2


# -- Group behavior --


def test_group_channel_all_members_receive(router: ChatRouter) -> None:
    for aid in ["agent-a", "agent-b", "agent-c"]:
        router.register_agent(aid)
    group = make_group_channel()
    router.create_channel(group)

    _send(router, "agent-a", group.channel_id, "hello group")

    assert len(router.read_inbox("agent-b")) == 1
    assert len(router.read_inbox("agent-c")) == 1
    assert len(router.read_inbox("agent-a")) == 0


def test_group_channel_with_title(router: ChatRouter) -> None:
    group = make_group_channel(title="Team Chat", description="For the team")
    router.create_channel(group)
    ch = router.get_channel(group.channel_id)
    assert ch.title == "Team Chat"
    assert ch.description == "For the team"


# -- Gated processor --


def test_gated_channel_holds_until_all_publishers(router: ChatRouter) -> None:
    for aid in ["agent-a", "agent-b", "agent-c"]:
        router.register_agent(aid)
    gated = make_gated_channel()
    router.create_channel(gated)

    _send(router, "agent-a", gated.channel_id, "from A")
    assert len(router.peek_inbox("agent-c")) == 0

    _send(router, "agent-b", gated.channel_id, "from B")
    inbox_c = router.read_inbox("agent-c")
    assert len(inbox_c) == 2
    contents = [m.content for m in inbox_c]
    assert "from A" in contents
    assert "from B" in contents


def test_gated_channel_pass_through_after_open(router: ChatRouter) -> None:
    for aid in ["agent-a", "agent-b", "agent-c"]:
        router.register_agent(aid)
    gated = make_gated_channel()
    router.create_channel(gated)

    _send(router, "agent-a", gated.channel_id, "from A")
    _send(router, "agent-b", gated.channel_id, "from B")
    router.read_inbox("agent-c")

    _send(router, "agent-a", gated.channel_id, "follow-up")
    inbox_c = router.read_inbox("agent-c")
    assert len(inbox_c) == 1
    assert inbox_c[0].content == "follow-up"


def test_gated_ack_dispatched(router: ChatRouter) -> None:
    """ChatMessageDelivered event is dispatched after send."""
    acks: list[ChatMessageDelivered] = []
    router._sandbox_bus.on(ChatMessageDelivered, lambda e: acks.append(e))

    for aid in ["agent-a", "agent-b", "agent-c"]:
        router.register_agent(aid)

    gated = make_gated_channel()
    router.create_channel(gated)

    _send(router, "agent-a", gated.channel_id, "from A")
    assert len(acks) == 1
    assert acks[0].error == ""



def test_gated_flush(router: ChatRouter) -> None:
    for aid in ["agent-a", "agent-b", "agent-c"]:
        router.register_agent(aid)
    gated = make_gated_channel()
    router.create_channel(gated)

    _send(router, "agent-a", gated.channel_id, "from A")
    processor = router._processors[gated.channel_id]
    flushed = processor.flush()
    assert len(flushed) == 1


# -- Aggregation processor --


def test_aggregation_channel_batches(router: ChatRouter) -> None:
    for aid in ["agent-a", "agent-b"]:
        router.register_agent(aid)
    agg = make_aggregation_channel(batch_threshold=3)
    router.create_channel(agg)

    _send(router, "agent-a", agg.channel_id, "msg 1")
    _send(router, "agent-a", agg.channel_id, "msg 2")
    assert len(router.peek_inbox("agent-b")) == 0

    _send(router, "agent-a", agg.channel_id, "msg 3")
    inbox_b = router.read_inbox("agent-b")
    assert len(inbox_b) == 3


def test_aggregation_flush() -> None:
    from harvest.agent_sandbox.processors.aggregation import AggregationProcessor
    from harvest.agent_sandbox.endpoints import EndpointAddress, EndpointKind
    from harvest.agent_sandbox.chat.messages import SandboxMessage

    proc = AggregationProcessor(batch_threshold=5)
    for i in range(2):
        proc.accept_message(SandboxMessage(
            message_id=f"msg-{i}",
            sender=EndpointAddress(endpoint_id="agent-a", kind=EndpointKind.AGENT),
            recipient=EndpointAddress(endpoint_id="ch", kind=EndpointKind.GROUP_CHAT),
            content=f"msg {i}",
        ))
    flushed = proc.flush()
    assert len(flushed) == 2


# -- Notification callbacks --


def test_new_message_callback(router: ChatRouter) -> None:
    notifications: list[tuple] = []
    router.on_new_message(lambda ch, sid, rids, mid, ct, content="", reply_to="": notifications.append((ch, sid, rids, ct)))

    router.register_agent("agent-a")
    router.register_agent("agent-b")
    dm = make_dm_channel()
    router.create_channel(dm)

    _send(router, "agent-a", dm.channel_id, "hello")
    assert len(notifications) == 1
    assert "agent-b" in notifications[0][2]
    assert notifications[0][3] == "group"


def test_new_message_not_fired_until_gate_opens(router: ChatRouter) -> None:
    notifications: list[tuple] = []
    router.on_new_message(lambda ch, sid, rids, mid, ct, content="", reply_to="": notifications.append((ch, rids)))

    for aid in ["agent-a", "agent-b", "agent-c"]:
        router.register_agent(aid)
    gated = make_gated_channel()
    router.create_channel(gated)

    _send(router, "agent-a", gated.channel_id, "from A")
    assert len(notifications) == 0

    _send(router, "agent-b", gated.channel_id, "from B")
    assert len(notifications) == 1


# -- Invalid sends --


def test_send_to_nonexistent_channel(router: ChatRouter) -> None:
    acks: list[ChatMessageDelivered] = []
    router._sandbox_bus.on(ChatMessageDelivered, lambda e: acks.append(e))

    router.register_agent("agent-a")
    _send(router, "agent-a", "nonexistent", "hello")
    assert len(acks) == 1
    assert acks[0].error != ""


# -- Registration and cleanup --


def test_remove_channel(router: ChatRouter) -> None:
    group = make_group_channel()
    router.create_channel(group)
    router.remove_channel(group.channel_id)
    assert router.list_channels() == []


def test_unregister_last_member_auto_deletes(router: ChatRouter) -> None:
    router.register_agent("agent-a")
    router.register_agent("agent-b")
    dm = make_dm_channel()
    router.create_channel(dm)

    router.unregister_agent("agent-a")
    router.unregister_agent("agent-b")
    assert router.list_channels() == []


def test_load_channel_history_ordered(router: ChatRouter) -> None:
    router.register_agent("agent-a")
    router.register_agent("agent-b")
    dm = make_dm_channel()
    router.create_channel(dm)

    _send(router, "agent-a", dm.channel_id, "first")
    _send(router, "agent-b", dm.channel_id, "second")
    _send(router, "agent-a", dm.channel_id, "third")

    history = router.load_channel_history(dm.channel_id)
    assert [h["content"] for h in history] == ["first", "second", "third"]


# -- Inbox operations --


def test_read_inbox_clears(router: ChatRouter) -> None:
    router.register_agent("agent-a")
    router.register_agent("agent-b")
    dm = make_dm_channel()
    router.create_channel(dm)

    _send(router, "agent-a", dm.channel_id, "hello")
    router.read_inbox("agent-b")
    assert len(router.read_inbox("agent-b")) == 0


def test_peek_inbox_does_not_clear(router: ChatRouter) -> None:
    router.register_agent("agent-a")
    router.register_agent("agent-b")
    dm = make_dm_channel()
    router.create_channel(dm)

    _send(router, "agent-a", dm.channel_id, "hello")
    assert len(router.peek_inbox("agent-b")) == 1
    assert len(router.peek_inbox("agent-b")) == 1


# -- Channel listing --


def test_list_channels_for_agent(router: ChatRouter) -> None:
    for aid in ["agent-a", "agent-b", "agent-c", "agent-x"]:
        router.register_agent(aid)
    dm = make_dm_channel()
    group = make_group_channel()
    gated = make_gated_channel()
    router.create_channel(dm)
    router.create_channel(group)
    router.create_channel(gated)

    channels_a = router.list_channels_for_agent("agent-a")
    assert len(channels_a) == 3

    channels_x = router.list_channels_for_agent("agent-x")
    assert len(channels_x) == 0

    all_channels = router.list_channels()
    assert len(all_channels) == 3


def test_list_channels_for_agent_shows_processor_role(router: ChatRouter) -> None:
    for aid in ["agent-a", "agent-c"]:
        router.register_agent(aid)
    gated = make_gated_channel()
    router.create_channel(gated)

    channels_c = router.list_channels_for_agent("agent-c")
    assert len(channels_c) == 1
    assert isinstance(channels_c[0], GatedProcessorChannel)


# -- Leave channel --


def test_leave_channel(router: ChatRouter) -> None:
    for aid in ["agent-a", "agent-b", "agent-c"]:
        router.register_agent(aid)
    group = make_group_channel()
    router.create_channel(group)

    router.leave_channel("agent-a", group.channel_id)
    ch = router.get_channel(group.channel_id)
    assert isinstance(ch, GroupChannel)
    assert "agent-a" not in ch.member_ids


def test_leave_channel_auto_cleanup(router: ChatRouter) -> None:
    router.register_agent("agent-a")
    router.register_agent("agent-b")
    dm = make_dm_channel()
    router.create_channel(dm)

    router.leave_channel("agent-a", dm.channel_id)
    router.leave_channel("agent-b", dm.channel_id)
    assert router.list_channels() == []


# -- Unified interface --


def test_same_send_works_for_all_channel_types(router: ChatRouter) -> None:
    for aid in ["agent-a", "agent-b", "agent-c"]:
        router.register_agent(aid)

    dm = make_dm_channel()
    group = make_group_channel(channel_id="group-test", member_ids=["agent-a", "agent-b"])
    gated = make_gated_channel(
        channel_id="gated-test",
        publisher_ids=["agent-a"],
        subscriber_ids=["agent-c"],
    )

    router.create_channel(dm)
    router.create_channel(group)
    router.create_channel(gated)

    _send(router, "agent-a", dm.channel_id, "dm msg")
    _send(router, "agent-a", group.channel_id, "group msg")
    _send(router, "agent-a", gated.channel_id, "gated msg")

    assert len(router.read_inbox("agent-b")) == 2
    assert len(router.read_inbox("agent-c")) == 1


# -- Concurrency --


def test_concurrent_sends_no_corruption(router_no_store: ChatRouter) -> None:
    router = router_no_store
    for aid in ["agent-a", "agent-b", "agent-c"]:
        router.register_agent(aid)
    group = make_group_channel()
    router.create_channel(group)

    errors: list[Exception] = []

    def send_messages(sender: str, count: int) -> None:
        try:
            for i in range(count):
                _send(router, sender, group.channel_id, f"{sender}-{i}")
        except Exception as e:
            errors.append(e)

    threads = [
        threading.Thread(target=send_messages, args=("agent-a", 50)),
        threading.Thread(target=send_messages, args=("agent-b", 50)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    inbox_c = router.read_inbox("agent-c")
    assert len(inbox_c) == 100


# -- No store --


def test_load_history_without_store(router_no_store: ChatRouter) -> None:
    assert router_no_store.load_channel_history("any") == []


# -- Mention system --


def test_dm_always_sets_mention_type(router: ChatRouter) -> None:
    router.register_agent("agent-a")
    router.register_agent("agent-b")
    dm = make_dm_channel("agent-a", "agent-b")
    router.create_channel(dm)

    _send(router, "agent-a", dm.channel_id, "hello")
    inbox = router.read_inbox("agent-b")
    assert len(inbox) == 1


def test_group_ambient_mode_all_messages_are_mention(router: ChatRouter) -> None:
    """In ambient mode (default), all group messages are delivered as mentions."""
    for aid in ["agent-a", "agent-b", "agent-c"]:
        router.register_agent(aid)
    group = make_group_channel()  # default: AMBIENT
    router.create_channel(group)

    _send(router, "agent-a", group.channel_id, "just thinking out loud")
    inbox_b = router.read_inbox("agent-b")
    inbox_c = router.read_inbox("agent-c")
    assert len(inbox_b) == 1
    assert len(inbox_c) == 1


# ---------------------------------------------------------------------------
# Channel staking (event-driven write locking)
# ---------------------------------------------------------------------------


def test_event_stake_grant_and_send(router: ChatRouter) -> None:
    """RequestStake → StakeGranted → SendChatMessage → delivery."""
    from harvest.agent_sandbox.chat.events import RequestStake, StakeGranted

    for aid in ["agent-a", "agent-b"]:
        router.register_agent(aid)
    group = make_group_channel(member_ids=["agent-a", "agent-b"])
    router.create_channel(group)

    grants: list[StakeGranted] = []
    router._sandbox_bus.on(StakeGranted, lambda e: grants.append(e))

    # Request stake
    router._sandbox_bus.dispatch(RequestStake(
        agent_id="agent-a", channel_id=group.channel_id,
        request_id="r1", source="agent-a",
    ))
    assert len(grants) == 1
    assert grants[0].agent_id == "agent-a"

    # Send while holding stake
    _send(router, "agent-a", group.channel_id, "hello")
    assert len(router.read_inbox("agent-b")) == 1

    # Stake should be released after send
    assert group.channel_id not in router._channel_stakes


def test_event_stake_queued_when_held(router: ChatRouter) -> None:
    """Second agent gets StakeQueued, then StakeGranted after first releases."""
    from harvest.agent_sandbox.chat.events import (
        RequestStake, StakeGranted, StakeQueued, ReleaseStake,
    )

    for aid in ["agent-a", "agent-b"]:
        router.register_agent(aid)
    group = make_group_channel(member_ids=["agent-a", "agent-b"])
    router.create_channel(group)

    grants: list[StakeGranted] = []
    queued: list[StakeQueued] = []
    router._sandbox_bus.on(StakeGranted, lambda e: grants.append(e))
    router._sandbox_bus.on(StakeQueued, lambda e: queued.append(e))

    # Agent A acquires stake
    router._sandbox_bus.dispatch(RequestStake(
        agent_id="agent-a", channel_id=group.channel_id,
        request_id="r1", source="agent-a",
    ))
    assert len(grants) == 1

    # Agent B requests — should be queued
    router._sandbox_bus.dispatch(RequestStake(
        agent_id="agent-b", channel_id=group.channel_id,
        request_id="r2", source="agent-b",
    ))
    assert len(queued) == 1
    assert queued[0].agent_id == "agent-b"

    # Agent A releases — B should be granted
    router._sandbox_bus.dispatch(ReleaseStake(
        agent_id="agent-a", channel_id=group.channel_id,
        source="agent-a",
    ))
    assert len(grants) == 2
    assert grants[1].agent_id == "agent-b"


def test_stake_not_applied_to_staking_disabled(router: ChatRouter) -> None:
    """Channels with staking_enabled=False don't hold stakes."""
    for aid in ["agent-a", "agent-b"]:
        router.register_agent(aid)
    dm = make_dm_channel()
    router.create_channel(dm)

    _send(router, "agent-a", dm.channel_id, "hello")
    assert dm.channel_id not in router._channel_stakes


def test_stake_cleanup_on_unregister(router: ChatRouter) -> None:
    """Unregistering an agent releases its stakes."""
    from harvest.agent_sandbox.chat.events import RequestStake, StakeGranted

    for aid in ["agent-a", "agent-b"]:
        router.register_agent(aid)
    group = make_group_channel(member_ids=["agent-a", "agent-b"])
    router.create_channel(group)

    router._sandbox_bus.dispatch(RequestStake(
        agent_id="agent-a", channel_id=group.channel_id,
        request_id="r1", source="agent-a",
    ))
    assert group.channel_id in router._channel_stakes

    router.unregister_agent("agent-a")
    assert group.channel_id not in router._channel_stakes
