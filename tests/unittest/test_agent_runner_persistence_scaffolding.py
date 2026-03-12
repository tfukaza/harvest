"""Phase 2 scaffolding tests for agent-runner persistence surfaces."""

from __future__ import annotations

from abc import ABC
from datetime import UTC


def test_local_agent_store_contract_exists() -> None:
    """Phase 2 should add a local persistence contract for runner state."""
    from harvest.agent_runner import LocalAgentStore

    assert issubclass(LocalAgentStore, ABC)


def test_local_agent_store_exposes_expected_records() -> None:
    """The persistence contract should name the key record types explicitly."""
    from harvest.agent_runner import LocalAgentStore

    assert hasattr(LocalAgentStore, "save_reasoning_record")
    assert hasattr(LocalAgentStore, "save_tool_result_record")
    assert hasattr(LocalAgentStore, "save_session_state_record")
    assert hasattr(LocalAgentStore, "save_recovery_snapshot")
    assert hasattr(LocalAgentStore, "load_recovery_snapshot")


def test_persistence_records_default_to_utc_timestamps() -> None:
    """Scaffold persistence records should default to UTC timestamps."""
    from harvest.agent_runner import ReasoningRecord, SessionStateRecord, ToolResultRecord

    reasoning = ReasoningRecord(agent_id="agent-a", entry={"thought": "x"})
    tool_result = ToolResultRecord(agent_id="agent-a", tool_name="search", result={"ok": True})
    session_state = SessionStateRecord(runner_id="runner-a", state={"phase": "idle"})

    assert reasoning.recorded_at.tzinfo is UTC
    assert tool_result.recorded_at.tzinfo is UTC
    assert session_state.recorded_at.tzinfo is UTC


def test_recovery_snapshot_tracks_runtime_topology() -> None:
    """Recovery scaffolding should name the future topology recovery inputs."""
    from harvest.agent_runner import RecoverySnapshot

    snapshot = RecoverySnapshot(
        runner_id="runner-a",
        agent_ids=["agent-a"],
        processor_ids=["processor-a"],
        group_chat_ids=["group-a"],
    )

    assert snapshot.runner_id == "runner-a"
    assert snapshot.agent_ids == ["agent-a"]
    assert snapshot.processor_ids == ["processor-a"]
    assert snapshot.group_chat_ids == ["group-a"]
