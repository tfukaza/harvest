"""Tests for Service with multiple roles registered in a single sandbox."""


import json
from typing import Any

import pytest

from harvest.agent_sandbox.services.router import SandboxServiceRouter
from harvest.interfaces.examples.mock_full_service import MockFullService
from harvest.interfaces.service import ServiceRole
from harvest.core.policy import AgentPolicy
from harvest.interfaces.service import ServicePermission


def test_multi_role_service_registers_without_errors() -> None:
    router = SandboxServiceRouter(sandbox_id="test")
    svc = MockFullService("multi-svc")
    router.register_service(svc)
    assert "multi-svc" in router.list_services()


def test_multi_role_service_exposes_data_and_action_tools() -> None:
    router = SandboxServiceRouter(sandbox_id="test")
    svc = MockFullService("multi-svc")
    router.register_service(svc)

    names = router._tool_registry.list_tool_names()
    assert "full_service_lookup" in names
    assert "full_service_notify" in names


def test_multi_role_service_data_fetch_works() -> None:
    router = SandboxServiceRouter(sandbox_id="test")
    svc = MockFullService("multi-svc")
    router.register_service(svc)

    policy = AgentPolicy(
        name="all-access",
        allowed_services=(ServicePermission("multi-svc"),),
    )
    _, tool_map = router.make_service_tools("agent-1", policy)
    assert "fetch_data" in tool_map
    result = json.loads(tool_map["fetch_data"]("multi-svc", "lookup", {"key": "x"}))
    assert "error" not in result
    assert result["key"] == "x"


def test_multi_role_service_action_works() -> None:
    router = SandboxServiceRouter(sandbox_id="test")
    svc = MockFullService("multi-svc")
    router.register_service(svc)

    policy = AgentPolicy(
        name="all-access",
        allowed_services=(ServicePermission("multi-svc"),),
    )
    _, tool_map = router.make_service_tools("agent-1", policy)
    assert "execute_action" in tool_map
    result = json.loads(tool_map["execute_action"]("multi-svc", "notify", {"message": "hello"}))
    assert "error" not in result
    assert result["notified"] is True


def test_multi_role_service_event_subscription() -> None:
    router = SandboxServiceRouter(sandbox_id="test")
    svc = MockFullService("multi-svc")
    router.register_service(svc)

    router.register_agent_wake_callback("agent-1", lambda: None)
    router.subscribe_agent("agent-1", "multi-svc")

    policy = AgentPolicy(
        name="all-access",
        allowed_services=(ServicePermission("multi-svc"),),
    )
    _, tool_map = router.make_service_tools("agent-1", policy)
    assert "read_event_notifications" in tool_map

    router.deliver_external_event("multi-svc", "tick", {"value": 42.0})

    notifs = json.loads(tool_map["read_event_notifications"]())
    assert len(notifs) == 1
    assert notifs[0]["event_type"] == "tick"


def test_registering_same_service_twice_raises() -> None:
    router = SandboxServiceRouter(sandbox_id="test")
    router.register_service(MockFullService("dup"))
    with pytest.raises(ValueError, match="already registered"):
        router.register_service(MockFullService("dup"))
