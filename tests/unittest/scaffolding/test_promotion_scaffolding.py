"""Scaffolding tests for sandbox promotion policy surfaces."""


from abc import ABC


def test_promotion_policy_contract_exists() -> None:
    """Harvest should expose a promotion-policy scaffold contract."""
    from harvest.agent_sandbox import PromotionPolicy

    assert issubclass(PromotionPolicy, ABC)


def test_promotion_policy_exposes_evaluation_hook() -> None:
    """Promotion scaffolding should expose one evaluation entrypoint."""
    from harvest.agent_sandbox import PromotionPolicy

    assert hasattr(PromotionPolicy, "evaluate")


def test_promotion_candidate_and_decision_capture_scaffold_data() -> None:
    """Promotion scaffolding should preserve event metadata and policy output."""
    from harvest.agent_sandbox import PromotionCandidate, PromotionDecision, PromotionTarget

    candidate = PromotionCandidate(
        event_type="tool_result",
        payload={"result": "ok"},
        source_endpoint_id="agent-a",
        severity="serious",
    )
    decision = PromotionDecision(
        should_promote=True,
        reason="framework-visible failure",
        promoted_event_type="system_failure",
    )

    assert candidate.severity == "serious"
    assert decision.should_promote is True
    assert decision.target == PromotionTarget.ORCHESTRATOR_EVENT_BUS
    assert decision.promoted_event_type == "system_failure"
