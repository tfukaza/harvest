"""InterfaceTool and ToolArgument dataclasses for the tool discovery system.

InterfaceTool represents a single operation that a DataSource or Action
exposes to agents.  It carries both the metadata needed for agent discovery
(name, descriptions, argument specs) and the callable handler that executes
the operation through the service router.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(slots=True)
class ToolArgument:
    """Description of one argument accepted by an InterfaceTool.

    Attributes:
        name: Argument name as it appears in the tool's handler signature.
        type: JSON-schema primitive type string.  One of ``"string"``,
            ``"integer"``, ``"float"``, ``"boolean"``, ``"object"``,
            ``"array"``.
        description: Human-readable description of what this argument is.
        required: Whether the argument must be supplied.  Defaults to
            ``True``.
        default: Default value when ``required`` is ``False``.  Only
            meaningful when ``required=False``.
    """

    name: str
    type: str  # "string" | "integer" | "float" | "boolean" | "object" | "array"
    description: str
    required: bool = True
    default: Any = None


@dataclass
class InterfaceTool:
    """A declared, structured description of one operation a service can perform.

    InterfaceTools are defined by DataSource and Action implementations and
    registered with the ToolRegistry at service-registration time.  They are
    wired as callables onto permitted agents at sandbox startup
    (auto-registration) and their full specs are injected into the agent's
    system prompt on demand via ``discover_tools(tool_name)``.

    Attributes:
        name: Stable, sandbox-unique tool name (e.g. ``"get_stock_price"``).
        short_description: One-sentence summary returned in the lightweight
            ``discover_tools()`` catalogue listing.
        full_description: Detailed description injected into the system prompt
            and returned when the agent calls ``discover_tools(tool_name)``.
        arguments: Typed, described argument list.
        returns_description: Prose description of the return value shape.
        service_id: ID of the service this tool belongs to.
        service_type: One of ``"data_source"``, ``"action"``, or
            ``"event_source"``.
        handler: Callable that receives keyword arguments matching
            ``arguments``, performs validation, translates to the internal
            schema, and calls back through the service router.  Return value
            is a JSON string.
    """

    name: str
    short_description: str
    full_description: str
    arguments: list[ToolArgument]
    returns_description: str
    service_id: str
    service_type: str  # "data_source" | "action" | "event_source"
    handler: Callable[..., str]

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    def to_tool_spec(self) -> dict:
        """Return an OpenAI function-calling compatible tool spec dict.

        Uses ``full_description`` and ``arguments`` to build the spec.
        The spec can be passed directly to the LLM's tools list.

        Returns:
            Dict in ``{"type": "function", "function": {...}}`` format.
        """
        properties: dict[str, Any] = {}
        required: list[str] = []

        for arg in self.arguments:
            arg_type = arg.type
            # Map "float" to "number" for JSON schema compatibility
            if arg_type == "float":
                arg_type = "number"

            prop: dict[str, Any] = {
                "type": arg_type,
                "description": arg.description,
            }
            if not arg.required and arg.default is not None:
                prop["default"] = arg.default

            properties[arg.name] = prop
            if arg.required:
                required.append(arg.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.full_description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    def to_system_prompt_block(self) -> str:
        """Return a formatted string block for system prompt injection.

        The block is human-readable for the LLM and contains the tool name,
        full description, service info, argument list (with types and
        required/optional markers), and return description.

        Returns:
            Markdown-style text block suitable for appending to a system
            prompt under an ``## Available Tools`` header.
        """
        lines: list[str] = [
            f"### {self.name}",
            self.full_description,
            f"Service: {self.service_id} [{self.service_type}]",
            "",
            "Arguments:",
        ]

        if self.arguments:
            for arg in self.arguments:
                req_marker = "required" if arg.required else "optional"
                line = f"  - {arg.name} ({arg.type}, {req_marker}): {arg.description}"
                if not arg.required and arg.default is not None:
                    line += f" (default: {arg.default!r})"
                lines.append(line)
        else:
            lines.append("  (none)")

        lines.append("")
        lines.append(f"Returns: {self.returns_description}")
        lines.append("")
        lines.append("---")
        lines.append("")

        return "\n".join(lines)
