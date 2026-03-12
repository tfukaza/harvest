"""Scaffolding tests for the Agent Runner surface."""

from __future__ import annotations

from abc import ABC


def test_agent_runner_contract_exists() -> None:
    """Harvest should expose a dedicated scaffold contract for agent runners."""
    from harvest.agent_runner import AgentRunner

    assert issubclass(AgentRunner, ABC)


def test_agent_runner_refines_runtime_contract() -> None:
    """AgentRunner should narrow the generic Runtime contract for sandbox work."""
    from harvest.agent_runner import AgentRunner
    from harvest.runtime import Runtime

    assert issubclass(AgentRunner, Runtime)


def test_agent_runner_exposes_topology_methods() -> None:
    """AgentRunner scaffolding should expose sandbox topology surfaces."""
    from harvest.agent_runner import AgentRunner

    assert hasattr(AgentRunner, "config")
    assert hasattr(AgentRunner, "register_processor")
    assert hasattr(AgentRunner, "list_processors")
    assert hasattr(AgentRunner, "remove_processor")
    assert hasattr(AgentRunner, "register_group_chat")
    assert hasattr(AgentRunner, "list_group_chats")
    assert hasattr(AgentRunner, "remove_group_chat")
    assert hasattr(AgentRunner, "list_endpoints")
    assert hasattr(AgentRunner, "get_supported_delivery_modes")


def test_agent_runner_scaffold_has_configuration_and_factory() -> None:
    """Phase 2 scaffolding should define construction seams without implementation."""
    from harvest.agent_runner import AgentRunnerConfig, AgentRunnerFactory

    config = AgentRunnerConfig(runner_id="sandbox-1", display_name="Sandbox")

    assert issubclass(AgentRunnerFactory, ABC)
    assert config.runner_id == "sandbox-1"
    assert config.display_name == "Sandbox"
    assert config.sandbox_namespace == "sandbox"


def test_agent_runner_is_exported_from_package_root() -> None:
    """The top-level package should expose the scaffold AgentRunner contract."""
    from harvest import AgentRunner as exported_agent_runner
    from harvest.agent_runner import AgentRunner

    assert exported_agent_runner is AgentRunner
