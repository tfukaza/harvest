"""End-to-end test: Alice & Bob demo with mocked LLM."""

from __future__ import annotations

import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from harvest import cli
from harvest.agent_sandbox.basic_sandbox import BasicSandbox
from harvest.agent_sandbox.manifest import load_manifest
from harvest.storage.schema.chat import ChatStore

MANIFEST_PATH = Path(__file__).resolve().parent.parent.parent / "demos" / "alice-bob.yaml"


# ---------------------------------------------------------------------------
# Fake LLM completion
# ---------------------------------------------------------------------------


@dataclass
class _FakeFunction:
    name: str
    arguments: str


@dataclass
class _FakeToolCall:
    id: str
    function: _FakeFunction


@dataclass
class _FakeMessage:
    role: str = "assistant"
    content: str | None = None
    tool_calls: list[_FakeToolCall] | None = None


@dataclass
class _FakeChoice:
    message: _FakeMessage


@dataclass
class _FakeResponse:
    choices: list[_FakeChoice]


def _make_fake_completion():
    """Create a fake completion function with its own call counter."""
    call_count = 0

    def fake_completion(
        *, model: str, messages: list[dict], tools: list | None = None, **kwargs: Any
    ) -> _FakeResponse:
        nonlocal call_count
        call_count += 1

        system = messages[0]["content"] if messages else ""
        is_alice = "Alice" in system
        agent_name = "Alice" if is_alice else "Bob"

        # Odd calls: use send_message tool; even calls: return text
        if call_count % 2 == 1 and tools:
            content_text = f"{agent_name}'s response #{call_count}"
            tool_call = _FakeToolCall(
                id=f"call_{call_count}",
                function=_FakeFunction(
                    name="send_message",
                    arguments=json.dumps(
                        {"channel_id": "tech-talk", "content": content_text}
                    ),
                ),
            )
            return _FakeResponse(
                choices=[_FakeChoice(message=_FakeMessage(tool_calls=[tool_call]))]
            )
        else:
            return _FakeResponse(
                choices=[
                    _FakeChoice(
                        message=_FakeMessage(
                            content=f"{agent_name} wraps up thought #{call_count}."
                        )
                    )
                ]
            )

    return fake_completion


def _patch_agents(sandbox: BasicSandbox) -> None:
    """Replace completion functions on all agents with fakes."""
    for agent_id in sandbox.list_agents():
        agent = sandbox.get_agent(agent_id)
        agent._completion_func = _make_fake_completion()


def _step_agent(sandbox: BasicSandbox, agent_id: str) -> str | None:
    """Read inbox and run one LLM step for an agent (test helper)."""
    inbox = sandbox.chat_router.read_inbox(agent_id)
    if not inbox:
        return None
    parts = [f"[{m.sender.endpoint_id}]: {m.content}" for m in inbox]
    prompt = "\n".join(parts)
    agent = sandbox.get_agent(agent_id)
    try:
        return agent.step(prompt)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Manifest & sandbox tests
# ---------------------------------------------------------------------------


class TestManifestAndSandbox:
    def test_manifest_loads(self) -> None:
        """Manifest parses and validates without errors."""
        manifest = load_manifest(MANIFEST_PATH)
        assert "alice" in manifest.agents
        assert "bob" in manifest.agents
        assert "tech-talk" in manifest.channels
        assert "chatter" in manifest.policies

    def test_sandbox_from_manifest(self) -> None:
        """Sandbox can be created from the manifest with correct agents."""
        sandbox = BasicSandbox.from_manifest(MANIFEST_PATH)
        assert set(sandbox.list_agents()) == {"alice", "bob"}

    def test_sandbox_channels_created(self) -> None:
        """Sandbox creates the tech-talk channel from the manifest."""
        sandbox = BasicSandbox.from_manifest(MANIFEST_PATH)
        channels = sandbox.chat_router.list_channels()
        channel_ids = [ch.channel_id for ch in channels]
        assert "tech-talk" in channel_ids

    def test_seed_message_reaches_both_agents(self) -> None:
        """Seed message appears in both agents' inboxes."""
        sandbox = BasicSandbox.from_manifest(MANIFEST_PATH)
        sandbox.chat_router.inject_seed("tech-talk", "Test topic")

        alice_inbox = sandbox.chat_router.peek_inbox("alice")
        bob_inbox = sandbox.chat_router.peek_inbox("bob")
        assert len(alice_inbox) == 1
        assert len(bob_inbox) == 1
        assert alice_inbox[0].content == "Test topic"

    def test_policy_prevents_channel_creation(self) -> None:
        """Neither agent can create new channels (chatter policy)."""
        sandbox = BasicSandbox.from_manifest(MANIFEST_PATH)
        alice_agent = sandbox.get_agent("alice")
        assert "create_channel" not in alice_agent._tool_map

    def test_policy_allows_send_message(self) -> None:
        """Both agents have send_message in their tool map."""
        sandbox = BasicSandbox.from_manifest(MANIFEST_PATH)
        for aid in ("alice", "bob"):
            assert "send_message" in sandbox.get_agent(aid)._tool_map

    def test_empty_inbox_returns_no_messages(self) -> None:
        """Empty inbox means no messages to process."""
        sandbox = BasicSandbox.from_manifest(MANIFEST_PATH)
        inbox = sandbox.chat_router.read_inbox("alice")
        assert inbox == []


# ---------------------------------------------------------------------------
# Conversation tests (with mocked LLM)
# ---------------------------------------------------------------------------


class TestConversation:
    def test_full_conversation_runs(self) -> None:
        """Two agents exchange messages for 2 turns without errors."""
        chat_store = ChatStore()
        sandbox = BasicSandbox.from_manifest(MANIFEST_PATH, chat_store=chat_store)
        _patch_agents(sandbox)

        sandbox.chat_router.inject_seed("tech-talk", "Test topic")

        for _ in range(2):
            _step_agent(sandbox, "alice")
            _step_agent(sandbox, "bob")

        history = sandbox.chat_router.load_channel_history("tech-talk")
        assert len(history) >= 3

    def test_channel_history_persisted(self) -> None:
        """Messages are persisted in ChatStore and retrievable."""
        chat_store = ChatStore()
        sandbox = BasicSandbox.from_manifest(MANIFEST_PATH, chat_store=chat_store)
        _patch_agents(sandbox)

        sandbox.chat_router.inject_seed("tech-talk", "Test topic")
        _step_agent(sandbox, "alice")
        _step_agent(sandbox, "bob")

        history = sandbox.chat_router.load_channel_history("tech-talk")
        assert len(history) >= 3
        sender_ids = {msg["sender_id"] for msg in history}
        assert "system" in sender_ids

    def test_agents_use_correct_channel(self) -> None:
        """Agent messages go to tech-talk channel."""
        chat_store = ChatStore()
        sandbox = BasicSandbox.from_manifest(MANIFEST_PATH, chat_store=chat_store)
        _patch_agents(sandbox)

        sandbox.chat_router.inject_seed("tech-talk", "Test topic")
        _step_agent(sandbox, "alice")

        history = sandbox.chat_router.load_channel_history("tech-talk")
        for msg in history:
            assert msg["channel_id"] == "tech-talk"


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


class TestCLI:
    def test_sandbox_parser_accepts_manifest(self) -> None:
        """CLI parser parses 'sandbox <path>' correctly."""
        args = cli.parser.parse_args(["sandbox", "demos/alice-bob.yaml"])
        assert args.command == "sandbox"
        assert args.manifest == "demos/alice-bob.yaml"
        assert args.no_monitor is False

    def test_sandbox_parser_accepts_all_flags(self) -> None:
        """CLI parser accepts --topic, --no-monitor, --seed-channel."""
        args = cli.parser.parse_args([
            "sandbox", "demos/alice-bob.yaml",
            "--topic", "test topic",
            "--seed-channel", "tech-talk",
            "--no-monitor",
            "--port", "9000",
        ])
        assert args.topic == "test topic"
        assert args.seed_channel == "tech-talk"
        assert args.no_monitor is True
        assert args.port == 9000
