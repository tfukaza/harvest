"""Phase 2 scaffolding tests for agent-runner endpoint and message schemas."""

from __future__ import annotations

from datetime import UTC


def test_endpoint_kinds_cover_scaffold_targets() -> None:
    """Endpoint kinds should cover the main sandbox topology concepts."""
    from harvest.agent_runner import EndpointKind

    assert EndpointKind.AGENT == "agent"
    assert EndpointKind.GROUP_CHAT == "group_chat"
    assert EndpointKind.MESSAGE_PROCESSOR == "message_processor"


def test_delivery_modes_capture_push_and_pull() -> None:
    """Delivery modes should remain explicit even before transport exists."""
    from harvest.agent_runner import DeliveryMode

    assert DeliveryMode.PUSH == "push"
    assert DeliveryMode.PULL == "pull"


def test_group_chat_definition_tracks_membership() -> None:
    """Group-chat scaffolding should preserve membership and addressing."""
    from harvest.agent_runner import EndpointAddress, EndpointKind, GroupChatDefinition

    group_chat = GroupChatDefinition(
        address=EndpointAddress(endpoint_id="group-1", kind=EndpointKind.GROUP_CHAT),
        member_ids=["agent-a", "agent-b"],
        description="Research cluster",
    )

    assert group_chat.address.endpoint_id == "group-1"
    assert group_chat.member_ids == ["agent-a", "agent-b"]
    assert group_chat.description == "Research cluster"


def test_sandbox_message_defaults_to_utc_timestamp() -> None:
    """Scaffold message records should use UTC timestamps by default."""
    from harvest.agent_runner import EndpointAddress, EndpointKind, SandboxMessage

    message = SandboxMessage(
        message_id="msg-1",
        sender=EndpointAddress(endpoint_id="agent-a", kind=EndpointKind.AGENT),
        recipient=EndpointAddress(endpoint_id="agent-b", kind=EndpointKind.AGENT),
        content="status",
    )

    assert message.created_at.tzinfo is UTC


def test_message_batch_groups_messages_for_one_recipient() -> None:
    """Batch scaffolding should group messages per endpoint."""
    from harvest.agent_runner import EndpointAddress, EndpointKind, MessageBatch, SandboxMessage

    recipient = EndpointAddress(endpoint_id="agent-a", kind=EndpointKind.AGENT)
    message = SandboxMessage(
        message_id="msg-1",
        sender=EndpointAddress(endpoint_id="agent-b", kind=EndpointKind.AGENT),
        recipient=recipient,
        content="hello",
    )
    batch = MessageBatch(recipient=recipient, messages=[message])

    assert batch.recipient is recipient
    assert batch.messages == [message]
