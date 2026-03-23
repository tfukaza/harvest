"""Tests for role-filtered ServicePermission policies."""

from __future__ import annotations

import json
from typing import Any

from harvest.agent_sandbox.service_router import SandboxServiceRouter
from harvest.interfaces.examples.mock_full_service import MockFullService
from harvest.interfaces.service import ServicePermission, ServiceRole
from harvest.interfaces.tool_registry import ToolRegistry
from harvest.interfaces.tool_definition import InterfaceTool, ToolArgument
from harvest.policy import AgentPolicy


def test_data_source_only_permission_gets_fetch_tool_not_execute() -> None:
    router = SandboxServiceRouter(sandbox_id="test")
    router.register_service(MockFullService("multi"))

    # Only DATA_SOURCE role
    policy = AgentPolicy(
        name="reader",
        allowed_services=(
            ServicePermission("multi", roles=frozenset({ServiceRole.DATA_SOURCE})),
        ),
    )
    _, tool_map = router.make_service_tools("agent-1", policy)
    assert "fetch_data" in tool_map
    assert "execute_action" not in tool_map
    assert "read_event_notifications" not in tool_map


def test_action_only_permission_gets_execute_tool_not_fetch() -> None:
    router = SandboxServiceRouter(sandbox_id="test")
    router.register_service(MockFullService("multi"))

    policy = AgentPolicy(
        name="actor",
        allowed_services=(
            ServicePermission("multi", roles=frozenset({ServiceRole.ACTION})),
        ),
    )
    _, tool_map = router.make_service_tools("agent-1", policy)
    assert "execute_action" in tool_map
    assert "fetch_data" not in tool_map
    assert "read_event_notifications" not in tool_map


def test_event_only_permission_gets_read_notifications_not_fetch_or_execute() -> None:
    router = SandboxServiceRouter(sandbox_id="test")
    router.register_service(MockFullService("multi"))

    router.register_agent_wake_callback("agent-1", lambda: None)
    router.subscribe_agent("agent-1", "multi")

    policy = AgentPolicy(
        name="listener",
        allowed_services=(
            ServicePermission("multi", roles=frozenset({ServiceRole.EVENT_SOURCE})),
        ),
    )
    _, tool_map = router.make_service_tools("agent-1", policy)
    assert "read_event_notifications" in tool_map
    assert "fetch_data" not in tool_map
    assert "execute_action" not in tool_map


def test_all_roles_permission_gets_all_tools() -> None:
    router = SandboxServiceRouter(sandbox_id="test")
    router.register_service(MockFullService("multi"))

    router.register_agent_wake_callback("agent-1", lambda: None)
    router.subscribe_agent("agent-1", "multi")

    policy = AgentPolicy(
        name="full-access",
        allowed_services=(ServicePermission("multi"),),  # None roles = all
    )
    _, tool_map = router.make_service_tools("agent-1", policy)
    assert "fetch_data" in tool_map
    assert "execute_action" in tool_map
    assert "read_event_notifications" in tool_map


def test_role_filter_on_tool_registry() -> None:
    """ToolRegistry.tools_for_policy respects role restrictions."""
    registry = ToolRegistry()

    ds_tool = InterfaceTool(
        name="read_data",
        short_description="Read data.",
        full_description="Read data from service.",
        arguments=[],
        returns_description="Data.",
        service_id="combo",
        service_type="data_source",
        handler=lambda agent_id: "{}",
    )
    act_tool = InterfaceTool(
        name="write_data",
        short_description="Write data.",
        full_description="Write data to service.",
        arguments=[],
        returns_description="Result.",
        service_id="combo",
        service_type="action",
        handler=lambda agent_id: "{}",
    )
    registry.register(ds_tool)
    registry.register(act_tool)

    # DATA_SOURCE only
    ds_policy = AgentPolicy(
        name="reader",
        allowed_services=(
            ServicePermission("combo", roles=frozenset({ServiceRole.DATA_SOURCE})),
        ),
    )
    ds_tools = registry.tools_for_policy(ds_policy)
    names = {t.name for t in ds_tools}
    assert "read_data" in names
    assert "write_data" not in names

    # ACTION only
    act_policy = AgentPolicy(
        name="writer",
        allowed_services=(
            ServicePermission("combo", roles=frozenset({ServiceRole.ACTION})),
        ),
    )
    act_tools = registry.tools_for_policy(act_policy)
    names = {t.name for t in act_tools}
    assert "write_data" in names
    assert "read_data" not in names

    # All roles
    all_policy = AgentPolicy(
        name="all",
        allowed_services=(ServicePermission("combo"),),
    )
    all_tools = registry.tools_for_policy(all_policy)
    names = {t.name for t in all_tools}
    assert "read_data" in names
    assert "write_data" in names


def test_policy_denied_when_role_not_permitted() -> None:
    """Calling fetch_data on a service where only ACTION is permitted returns policy_denied."""
    router = SandboxServiceRouter(sandbox_id="test")
    router.register_service(MockFullService("multi"))

    # Only ACTION — no DATA_SOURCE
    policy = AgentPolicy(
        name="actor-only",
        allowed_services=(
            ServicePermission("multi", roles=frozenset({ServiceRole.ACTION})),
        ),
    )
    _, tool_map = router.make_service_tools("agent-1", policy)

    # fetch_data not registered when no DATA_SOURCE permission
    assert "fetch_data" not in tool_map
