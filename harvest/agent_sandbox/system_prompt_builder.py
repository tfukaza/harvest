"""SystemPromptBuilder: manages dynamic sections appended to an agent's system prompt.

Multiple independent sources of dynamic content (injected tool specs, event
arrival notifications, future memory fragments) each own a named section.
Sections can be set, appended, or cleared independently without affecting
other sections.
"""

from __future__ import annotations


class SystemPromptBuilder:
    """Manages dynamic sections appended to an agent's base system prompt.

    Sections are independent named blocks.  Any section can be set, updated,
    or cleared without affecting other sections.  On each LLM invocation,
    ``BasicSandbox`` calls :meth:`build` to assemble the final system prompt
    string::

        {base_system_prompt}

        {section_1_content}

        {section_2_content}
        ...

    Sections are rendered in insertion order.  An empty or cleared section
    contributes nothing to the output.

    Section keys used in Phase 14:

    ``"tool_specs"``
        Set by ``_inject_tool_spec`` when ``discover_tools(tool_name)`` is
        called.  Never cleared — specs are permanent for the session.

    ``"event_notifications"``
        Set by ``_add_event_notification`` when an external event is
        delivered.  Cleared by ``_clear_event_notifications`` after the
        agent calls ``read_event_notifications()``.

    Future phases add new keys without touching existing ones.
    """

    def __init__(self) -> None:
        # Ordered dict preserves insertion order (guaranteed in Python 3.7+)
        self._sections: dict[str, str] = {}
        # Sections that should be cleared after the next build() call
        self._auto_clear: set[str] = set()

    def set(self, section_key: str, content: str) -> None:
        """Set or replace the content of a named section.

        If the section does not exist it is created (at the end of the
        insertion order).  If it already exists the content is replaced
        in-place (insertion order is preserved).

        Args:
            section_key: Unique section identifier.
            content: New content for the section.
        """
        self._sections[section_key] = content

    def append(self, section_key: str, content: str) -> None:
        """Append content to a named section, creating it if absent.

        If the section already has content, the new content is appended
        with a blank line separator.  If the section is new (or was
        previously cleared), it is created with the supplied content.

        Args:
            section_key: Unique section identifier.
            content: Content to append.
        """
        if section_key in self._sections and self._sections[section_key]:
            self._sections[section_key] = (
                self._sections[section_key] + "\n\n" + content
            )
        else:
            self._sections[section_key] = content

    def append_auto_clear(self, section_key: str, content: str) -> None:
        """Append content that will be automatically cleared after the next build().

        Use for transient notifications (e.g. inbox alerts) that the agent
        should see exactly once.

        Args:
            section_key: Unique section identifier.
            content: Content to append.
        """
        self.append(section_key, content)
        self._auto_clear.add(section_key)

    def clear(self, section_key: str) -> None:
        """Remove a named section entirely.

        Removing a section that does not exist is a no-op.  The section is
        gone from the output but its insertion-order slot is not preserved —
        if the key is re-added via :meth:`set` or :meth:`append` it will
        appear at the end.

        Args:
            section_key: Section to remove.
        """
        self._sections.pop(section_key, None)

    def build(self, base_prompt: str) -> str:
        """Return the complete system prompt: base followed by all non-empty sections.

        Empty or cleared sections are omitted.  Non-empty sections are
        separated from each other and from the base prompt by a blank line.
        Sections marked as auto-clear are removed after being included.

        Args:
            base_prompt: The agent's base system prompt.

        Returns:
            The assembled system prompt string.
        """
        parts: list[str] = [base_prompt]

        for content in self._sections.values():
            if content:
                parts.append(content)

        # Clear auto-clear sections after they've been included once
        for key in list(self._auto_clear):
            self._sections.pop(key, None)
            self._auto_clear.discard(key)

        return "\n\n".join(parts)

    def has_section(self, section_key: str) -> bool:
        """Return whether a section exists and has non-empty content.

        Args:
            section_key: Section to check.

        Returns:
            ``True`` if the section exists and is non-empty.
        """
        return bool(self._sections.get(section_key))
