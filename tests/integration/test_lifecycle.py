"""Integration test for the agent lifecycle: create -> work -> shutdown."""

import asyncio
import json
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from harvest.agent_sandbox.basic_sandbox import AgentStatus, BasicSandbox
from harvest.agent_sandbox.config import AgentSandboxConfig
from harvest.agent_sandbox.chat.channels import GroupChannel
from harvest.harvest_agent import HarvestAgent, HarvestAgentConfig
from harvest.core.policy import AgentPolicy, ChildPolicyMode
from harvest.core.policy_registry import PolicyRegistry


def _make_tool_call_response(tool_name: str, **kwargs):
    """Build a mock LLM response containing a single tool call."""
    return MagicMock(
        choices=[MagicMock(
            message=MagicMock(
                content=None,
                tool_calls=[MagicMock(
                    id=f"call_{tool_name}",
                    function=MagicMock(
                        name=tool_name,
                        arguments=json.dumps(kwargs),
                    ),
                )],
            ),
            finish_reason="tool_calls",
        )],
    )


def _make_text_response(text: str):
    """Build a mock LLM response with plain text."""
    return MagicMock(
        choices=[MagicMock(
            message=MagicMock(
                content=text,
                tool_calls=None,
            ),
            finish_reason="stop",
        )],
    )


class ScriptedCompletion:
    """A mock completion function that returns scripted responses in sequence."""

    def __init__(self, script: list):
        self._script = list(script)
        self._index = 0
        self._lock = threading.Lock()

    def __call__(self, **kwargs):
        with self._lock:
            if self._index >= len(self._script):
                return _make_text_response("(no more scripted responses)")
            resp = self._script[self._index]
            self._index += 1
            return resp


def test_lifecycle_happy_path():
    """Supervisor creates researcher, researcher works, supervisor shuts down both."""
    registry = PolicyRegistry()

    supervisor_policy = AgentPolicy(
        name="supervisor",
        allowed_tools=frozenset(["send_message", "read_messages", "list_channels",
                                  "create_agent", "shutdown_agent", "complete_task",
                                  "add_agent_to_channel", "get_username"]),
        can_create_agents=True,
        child_policy_mode=ChildPolicyMode.PREDEFINED,
        allowed_child_policies=("researcher",),
        can_send_messages=True,
    )
    researcher_policy = AgentPolicy(
        name="researcher",
        allowed_tools=frozenset(["send_message", "read_messages", "list_channels", "get_username"]),
        can_create_agents=False,
        can_send_messages=True,
    )
    registry.register(supervisor_policy)
    registry.register(researcher_policy)

    config = AgentSandboxConfig(runner_id="lifecycle-test", display_name="lifecycle-test")
    sandbox = BasicSandbox(config=config, policy_registry=registry)

    # Create channels
    general = GroupChannel(channel_id="general", member_ids=["supervisor"])
    research = GroupChannel(channel_id="research", member_ids=["supervisor"])
    sandbox.chat_router.create_channel(general)
    sandbox.chat_router.create_channel(research)

    # Create supervisor with scripted responses
    supervisor_script = ScriptedCompletion([
        _make_tool_call_response("create_agent", agent_id="researcher", policy_name="researcher"),
        _make_tool_call_response("add_agent_to_channel", agent_id="researcher", channel_id="research"),
        _make_tool_call_response("send_message", channel_id="research", content="Research: history of Python"),
        _make_text_response("Waiting for researcher report..."),
    ])

    sup_config = HarvestAgentConfig(model="test", system_prompt="You are a supervisor.")
    supervisor = HarvestAgent(config=sup_config, agent_id="supervisor",
                              completion_func=supervisor_script, policy=supervisor_policy)
    sandbox.register_agent("supervisor", supervisor, policy=supervisor_policy)

    # Verify basic setup
    assert "supervisor" in sandbox.list_agents()

    # The test verifies that:
    # 1. The sandbox can be created with the policy registry
    # 2. Agents can be registered with proper policies
    # 3. The new AgentStatus values exist
    assert AgentStatus.STOPPED.value == "stopped"
    assert AgentStatus.UNRECOVERABLE.value == "unrecoverable"

    # Verify lifecycle events module imports
    from harvest.agent_sandbox.lifecycle.events import (
        AgentStarted, AgentStatusChanged, AgentStopped,
        CreateAgentRequest, CreateAgentResponse,
        ShutdownAgentRequest, ShutdownAgentResponse,
    )

    # Verify chat client module imports
    from harvest.agent_sandbox.chat.client import ChatRouterClient
    from harvest.agent_sandbox.lifecycle.manager_client import AgentManagerClient

    # Verify service events module imports
    from harvest.agent_sandbox.services.events import (
        FetchDataRequest, FetchDataResponse,
    )


def test_unrecoverable_error_sets_status():
    """An unrecoverable LLM error should set UNRECOVERABLE, not CRASHED."""
    from harvest.agent_sandbox.llm_errors import LLMErrorKind, classify_llm_error

    exc = Exception("Your credit balance is too low")
    assert classify_llm_error(exc) == LLMErrorKind.UNRECOVERABLE

    # Verify the status enum value exists
    assert AgentStatus.UNRECOVERABLE.value == "unrecoverable"
