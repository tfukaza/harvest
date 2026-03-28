"""Contract tests for the Runtime abstraction."""


from abc import ABC


def test_runtime_contract_exists() -> None:
    """Harvest should expose a Runtime contract."""
    from harvest.core.runtime import Runtime

    assert issubclass(Runtime, ABC)


def test_runtime_hosts_agents() -> None:
    """Runtime should be the sandbox boundary that hosts one or more agents."""
    from harvest.core.runtime import Runtime

    assert hasattr(Runtime, "register_agent")
    assert hasattr(Runtime, "list_agents")
    assert hasattr(Runtime, "remove_agent")


def test_runtime_owns_framework_integration() -> None:
    """Runtime should own framework integration responsibilities for hosted agents."""
    from harvest.core.runtime import Runtime

    assert hasattr(Runtime, "bind_resource")
    assert hasattr(Runtime, "bind_tool")
    assert hasattr(Runtime, "publish_event")
    assert hasattr(Runtime, "handle_event")


def test_runtime_controls_lifecycle() -> None:
    """Runtime should own execution lifecycle instead of the Agent."""
    from harvest.core.runtime import Runtime

    assert hasattr(Runtime, "start")
    assert hasattr(Runtime, "stop")
    assert hasattr(Runtime, "health_check")
