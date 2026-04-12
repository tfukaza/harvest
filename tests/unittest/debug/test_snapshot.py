"""Tests for snapshot dataclasses."""


import dataclasses
import json

from harvest.debug.snapshot import AgentInfo, ChannelInfo, MessageInfo, SandboxSnapshot


def test_snapshot_serializes_to_json() -> None:
    snap = SandboxSnapshot(
        sandbox_id="sb-1",
        display_name="Test",
        agents=[
            AgentInfo(
                agent_id="a1",
                agent_type="HarvestAgent",
                thread_alive=True,
                policy_summary={"can_send_messages": True},
            )
        ],
        channels=[
            ChannelInfo(
                channel_id="ch-1",
                channel_type="group",
                title="Team",
                member_ids=["a1", "a2"],
            )
        ],
        recent_messages=[
            MessageInfo(
                message_id="m1",
                channel_id="ch-1",
                sender_id="a1",
                content="hello",
                timestamp="2026-03-21T12:00:00Z",
            )
        ],
        snapshot_timestamp="2026-03-21T12:00:00Z",
    )
    data = dataclasses.asdict(snap)
    text = json.dumps(data)
    assert "sb-1" in text
    assert "HarvestAgent" in text
    assert "hello" in text


def test_snapshot_roundtrip() -> None:
    snap = SandboxSnapshot(
        sandbox_id="sb-2",
        display_name="Round",
        agents=[],
        channels=[],
        recent_messages=[],
        snapshot_timestamp="2026-03-21T00:00:00Z",
    )
    data = dataclasses.asdict(snap)
    text = json.dumps(data)
    restored = json.loads(text)
    assert restored["sandbox_id"] == "sb-2"
    assert restored["display_name"] == "Round"
    assert restored["agents"] == []


def test_snapshot_all_fields_present() -> None:
    snap = SandboxSnapshot(
        sandbox_id="x",
        display_name="y",
        snapshot_timestamp="t",
    )
    data = dataclasses.asdict(snap)
    assert "sandbox_id" in data
    assert "display_name" in data
    assert "agents" in data
    assert "channels" in data
    assert "recent_messages" in data
    assert "snapshot_timestamp" in data
