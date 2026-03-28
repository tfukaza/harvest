"""Unit tests for cognitive tools — think, memory, todo."""


import json

import pytest

from harvest.tools.cognitive_tools import get_cognitive_tools
from harvest.tools.result_buffer import ServiceResult


# ---------------------------------------------------------------------------
# Fake agent for testing (provides _memories and _todos state)
# ---------------------------------------------------------------------------


class _FakeAgent:
    def __init__(self) -> None:
        self._memories: dict[str, dict[str, str]] = {}
        self._todos: list[dict] = []


# ---------------------------------------------------------------------------
# Tests: think
# ---------------------------------------------------------------------------


class TestThinkTool:
    def setup_method(self) -> None:
        agent = _FakeAgent()
        pairs = get_cognitive_tools(agent, frozenset({"think"}))
        assert len(pairs) == 1
        self.spec, self.handler = pairs[0]

    def test_spec_name(self) -> None:
        assert self.spec["function"]["name"] == "think"

    def test_records_thought(self) -> None:
        result = json.loads(self.handler(thought="I should search for X first"))
        assert result["status"] == "thought_recorded"
        assert result["length"] == len("I should search for X first")

    def test_empty_thought(self) -> None:
        result = json.loads(self.handler(thought=""))
        assert result["status"] == "thought_recorded"
        assert result["length"] == 0


# ---------------------------------------------------------------------------
# Tests: memory (save_memory, get_memory, list_memories)
# ---------------------------------------------------------------------------


class TestMemoryTools:
    def setup_method(self) -> None:
        self.agent = _FakeAgent()
        pairs = get_cognitive_tools(self.agent, frozenset({"memory"}))
        assert len(pairs) == 3
        self.tools = {spec["function"]["name"]: handler for spec, handler in pairs}

    def test_tool_names(self) -> None:
        assert set(self.tools.keys()) == {"save_memory", "get_memory", "list_memories"}

    def test_save_and_get(self) -> None:
        save = self.tools["save_memory"]
        get = self.tools["get_memory"]

        result = json.loads(save(name="founders", description="Company founders", content="Alice and Bob founded Acme in 2020."))
        assert result["status"] == "saved"
        assert result["name"] == "founders"
        assert result["total_memories"] == 1

        raw = get(name="founders")
        assert isinstance(raw, ServiceResult)
        assert raw.kind == "dict"
        assert raw.data["name"] == "founders"
        assert raw.data["description"] == "Company founders"
        assert raw.data["content"] == "Alice and Bob founded Acme in 2020."

    def test_get_missing_key(self) -> None:
        get = self.tools["get_memory"]
        raw = get(name="nonexistent")
        assert isinstance(raw, ServiceResult)
        assert "error" in raw.data
        assert "not found" in raw.data["error"].lower()

    def test_list_memories_empty(self) -> None:
        result = json.loads(self.tools["list_memories"]())
        assert result["memories"] == []
        assert result["total"] == 0

    def test_list_memories(self) -> None:
        save = self.tools["save_memory"]
        save(name="topic_a", description="First topic", content="Details about A")
        save(name="topic_b", description="Second topic", content="Details about B")

        result = json.loads(self.tools["list_memories"]())
        assert result["total"] == 2
        names = {m["name"] for m in result["memories"]}
        assert names == {"topic_a", "topic_b"}
        # list_memories should NOT include full content
        for m in result["memories"]:
            assert "content" not in m

    def test_overwrite_existing(self) -> None:
        save = self.tools["save_memory"]
        get = self.tools["get_memory"]

        save(name="data", description="v1", content="old content")
        save(name="data", description="v2", content="new content")

        raw = get(name="data")
        assert isinstance(raw, ServiceResult)
        assert raw.data["description"] == "v2"
        assert raw.data["content"] == "new content"
        assert len(self.agent._memories) == 1

    def test_save_missing_name(self) -> None:
        result = json.loads(self.tools["save_memory"](name="", description="x", content="y"))
        assert "error" in result

    def test_per_agent_isolation(self) -> None:
        agent2 = _FakeAgent()
        pairs2 = get_cognitive_tools(agent2, frozenset({"memory"}))
        tools2 = {spec["function"]["name"]: handler for spec, handler in pairs2}

        self.tools["save_memory"](name="private", description="a", content="agent1 data")
        raw = tools2["get_memory"](name="private")
        assert isinstance(raw, ServiceResult)
        assert "error" in raw.data  # agent2 should not see agent1's data


# ---------------------------------------------------------------------------
# Tests: todo
# ---------------------------------------------------------------------------


class TestTodoTool:
    def setup_method(self) -> None:
        self.agent = _FakeAgent()
        pairs = get_cognitive_tools(self.agent, frozenset({"todo"}))
        assert len(pairs) == 1
        self.spec, self.handler = pairs[0]

    def test_spec_name(self) -> None:
        assert self.spec["function"]["name"] == "todo"

    def test_add_task(self) -> None:
        result = json.loads(self.handler(operation="add", task="Research company founders"))
        assert result["status"] == "added"
        assert "task_id" in result
        assert result["task"] == "Research company founders"
        assert result["total"] == 1

    def test_list_empty(self) -> None:
        result = json.loads(self.handler(operation="list"))
        assert result["tasks"] == []
        assert result["total"] == 0
        assert result["pending"] == 0

    def test_add_and_list(self) -> None:
        self.handler(operation="add", task="Task A")
        self.handler(operation="add", task="Task B")
        result = json.loads(self.handler(operation="list"))
        assert result["total"] == 2
        assert result["pending"] == 2

    def test_complete_task(self) -> None:
        add_result = json.loads(self.handler(operation="add", task="Do research"))
        task_id = add_result["task_id"]

        result = json.loads(self.handler(operation="complete", task_id=task_id))
        assert result["status"] == "completed"

        list_result = json.loads(self.handler(operation="list"))
        assert list_result["pending"] == 0
        assert list_result["total"] == 1
        assert list_result["tasks"][0]["done"] is True

    def test_complete_nonexistent(self) -> None:
        result = json.loads(self.handler(operation="complete", task_id="fake123"))
        assert "error" in result

    def test_remove_task(self) -> None:
        add_result = json.loads(self.handler(operation="add", task="Remove me"))
        task_id = add_result["task_id"]

        result = json.loads(self.handler(operation="remove", task_id=task_id))
        assert result["status"] == "removed"

        list_result = json.loads(self.handler(operation="list"))
        assert list_result["total"] == 0

    def test_remove_nonexistent(self) -> None:
        result = json.loads(self.handler(operation="remove", task_id="fake123"))
        assert "error" in result

    def test_add_missing_task(self) -> None:
        result = json.loads(self.handler(operation="add", task=""))
        assert "error" in result

    def test_unknown_operation(self) -> None:
        result = json.loads(self.handler(operation="nope"))
        assert "error" in result

    def test_mixed_done_pending(self) -> None:
        r1 = json.loads(self.handler(operation="add", task="A"))
        self.handler(operation="add", task="B")
        self.handler(operation="complete", task_id=r1["task_id"])

        result = json.loads(self.handler(operation="list"))
        assert result["total"] == 2
        assert result["pending"] == 1


# ---------------------------------------------------------------------------
# Tests: get_cognitive_tools selection
# ---------------------------------------------------------------------------


class TestGetCognitiveTools:
    def test_empty_set(self) -> None:
        agent = _FakeAgent()
        assert get_cognitive_tools(agent, frozenset()) == []

    def test_all_tools(self) -> None:
        agent = _FakeAgent()
        pairs = get_cognitive_tools(agent, frozenset({"think", "memory", "todo"}))
        names = {spec["function"]["name"] for spec, _ in pairs}
        assert names == {"think", "save_memory", "get_memory", "list_memories", "todo"}

    def test_only_think(self) -> None:
        agent = _FakeAgent()
        pairs = get_cognitive_tools(agent, frozenset({"think"}))
        names = {spec["function"]["name"] for spec, _ in pairs}
        assert names == {"think"}

    def test_only_memory(self) -> None:
        agent = _FakeAgent()
        pairs = get_cognitive_tools(agent, frozenset({"memory"}))
        names = {spec["function"]["name"] for spec, _ in pairs}
        assert names == {"save_memory", "get_memory", "list_memories"}


# ---------------------------------------------------------------------------
# Tests: policy parsing
# ---------------------------------------------------------------------------


class TestPolicyParsing:
    def test_cognitive_tools_parsed(self) -> None:
        from harvest.core.policy_registry import _parse_policy
        policy = _parse_policy("test", {
            "cognitive_tools": ["think", "memory", "todo"],
        })
        assert policy.cognitive_tools == frozenset({"think", "memory", "todo"})

    def test_cognitive_tools_default_empty(self) -> None:
        from harvest.core.policy_registry import _parse_policy
        policy = _parse_policy("test", {})
        assert policy.cognitive_tools == frozenset()
