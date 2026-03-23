"""Tests for InterfaceTool and ToolArgument dataclasses."""

from __future__ import annotations

import json

import pytest

from harvest.interfaces.tool_definition import InterfaceTool, ToolArgument


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_tool(
    name: str = "my_tool",
    args: list[ToolArgument] | None = None,
    service_id: str = "my-service",
    service_type: str = "data_source",
) -> InterfaceTool:
    if args is None:
        args = [
            ToolArgument(
                name="symbol",
                type="string",
                description="Ticker symbol",
                required=True,
            ),
            ToolArgument(
                name="limit",
                type="integer",
                description="Max results",
                required=False,
                default=10,
            ),
        ]
    return InterfaceTool(
        name=name,
        short_description="A short description.",
        full_description="A full, detailed description of the tool.",
        arguments=args,
        returns_description="Returns JSON with the result.",
        service_id=service_id,
        service_type=service_type,
        handler=lambda agent_id, **kwargs: json.dumps({"ok": True}),
    )


# ---------------------------------------------------------------------------
# ToolArgument tests
# ---------------------------------------------------------------------------


def test_tool_argument_required_default() -> None:
    arg = ToolArgument(name="x", type="string", description="An arg")
    assert arg.required is True
    assert arg.default is None


def test_tool_argument_optional_with_default() -> None:
    arg = ToolArgument(name="limit", type="integer", description="Max", required=False, default=50)
    assert arg.required is False
    assert arg.default == 50


def test_tool_argument_type_values() -> None:
    for t in ("string", "integer", "float", "boolean", "object", "array"):
        arg = ToolArgument(name="a", type=t, description="d")
        assert arg.type == t


# ---------------------------------------------------------------------------
# to_tool_spec() tests
# ---------------------------------------------------------------------------


def test_to_tool_spec_returns_openai_format() -> None:
    tool = _make_tool()
    spec = tool.to_tool_spec()
    assert spec["type"] == "function"
    assert "function" in spec
    fn = spec["function"]
    assert fn["name"] == "my_tool"
    assert fn["description"] == "A full, detailed description of the tool."
    assert "parameters" in fn
    params = fn["parameters"]
    assert params["type"] == "object"
    assert "symbol" in params["properties"]
    assert "limit" in params["properties"]


def test_to_tool_spec_required_fields() -> None:
    tool = _make_tool()
    spec = tool.to_tool_spec()
    required = spec["function"]["parameters"]["required"]
    assert "symbol" in required
    assert "limit" not in required


def test_to_tool_spec_float_mapped_to_number() -> None:
    tool = InterfaceTool(
        name="price_tool",
        short_description="short",
        full_description="full",
        arguments=[ToolArgument(name="price", type="float", description="A price")],
        returns_description="returns",
        service_id="svc",
        service_type="data_source",
        handler=lambda agent_id, price: "{}",
    )
    spec = tool.to_tool_spec()
    assert spec["function"]["parameters"]["properties"]["price"]["type"] == "number"


def test_to_tool_spec_no_arguments() -> None:
    tool = InterfaceTool(
        name="ping",
        short_description="Ping.",
        full_description="Ping the service.",
        arguments=[],
        returns_description="OK.",
        service_id="svc",
        service_type="action",
        handler=lambda agent_id: "{}",
    )
    spec = tool.to_tool_spec()
    assert spec["function"]["parameters"]["properties"] == {}
    assert spec["function"]["parameters"]["required"] == []


# ---------------------------------------------------------------------------
# to_system_prompt_block() tests
# ---------------------------------------------------------------------------


def test_to_system_prompt_block_contains_name() -> None:
    tool = _make_tool(name="get_stock_price")
    block = tool.to_system_prompt_block()
    assert "### get_stock_price" in block


def test_to_system_prompt_block_contains_service_info() -> None:
    tool = _make_tool(service_id="alpaca-market-data", service_type="data_source")
    block = tool.to_system_prompt_block()
    assert "alpaca-market-data" in block
    assert "data_source" in block


def test_to_system_prompt_block_contains_full_description() -> None:
    tool = _make_tool()
    block = tool.to_system_prompt_block()
    assert "A full, detailed description of the tool." in block


def test_to_system_prompt_block_lists_required_argument() -> None:
    tool = _make_tool()
    block = tool.to_system_prompt_block()
    assert "symbol" in block
    assert "required" in block


def test_to_system_prompt_block_lists_optional_argument() -> None:
    tool = _make_tool()
    block = tool.to_system_prompt_block()
    assert "limit" in block
    assert "optional" in block


def test_to_system_prompt_block_contains_returns_description() -> None:
    tool = _make_tool()
    block = tool.to_system_prompt_block()
    assert "Returns JSON with the result." in block


def test_to_system_prompt_block_has_separator() -> None:
    tool = _make_tool()
    block = tool.to_system_prompt_block()
    assert "---" in block


def test_to_system_prompt_block_no_arguments_shows_none() -> None:
    tool = InterfaceTool(
        name="ping",
        short_description="Ping.",
        full_description="Ping.",
        arguments=[],
        returns_description="OK.",
        service_id="svc",
        service_type="action",
        handler=lambda agent_id: "{}",
    )
    block = tool.to_system_prompt_block()
    assert "(none)" in block


def test_to_system_prompt_block_optional_with_default_shows_default() -> None:
    tool = InterfaceTool(
        name="search",
        short_description="Search.",
        full_description="Search something.",
        arguments=[
            ToolArgument(name="limit", type="integer", description="Max", required=False, default=20),
        ],
        returns_description="Results.",
        service_id="svc",
        service_type="data_source",
        handler=lambda agent_id, limit=20: "{}",
    )
    block = tool.to_system_prompt_block()
    assert "20" in block
