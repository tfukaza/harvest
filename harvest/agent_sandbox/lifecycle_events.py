"""Agent lifecycle events for the Harvest agent sandbox.

These events cover agent creation, status transitions, shutdown,
and parent-child management requests/responses.  All types extend
:class:`~harvest.events.base.HarvestEvent`.
"""

from __future__ import annotations

from pydantic import Field

from harvest.events.base import HarvestEvent


# ---------------------------------------------------------------------------
# Status / lifecycle notifications
# ---------------------------------------------------------------------------


class AgentStarted(HarvestEvent):
    """Fired when an agent is registered and enters IDLE state."""

    agent_id: str
    parent_id: str = ""  # empty for root agents
    policy_name: str = ""


class AgentStatusChanged(HarvestEvent):
    """Fired whenever an agent's status transitions."""

    agent_id: str
    old_status: str  # AgentStatus value string
    new_status: str
    reason: str = ""


class AgentStopped(HarvestEvent):
    """Fired when an agent is removed from the sandbox. Terminal event."""

    agent_id: str
    final_status: str  # STOPPED, CRASHED, UNRECOVERABLE
    reason: str = ""  # e.g. "task_complete", "parent_shutdown"


# ---------------------------------------------------------------------------
# Parent-child agent management requests / responses
# ---------------------------------------------------------------------------


class CreateAgentRequest(HarvestEvent):
    """Parent agent requests creation of a child agent."""

    parent_id: str
    agent_id: str
    request_id: str
    model: str = ""  # empty = inherit parent's model
    policy_name: str = ""
    policy_dict: dict = Field(default_factory=dict)
    system_prompt: str = ""


class CreateAgentResponse(HarvestEvent):
    """Sandbox responds to a create request."""

    parent_id: str
    agent_id: str
    request_id: str
    status: str = ""  # "created" or "error"
    error: str = ""


class ShutdownAgentRequest(HarvestEvent):
    """Parent agent (or self) requests shutdown."""

    parent_id: str
    agent_id: str
    request_id: str


class ShutdownAgentResponse(HarvestEvent):
    """Sandbox responds to a shutdown request."""

    parent_id: str
    agent_id: str
    request_id: str
    status: str = ""  # "stopped" or "error"
    error: str = ""


class GetAgentStatusRequest(HarvestEvent):
    """Parent queries a child's current status."""

    parent_id: str
    agent_id: str
    request_id: str


class GetAgentStatusResponse(HarvestEvent):
    """Sandbox returns agent status."""

    parent_id: str
    agent_id: str
    request_id: str
    agent_status: str = ""
    error: str = ""
