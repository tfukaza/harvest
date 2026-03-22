"""Tests for the ChatRouter unified channel system."""

from __future__ import annotations

import threading
import uuid

import pytest

from harvest.agent_sandbox.channels import (
    AggregationProcessorChannel,
    ChannelType,
    DMChannel,
    GatedProcessorChannel,
    GroupChannel,
    NotificationMode,
)
from harvest.agent_sandbox.chat import ChatRouter
from harvest.storage.schema.chat import ChatStore
from tests.unittest.channels.conftest import (
    make_aggregation_channel,
    make_dm_channel,
    make_gated_channel,
    make_group_channel,
)


def _send(router: ChatRouter, sender_id: str, channel_id: str, content: str) -> dict:
    """Helper to send a message and return the result."""
    message_id = uuid.uuid4().hex
    return router.send_message(sender_id, channel_id, content, message_id)


# -- Agent registration --


def test_register_and_list_agents(router: ChatRouter) -> None:
    router.register_agent("agent-a")
    router.register_agent("agent-b")
    assert sorted(router.list_agents()) == ["agent-a", "agent-b"]


def test_unregister_agent(router: ChatRouter) -> None:
    router.register_agent("agent-a")
    router.unregister_agent("agent-a")
    assert router.list_agents() == []


# -- DM behavior --


def test_dm_recipient_receives_message(router: ChatRouter) -> None:
    router.register_agent("agent-a")
    router.register_agent("agent-b")
    dm = make_dm_channel("agent-a", "agent-b")
    router.create_channel(dm)

    result = _send(router, "agent-a", dm.channel_id, "hello")
    assert result["status"] == "ok"

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


def test_gated_ack_sent_immediately(router: ChatRouter) -> None:
    acks: list[tuple] = []

    for aid in ["agent-a", "agent-b", "agent-c"]:
        router.register_agent(aid)

    gated = make_gated_channel()
    router.create_channel(gated)
    router.on_message_delivered(lambda ch, mid, sid, ts, err: acks.append((ch, mid, sid, err)))

    _send(router, "agent-a", gated.channel_id, "from A")
    assert len(acks) == 1
    assert acks[0][3] == ""  # no error


def test_gated_non_publisher_denied(router: ChatRouter) -> None:
    for aid in ["agent-a", "agent-b", "agent-c"]:
        router.register_agent(aid)
    gated = make_gated_channel()
    router.create_channel(gated)

    result = _send(router, "agent-c", gated.channel_id, "not allowed")
    assert result["status"] == "error"
    assert result["error"] == "Permission denied"


def test_gated_subscriber_cannot_send(router: ChatRouter) -> None:
    for aid in ["agent-a", "agent-b", "agent-c"]:
        router.register_agent(aid)
    gated = make_gated_channel()
    router.create_channel(gated)

    result = _send(router, "agent-c", gated.channel_id, "not allowed")
    assert result["error"] == "Permission denied"


def test_gated_flush(router: ChatRouter) -> None:
    for aid in ["agent-a", "agent-b", "agent-c"]:
        router.register_agent(aid)
    gated = make_gated_channel()
    router.create_channel(gated)

    _send(router, "agent-a", gated.channel_id, "from A")
    # Message is buffered in the processor since gate hasn't opened
    # But the ChatRouter's send_message already called accept_message
    # which buffers it. Flush releases regardless of gate state.
    processor = router._processors[gated.channel_id]
    flushed = processor.flush()
    # The message was buffered by accept_message (gate not open), so flush returns it
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
    from harvest.agent_sandbox.aggregation_processor import AggregationProcessor
    from harvest.agent_sandbox.endpoints import EndpointAddress, EndpointKind
    from harvest.agent_sandbox.messages import SandboxMessage

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


def test_new_message_callback_for_dm(router: ChatRouter) -> None:
    notifications: list[tuple] = []
    router.on_new_message(lambda ch, sid, rids, mid, ct, content="", reply_to="": notifications.append((ch, sid, rids, ct)))

    router.register_agent("agent-a")
    router.register_agent("agent-b")
    dm = make_dm_channel()
    router.create_channel(dm)

    _send(router, "agent-a", dm.channel_id, "hello")
    assert len(notifications) == 1
    assert "agent-b" in notifications[0][2]
    assert notifications[0][3] == "dm"


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
    router.register_agent("agent-a")
    result = _send(router, "agent-a", "nonexistent", "hello")
    assert result["status"] == "error"
    assert result["error"] == "Channel not found"


def test_send_from_non_member(router: ChatRouter) -> None:
    router.register_agent("agent-a")
    router.register_agent("agent-b")
    router.register_agent("agent-x")
    dm = make_dm_channel()
    router.create_channel(dm)

    result = _send(router, "agent-x", dm.channel_id, "hello")
    assert result["error"] == "Permission denied"


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
                router.send_message(sender, group.channel_id, f"{sender}-{i}", uuid.uuid4().hex)
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
    assert inbox[0].metadata.get("mention_type") == "mention"


def test_group_ambient_mode_all_messages_are_mention(router: ChatRouter) -> None:
    """In ambient mode (default), all group messages are delivered as mentions."""
    for aid in ["agent-a", "agent-b", "agent-c"]:
        router.register_agent(aid)
    group = make_group_channel()  # default: AMBIENT
    router.create_channel(group)

    _send(router, "agent-a", group.channel_id, "just thinking out loud")
    inbox_b = router.read_inbox("agent-b")
    inbox_c = router.read_inbox("agent-c")
    assert inbox_b[0].metadata["mention_type"] == "mention"
    assert inbox_c[0].metadata["mention_type"] == "mention"


def test_group_mention_mode_no_mention_is_ambient(router: ChatRouter) -> None:
    """In mention mode, messages without @mentions are ambient for all."""
    for aid in ["agent-a", "agent-b", "agent-c"]:
        router.register_agent(aid)
    group = make_group_channel(notification_mode=NotificationMode.MENTION)
    router.create_channel(group)

    _send(router, "agent-a", group.channel_id, "just thinking out loud")
    inbox_b = router.read_inbox("agent-b")
    inbox_c = router.read_inbox("agent-c")
    assert inbox_b[0].metadata["mention_type"] == "ambient"
    assert inbox_c[0].metadata["mention_type"] == "ambient"


def test_group_mention_mode_at_name_mentions_specific(router: ChatRouter) -> None:
    """In mention mode, @agent-b only gives agent-b a mention."""
    for aid in ["agent-a", "agent-b", "agent-c"]:
        router.register_agent(aid)
    group = make_group_channel(notification_mode=NotificationMode.MENTION)
    router.create_channel(group)

    _send(router, "agent-a", group.channel_id, "hey @agent-b what do you think?")
    inbox_b = router.read_inbox("agent-b")
    inbox_c = router.read_inbox("agent-c")
    assert inbox_b[0].metadata["mention_type"] == "mention"
    assert inbox_c[0].metadata["mention_type"] == "ambient"


def test_group_mention_mode_at_here_mentions_all(router: ChatRouter) -> None:
    """In mention mode, @here gives everyone a mention."""
    for aid in ["agent-a", "agent-b", "agent-c"]:
        router.register_agent(aid)
    group = make_group_channel(notification_mode=NotificationMode.MENTION)
    router.create_channel(group)

    _send(router, "agent-a", group.channel_id, "@here check this out")
    inbox_b = router.read_inbox("agent-b")
    inbox_c = router.read_inbox("agent-c")
    assert inbox_b[0].metadata["mention_type"] == "mention"
    assert inbox_c[0].metadata["mention_type"] == "mention"


# ---------------------------------------------------------------------------
# Channel staking (write locking)
# ---------------------------------------------------------------------------


def test_group_stake_immediate_send(router: ChatRouter) -> None:
    """When lock is free, message sends immediately with status ok."""
    for aid in ["agent-a", "agent-b"]:
        router.register_agent(aid)
    group = make_group_channel(member_ids=["agent-a", "agent-b"])
    router.create_channel(group)

    result = _send(router, "agent-a", group.channel_id, "hello")
    assert result["status"] == "ok"
    assert len(router.read_inbox("agent-b")) == 1


def test_group_stake_blocks_and_returns_updated(router: ChatRouter) -> None:
    """Second sender blocks, then gets channel_updated with new messages."""
    import time as _time

    for aid in ["agent-a", "agent-b", "agent-c"]:
        router.register_agent(aid)
    group = make_group_channel(member_ids=["agent-a", "agent-b", "agent-c"])
    router.create_channel(group)

    results: dict[str, dict] = {}
    send_started = threading.Event()
    send_can_proceed = threading.Event()

    original_send = router._send_message_internal

    def _slow_send(sender_id, channel_id, content, message_id, **kwargs):
        if sender_id == "agent-a":
            send_started.set()
            send_can_proceed.wait(timeout=5.0)
        return original_send(sender_id, channel_id, content, message_id, **kwargs)

    router._send_message_internal = _slow_send

    def send_a():
        results["a"] = router.send_message("agent-a", group.channel_id, "from A", "msg-a")

    def send_b():
        send_started.wait(timeout=5.0)
        results["b"] = router.send_message("agent-b", group.channel_id, "from B", "msg-b")

    t_a = threading.Thread(target=send_a)
    t_b = threading.Thread(target=send_b)
    t_a.start()
    t_b.start()

    _time.sleep(0.2)
    send_can_proceed.set()

    t_a.join(timeout=5.0)
    t_b.join(timeout=5.0)

    assert results["a"]["status"] == "ok"
    assert results["b"]["status"] == "channel_updated"
    assert "new_messages" in results["b"]
    assert "hint" in results["b"]


def test_group_stake_second_send_succeeds(router: ChatRouter) -> None:
    """After channel_updated, the agent holds the lock and can send."""
    import time as _time

    for aid in ["agent-a", "agent-b"]:
        router.register_agent(aid)
    group = make_group_channel(member_ids=["agent-a", "agent-b"])
    router.create_channel(group)

    results: dict[str, dict] = {}
    send_started = threading.Event()
    send_can_proceed = threading.Event()

    original_send = router._send_message_internal

    def _slow_send(sender_id, channel_id, content, message_id, **kwargs):
        if sender_id == "agent-a" and content == "first":
            send_started.set()
            send_can_proceed.wait(timeout=5.0)
        return original_send(sender_id, channel_id, content, message_id, **kwargs)

    router._send_message_internal = _slow_send

    def send_a():
        results["a"] = router.send_message("agent-a", group.channel_id, "first", "msg-a1")

    def send_b():
        send_started.wait(timeout=5.0)
        results["b1"] = router.send_message("agent-b", group.channel_id, "stale", "msg-b1")
        results["b2"] = router.send_message("agent-b", group.channel_id, "updated", "msg-b2")

    t_a = threading.Thread(target=send_a)
    t_b = threading.Thread(target=send_b)
    t_a.start()
    t_b.start()

    _time.sleep(0.2)
    send_can_proceed.set()

    t_a.join(timeout=5.0)
    t_b.join(timeout=5.0)

    assert results["a"]["status"] == "ok"
    assert results["b1"]["status"] == "channel_updated"
    assert results["b2"]["status"] == "ok"


def test_stake_not_applied_to_dm(router: ChatRouter) -> None:
    """DM channels bypass staking entirely."""
    for aid in ["agent-a", "agent-b"]:
        router.register_agent(aid)
    dm = make_dm_channel()
    router.create_channel(dm)

    result = _send(router, "agent-a", dm.channel_id, "hello")
    assert result["status"] == "ok"
    assert dm.channel_id not in router._channel_stakes


def test_same_agent_reacquire(router: ChatRouter) -> None:
    """Agent holding the lock can send immediately."""
    for aid in ["agent-a", "agent-b"]:
        router.register_agent(aid)
    group = make_group_channel(member_ids=["agent-a", "agent-b"])
    router.create_channel(group)

    router._acquire_stake(group.channel_id, "agent-a")
    result = router.send_message("agent-a", group.channel_id, "hello", "msg-1")
    assert result["status"] == "ok"


def test_stake_cleanup_on_unregister(router: ChatRouter) -> None:
    """Unregistering an agent releases its stakes."""
    for aid in ["agent-a", "agent-b"]:
        router.register_agent(aid)
    group = make_group_channel(member_ids=["agent-a", "agent-b"])
    router.create_channel(group)

    router._acquire_stake(group.channel_id, "agent-a")
    assert group.channel_id in router._channel_stakes

    router.unregister_agent("agent-a")
    assert group.channel_id not in router._channel_stakes
