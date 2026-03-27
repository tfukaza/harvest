"""Cognitive tools for HarvestAgent — think, memory, todo.

Phase 21: Agent-local tools that enhance individual agent reasoning.
These are not services; they require no external API. State lives on
the agent instance and persists within a session.

Activation is controlled by the ``cognitive_tools`` field on
:class:`~harvest.policy.AgentPolicy`.  Each value enables a group:

- ``"think"`` → ``think``
- ``"memory"`` → ``save_memory``, ``get_memory``, ``list_memories``
- ``"todo"`` → ``todo``
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Callable

from harvest.result_buffer import ServiceResult


def _tool_spec(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str] | None = None,
) -> dict[str, Any]:
    """Build an OpenAI-style tool specification dict."""
    params: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        params["required"] = required
    return {
        "type": "function",
        "function": {"name": name, "description": description, "parameters": params},
    }


# ---------------------------------------------------------------------------
# Think
# ---------------------------------------------------------------------------

def _make_think_tool() -> tuple[dict, Callable[..., str]]:
    spec = _tool_spec(
        "think",
        (
            "Private scratchpad for internal reasoning. Use this to plan your next "
            "steps, analyze data, or work through a problem BEFORE acting. "
            "The thought is NOT visible to users or posted to any channel — it is "
            "purely internal. To communicate with users, use send_message instead."
        ),
        {"thought": {"type": "string", "description": "Your private internal reasoning (not shown to users)"}},
        required=["thought"],
    )

    def handler(thought: str = "", **_kwargs: Any) -> str:
        return json.dumps({"status": "thought_recorded", "length": len(thought)})

    return spec, handler


# ---------------------------------------------------------------------------
# Memory (save / get / list)
# ---------------------------------------------------------------------------

def _make_memory_tools(
    agent: Any,
) -> list[tuple[dict, Callable[..., str | ServiceResult]]]:
    """Return (spec, handler) pairs for save_memory, get_memory, list_memories.

    All three handlers close over ``agent._memories`` (a dict on the agent
    instance).  Mutations are direct — ``save_memory`` inserts/overwrites,
    ``get_memory`` reads, ``list_memories`` iterates.  No external I/O.
    """

    # -- save_memory --------------------------------------------------------
    save_spec = _tool_spec(
        "save_memory",
        (
            "Save information to your personal memory for later retrieval. "
            "Provide a short name to identify the entry, a brief description, "
            "and the full content to store."
        ),
        {
            "name": {
                "type": "string",
                "description": "Unique name/key for this memory entry",
            },
            "description": {
                "type": "string",
                "description": "Brief one-line summary of what this memory contains",
            },
            "content": {
                "type": "string",
                "description": "Full text content to save",
            },
        },
        required=["name", "description", "content"],
    )

    def save_handler(
        name: str = "",
        description: str = "",
        content: str = "",
        **_kwargs: Any,
    ) -> str:
        if not name:
            return json.dumps({"error": "name is required"})
        agent._memories[name] = {
            "name": name,
            "description": description,
            "content": content,
        }
        return json.dumps({
            "status": "saved",
            "name": name,
            "total_memories": len(agent._memories),
        })

    # -- get_memory ---------------------------------------------------------
    get_spec = _tool_spec(
        "get_memory",
        "Retrieve the full content of a previously saved memory entry by name.",
        {
            "name": {
                "type": "string",
                "description": "Name of the memory entry to retrieve",
            },
        },
        required=["name"],
    )

    def get_handler(name: str = "", **_kwargs: Any) -> ServiceResult:
        if not name:
            return ServiceResult.from_dict({"error": "name is required"})
        entry = agent._memories.get(name)
        if entry is None:
            return ServiceResult.from_dict({"error": f"Memory not found: {name}"})
        return ServiceResult.from_dict(
            entry,
            summary=f"Memory '{name}': {entry.get('description', '')}",
        )

    # -- list_memories ------------------------------------------------------
    list_spec = _tool_spec(
        "list_memories",
        (
            "List all saved memory entries. Returns the name and brief description "
            "of each entry (not the full content). Use get_memory to retrieve details."
        ),
        {},
    )

    def list_handler(**_kwargs: Any) -> str:
        summaries = [
            {"name": e["name"], "description": e["description"]}
            for e in agent._memories.values()
        ]
        return json.dumps({"memories": summaries, "total": len(summaries)})

    return [
        (save_spec, save_handler),
        (get_spec, get_handler),
        (list_spec, list_handler),
    ]


# ---------------------------------------------------------------------------
# Todo
# ---------------------------------------------------------------------------

def _make_todo_tool(agent: Any) -> tuple[dict, Callable[..., str]]:
    spec = _tool_spec(
        "todo",
        (
            "Manage your personal task list for planning and tracking work. "
            "Operations: 'add' a new task, 'complete' a task by ID, "
            "'list' all tasks, or 'remove' a task by ID."
        ),
        {
            "operation": {
                "type": "string",
                "enum": ["add", "complete", "list", "remove"],
                "description": "The operation to perform",
            },
            "task": {
                "type": "string",
                "description": "Task description (required for 'add')",
            },
            "task_id": {
                "type": "string",
                "description": "Task ID (required for 'complete' and 'remove')",
            },
        },
        required=["operation"],
    )

    def handler(
        operation: str = "",
        task: str = "",
        task_id: str = "",
        **_kwargs: Any,
    ) -> str:
        if operation == "add":
            if not task:
                return json.dumps({"error": "task description is required for 'add'"})
            new_id = uuid.uuid4().hex[:8]
            entry = {"id": new_id, "task": task, "done": False}
            agent._todos.append(entry)
            return json.dumps({
                "status": "added",
                "task_id": new_id,
                "task": task,
                "total": len(agent._todos),
            })

        if operation == "complete":
            if not task_id:
                return json.dumps({"error": "task_id is required for 'complete'"})
            for item in agent._todos:
                if item["id"] == task_id:
                    item["done"] = True
                    return json.dumps({"status": "completed", "task_id": task_id})
            return json.dumps({"error": f"Task not found: {task_id}"})

        if operation == "list":
            pending = sum(1 for t in agent._todos if not t["done"])
            return json.dumps({
                "tasks": agent._todos,
                "total": len(agent._todos),
                "pending": pending,
            })

        if operation == "remove":
            if not task_id:
                return json.dumps({"error": "task_id is required for 'remove'"})
            for i, item in enumerate(agent._todos):
                if item["id"] == task_id:
                    agent._todos.pop(i)
                    return json.dumps({"status": "removed", "task_id": task_id})
            return json.dumps({"error": f"Task not found: {task_id}"})

        return json.dumps({"error": f"Unknown operation: {operation}"})

    return spec, handler


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_cognitive_tools(
    agent: Any,
    enabled: frozenset[str],
) -> list[tuple[dict, Callable[..., str]]]:
    """Return ``(tool_spec, handler)`` pairs for the requested cognitive tools.

    Args:
        agent: The HarvestAgent instance (handlers close over its state).
        enabled: Set of cognitive tool group names to activate.

    Returns:
        List of (OpenAI tool spec dict, handler callable) tuples.
    """
    tools: list[tuple[dict, Callable[..., str]]] = []
    if "think" in enabled:
        tools.append(_make_think_tool())
    if "memory" in enabled:
        tools.extend(_make_memory_tools(agent))
    if "todo" in enabled:
        tools.append(_make_todo_tool(agent))
    return tools
