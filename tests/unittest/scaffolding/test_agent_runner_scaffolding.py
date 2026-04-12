"""Scaffolding tests for the Agent Sandbox surface."""


from abc import ABC


def test_agent_sandbox_contract_exists() -> None:
    """Harvest should expose a dedicated scaffold contract for agent sandboxes."""
    from harvest.agent_sandbox import AgentSandbox

    assert issubclass(AgentSandbox, ABC)


def test_agent_sandbox_refines_runtime_contract() -> None:
    """AgentSandbox should narrow the generic Runtime contract for sandbox work."""
    from harvest.agent_sandbox import AgentSandbox
    from harvest.core.runtime import Runtime

    assert issubclass(AgentSandbox, Runtime)


def test_agent_sandbox_exposes_topology_methods() -> None:
    """AgentSandbox scaffolding should expose sandbox topology surfaces."""
    from harvest.agent_sandbox import AgentSandbox

    assert hasattr(AgentSandbox, "config")
    assert hasattr(AgentSandbox, "register_processor")
    assert hasattr(AgentSandbox, "list_processors")
    assert hasattr(AgentSandbox, "remove_processor")
    assert hasattr(AgentSandbox, "register_group_chat")
    assert hasattr(AgentSandbox, "list_group_chats")
    assert hasattr(AgentSandbox, "remove_group_chat")
    assert hasattr(AgentSandbox, "list_endpoints")
    assert hasattr(AgentSandbox, "get_supported_delivery_modes")


def test_agent_sandbox_scaffold_has_configuration_and_factory() -> None:
    """Phase 2 scaffolding should define construction seams without implementation."""
    from harvest.agent_sandbox import AgentSandboxConfig, AgentSandboxFactory

    config = AgentSandboxConfig(runner_id="sandbox-1", display_name="Sandbox")

    assert issubclass(AgentSandboxFactory, ABC)
    assert config.runner_id == "sandbox-1"
    assert config.display_name == "Sandbox"
    assert config.sandbox_namespace == "sandbox"


def test_agent_sandbox_is_exported_from_package_root() -> None:
    """The top-level package should expose the scaffold AgentSandbox contract."""
    from harvest import AgentSandbox as exported_agent_sandbox
    from harvest.agent_sandbox import AgentSandbox

    assert exported_agent_sandbox is AgentSandbox
