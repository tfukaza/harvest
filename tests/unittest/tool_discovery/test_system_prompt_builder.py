"""Tests for SystemPromptBuilder — named, independently addressable sections."""

from __future__ import annotations

import pytest

from harvest.agent_sandbox.system_prompt_builder import SystemPromptBuilder


def test_build_with_no_sections_returns_base_prompt() -> None:
    builder = SystemPromptBuilder()
    result = builder.build("You are a helpful assistant.")
    assert result == "You are a helpful assistant."


def test_set_creates_section() -> None:
    builder = SystemPromptBuilder()
    builder.set("my_section", "Section content")
    result = builder.build("Base prompt.")
    assert "Base prompt." in result
    assert "Section content" in result


def test_set_replaces_existing_content() -> None:
    builder = SystemPromptBuilder()
    builder.set("key", "First content")
    builder.set("key", "Second content")
    result = builder.build("Base.")
    assert "First content" not in result
    assert "Second content" in result


def test_append_creates_section_if_absent() -> None:
    builder = SystemPromptBuilder()
    builder.append("new_section", "Initial content")
    result = builder.build("Base.")
    assert "Initial content" in result


def test_append_accumulates_content() -> None:
    builder = SystemPromptBuilder()
    builder.append("notes", "First note")
    builder.append("notes", "Second note")
    result = builder.build("Base.")
    assert "First note" in result
    assert "Second note" in result


def test_clear_removes_section() -> None:
    builder = SystemPromptBuilder()
    builder.set("temp", "Temporary content")
    builder.clear("temp")
    result = builder.build("Base prompt.")
    assert "Temporary content" not in result


def test_clear_does_not_affect_other_sections() -> None:
    builder = SystemPromptBuilder()
    builder.set("keep", "Keep this")
    builder.set("remove", "Remove this")
    builder.clear("remove")
    result = builder.build("Base.")
    assert "Keep this" in result
    assert "Remove this" not in result


def test_clear_nonexistent_section_is_noop() -> None:
    builder = SystemPromptBuilder()
    builder.set("existing", "Content")
    builder.clear("does_not_exist")  # Should not raise
    result = builder.build("Base.")
    assert "Content" in result


def test_sections_rendered_in_insertion_order() -> None:
    builder = SystemPromptBuilder()
    builder.set("section_a", "Content A")
    builder.set("section_b", "Content B")
    builder.set("section_c", "Content C")
    result = builder.build("Base.")
    idx_a = result.index("Content A")
    idx_b = result.index("Content B")
    idx_c = result.index("Content C")
    assert idx_a < idx_b < idx_c


def test_empty_sections_omitted_from_output() -> None:
    builder = SystemPromptBuilder()
    builder.set("non_empty", "Something")
    builder.set("empty", "")
    result = builder.build("Base.")
    # The empty section should not add extra blank lines between sections
    # and should not appear as meaningful content
    assert "Something" in result
    lines = result.split("\n")
    # No more than one consecutive blank line
    for i in range(len(lines) - 1):
        if lines[i] == "" and i + 1 < len(lines):
            assert lines[i + 1] != "" or i + 2 >= len(lines)


def test_cleared_section_omitted() -> None:
    builder = SystemPromptBuilder()
    builder.set("gone", "Content that will be cleared")
    builder.clear("gone")
    result = builder.build("Base.")
    assert "Content that will be cleared" not in result
    assert result == "Base."


def test_has_section_returns_true_for_nonempty() -> None:
    builder = SystemPromptBuilder()
    builder.set("key", "content")
    assert builder.has_section("key") is True


def test_has_section_returns_false_for_missing() -> None:
    builder = SystemPromptBuilder()
    assert builder.has_section("missing") is False


def test_has_section_returns_false_after_clear() -> None:
    builder = SystemPromptBuilder()
    builder.set("key", "content")
    builder.clear("key")
    assert builder.has_section("key") is False


def test_build_separates_sections_with_blank_line() -> None:
    builder = SystemPromptBuilder()
    builder.set("s1", "Section 1")
    builder.set("s2", "Section 2")
    result = builder.build("Base.")
    # base + s1 + s2 should be separated by blank lines
    assert "Base.\n\nSection 1\n\nSection 2" == result


def test_append_after_clear_creates_fresh_section() -> None:
    builder = SystemPromptBuilder()
    builder.set("key", "original")
    builder.clear("key")
    builder.append("key", "after clear")
    result = builder.build("Base.")
    assert "after clear" in result
    assert "original" not in result
