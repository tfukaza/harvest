"""Contract tests for the Agent abstraction."""


import inspect
from abc import ABC


def test_agent_contract_exists() -> None:
    """Harvest should expose an Agent contract."""
    from harvest.core.agent import Agent

    assert issubclass(Agent, ABC)


def test_agent_contract_is_framework_agnostic() -> None:
    """Agent should not expose framework plumbing on its public contract."""
    from harvest.core.agent import Agent

    assert not hasattr(Agent, "event_bus")
    assert not hasattr(Agent, "service_registry")
    assert not hasattr(Agent, "resource_registry")


def test_agent_contract_exposes_loop_facing_methods() -> None:
    """Agent should define loop-facing methods rather than framework wiring methods."""
    from harvest.core.agent import Agent

    assert hasattr(Agent, "step")
    assert hasattr(Agent, "reset")
    step_signature = inspect.signature(Agent.step)
    assert "runtime" not in step_signature.parameters
    assert "event_bus" not in step_signature.parameters


def test_agent_contract_tracks_internal_history() -> None:
    """Agent should expose reasoning history without leaking framework concerns."""
    from harvest.core.agent import Agent

    assert hasattr(Agent, "get_reasoning_history")
