"""Tests for system prompt injection via SystemPromptBuilder.

- No tool specs before discover_tools(name)
- Spec appears after the call
- Multiple activated tools append without disturbing previous specs
- Block survives across multiple invocations (builder state is persistent)
"""


import json
from typing import Any

import pytest

from harvest.agent_sandbox.system_prompt_builder import SystemPromptBuilder
from harvest.interfaces.tool_definition import InterfaceTool, ToolArgument


def _make_tool(name: str, service_id: str = "svc") -> InterfaceTool:
    return InterfaceTool(
        name=name,
        short_description=f"Short: {name}",
        full_description=f"Full description for {name}.",
        arguments=[ToolArgument(name="x", type="string", description="Input")],
        returns_description="Result.",
        service_id=service_id,
        service_type="data_source",
        handler=lambda agent_id, x: json.dumps({"x": x}),
    )


def test_system_prompt_no_specs_before_injection() -> None:
    builder = SystemPromptBuilder()
    base = "You are a helpful assistant."
    result = builder.build(base)
    assert result == base
    assert "### " not in result  # no tool spec blocks


def test_spec_appears_in_system_prompt_after_injection() -> None:
    builder = SystemPromptBuilder()
    tool = _make_tool("get_price")
    builder.append("tool_specs", "## Available Tools\n")
    builder.append("tool_specs", tool.to_system_prompt_block())

    result = builder.build("Base.")
    assert "get_price" in result
    assert "Full description for get_price" in result


def test_multiple_tool_specs_all_appear() -> None:
    builder = SystemPromptBuilder()
    tool_a = _make_tool("tool_a")
    tool_b = _make_tool("tool_b")

    builder.append("tool_specs", "## Available Tools\n")
    builder.append("tool_specs", tool_a.to_system_prompt_block())
    builder.append("tool_specs", tool_b.to_system_prompt_block())

    result = builder.build("Base.")
    assert "tool_a" in result
    assert "tool_b" in result


def test_second_tool_does_not_disturb_first() -> None:
    builder = SystemPromptBuilder()
    tool_a = _make_tool("tool_a")
    tool_b = _make_tool("tool_b")

    builder.append("tool_specs", "## Available Tools\n")
    builder.append("tool_specs", tool_a.to_system_prompt_block())
    after_first = builder.build("Base.")

    builder.append("tool_specs", tool_b.to_system_prompt_block())
    after_second = builder.build("Base.")

    # First tool still present
    assert "tool_a" in after_second
    # Second tool also present
    assert "tool_b" in after_second
    # Content of first tool unchanged
    first_block = tool_a.to_system_prompt_block()
    assert first_block in after_second


def test_spec_survives_multiple_build_calls() -> None:
    """SystemPromptBuilder state is persistent — repeated build() calls include injected specs."""
    builder = SystemPromptBuilder()
    tool = _make_tool("my_tool")
    builder.append("tool_specs", "## Available Tools\n")
    builder.append("tool_specs", tool.to_system_prompt_block())

    # Call build() multiple times (simulating multiple LLM invocations)
    for _ in range(5):
        result = builder.build("System prompt.")
        assert "my_tool" in result


def test_spec_not_duplicated_with_idempotency_set() -> None:
    """Simulates the _inject_tool_spec idempotency check."""
    builder = SystemPromptBuilder()
    injected_names: set[str] = set()
    tool = _make_tool("my_tool")

    def inject(tool_: InterfaceTool) -> None:
        if tool_.name not in injected_names:
            if not injected_names:
                builder.append("tool_specs", "## Available Tools\n")
            builder.append("tool_specs", tool_.to_system_prompt_block())
            injected_names.add(tool_.name)

    inject(tool)
    inject(tool)  # second call should be no-op

    result = builder.build("Base.")
    count = result.count(f"### {tool.name}")
    assert count == 1


def test_event_notifications_section_clears_independently() -> None:
    """Clearing event_notifications doesn't affect tool_specs."""
    builder = SystemPromptBuilder()
    tool = _make_tool("my_tool")
    builder.append("tool_specs", tool.to_system_prompt_block())
    builder.set("event_notifications", "## Pending Event Notification\n\nSome event arrived.")

    # Clear only event notifications
    builder.clear("event_notifications")

    result = builder.build("Base.")
    assert "my_tool" in result
    assert "Pending Event Notification" not in result
