"""Phase 2 scaffolding tests for message-processor surfaces."""

from __future__ import annotations

from abc import ABC


def test_message_processor_contract_exists() -> None:
    """Phase 2 should add a dedicated message-processor scaffold contract."""
    from harvest.agent_runner import MessageProcessor

    assert issubclass(MessageProcessor, ABC)


def test_message_processor_contract_exposes_staging_hooks() -> None:
    """Processor scaffolding should expose the future staging lifecycle."""
    from harvest.agent_runner import MessageProcessor

    assert hasattr(MessageProcessor, "endpoint")
    assert hasattr(MessageProcessor, "process_message")
    assert hasattr(MessageProcessor, "flush")
    assert hasattr(MessageProcessor, "get_state_snapshot")


def test_processor_config_scaffolds_cover_common_patterns() -> None:
    """Phase 2 should define placeholder configuration for common processor types."""
    from harvest.agent_runner import AggregationProcessorConfig, GatedReleaseProcessorConfig

    aggregation = AggregationProcessorConfig(
        processor_id="agg-1",
        release_after_message_count=3,
        output_recipient_id="manager",
    )
    gated = GatedReleaseProcessorConfig(
        processor_id="gate-1",
        required_dependency_ids=("a", "b"),
        output_recipient_id="manager",
    )

    assert aggregation.release_after_message_count == 3
    assert gated.required_dependency_ids == ("a", "b")
    assert gated.output_recipient_id == "manager"
