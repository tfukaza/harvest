"""Tests for ToolRegistry — aggregation, uniqueness enforcement, policy filtering."""

from __future__ import annotations

import json

import pytest

from harvest.interfaces.service import ServicePermission, ServiceRole
from harvest.interfaces.tool_definition import InterfaceTool, ToolArgument
from harvest.interfaces.tool_registry import ToolRegistry
from harvest.policy import AgentPolicy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tool(
    name: str,
    service_id: str = "svc",
    service_type: str = "data_source",
) -> InterfaceTool:
    return InterfaceTool(
        name=name,
        short_description=f"Short description of {name}.",
        full_description=f"Full description of {name}.",
        arguments=[],
        returns_description="Result.",
        service_id=service_id,
        service_type=service_type,
        handler=lambda agent_id: json.dumps({"tool": name}),
    )


def _data_source_tool(name: str, source_id: str = "stock-data") -> InterfaceTool:
    return _make_tool(name, service_id=source_id, service_type="data_source")


def _action_tool(name: str, action_id: str = "orders") -> InterfaceTool:
    return _make_tool(name, service_id=action_id, service_type="action")


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------


def test_register_adds_tool() -> None:
    registry = ToolRegistry()
    tool = _data_source_tool("get_price")
    registry.register(tool)
    assert registry.get_tool("get_price") is tool


def test_register_name_collision_raises_value_error() -> None:
    registry = ToolRegistry()
    registry.register(_data_source_tool("my_tool", "service-a"))
    with pytest.raises(ValueError, match="my_tool"):
        registry.register(_data_source_tool("my_tool", "service-b"))


def test_register_different_names_no_collision() -> None:
    registry = ToolRegistry()
    registry.register(_data_source_tool("tool_a"))
    registry.register(_data_source_tool("tool_b"))
    assert registry.get_tool("tool_a") is not None
    assert registry.get_tool("tool_b") is not None


def test_get_tool_returns_none_for_unknown() -> None:
    registry = ToolRegistry()
    assert registry.get_tool("nonexistent") is None


def test_list_tool_names() -> None:
    registry = ToolRegistry()
    registry.register(_data_source_tool("alpha"))
    registry.register(_action_tool("beta"))
    names = registry.list_tool_names()
    assert "alpha" in names
    assert "beta" in names
    assert len(names) == 2


# ---------------------------------------------------------------------------
# tools_for_policy() tests
# ---------------------------------------------------------------------------


def test_tools_for_policy_none_returns_all() -> None:
    """None policy (admin mode) returns all tools."""
    registry = ToolRegistry()
    registry.register(_data_source_tool("ds_tool", "stock-data"))
    registry.register(_action_tool("act_tool", "orders"))
    tools = registry.tools_for_policy(None)
    names = {t.name for t in tools}
    assert "ds_tool" in names
    assert "act_tool" in names


def test_tools_for_policy_filters_by_data_source() -> None:
    registry = ToolRegistry()
    registry.register(_data_source_tool("get_price", "stock-data"))
    registry.register(_data_source_tool("get_news", "news-feed"))

    policy = AgentPolicy(
        name="analyst",
        allowed_services=(ServicePermission("stock-data"),),
    )
    tools = registry.tools_for_policy(policy)
    names = {t.name for t in tools}
    assert "get_price" in names
    assert "get_news" not in names


def test_tools_for_policy_filters_by_action() -> None:
    registry = ToolRegistry()
    registry.register(_action_tool("place_order", "orders"))
    registry.register(_action_tool("cancel_order", "orders"))
    registry.register(_action_tool("post_slack", "slack"))

    policy = AgentPolicy(
        name="trader",
        allowed_services=(ServicePermission("orders"),),
    )
    tools = registry.tools_for_policy(policy)
    names = {t.name for t in tools}
    assert "place_order" in names
    assert "cancel_order" in names
    assert "post_slack" not in names


def test_tools_for_policy_empty_policy_returns_empty() -> None:
    registry = ToolRegistry()
    registry.register(_data_source_tool("get_price", "stock-data"))
    registry.register(_action_tool("place_order", "orders"))

    policy = AgentPolicy(
        name="restricted",
        allowed_services=(),
    )
    tools = registry.tools_for_policy(policy)
    assert tools == []


def test_tools_for_policy_excludes_event_source_tools() -> None:
    """Event source tools are never returned for normal policies."""
    registry = ToolRegistry()
    es_tool = InterfaceTool(
        name="es_tool",
        short_description="Event source tool.",
        full_description="This should not be returned.",
        arguments=[],
        returns_description="N/A",
        service_id="price-alerts",
        service_type="event_source",
        handler=lambda agent_id: "{}",
    )
    registry.register(es_tool)

    policy = AgentPolicy(
        name="test",
        allowed_services=(ServicePermission("price-alerts"),),
    )
    tools = registry.tools_for_policy(policy)
    assert tools == []


def test_tools_for_policy_mixed_policy() -> None:
    registry = ToolRegistry()
    registry.register(_data_source_tool("get_price", "stock-data"))
    registry.register(_data_source_tool("get_news", "news-feed"))
    registry.register(_action_tool("place_order", "orders"))
    registry.register(_action_tool("send_email", "email"))

    policy = AgentPolicy(
        name="analyst-trader",
        allowed_services=(
            ServicePermission("stock-data"),
            ServicePermission("orders"),
        ),
    )
    tools = registry.tools_for_policy(policy)
    names = {t.name for t in tools}
    assert names == {"get_price", "place_order"}


def test_tools_for_policy_role_restricted() -> None:
    """DATA_SOURCE-only permission excludes action tools for the same service."""
    registry = ToolRegistry()
    registry.register(_data_source_tool("get_price", "combo"))
    registry.register(_action_tool("place_order", "combo"))

    policy = AgentPolicy(
        name="reader",
        allowed_services=(
            ServicePermission("combo", roles=frozenset({ServiceRole.DATA_SOURCE})),
        ),
    )
    tools = registry.tools_for_policy(policy)
    names = {t.name for t in tools}
    assert "get_price" in names
    assert "place_order" not in names
