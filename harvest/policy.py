"""Agent policy system for the Harvest agent sandbox."""

from __future__ import annotations

import enum
from dataclasses import dataclass


class ChildPolicyMode(enum.Enum):
    """Controls how a spawning agent assigns policies to its children."""

    NONE = "none"
    CLONE = "clone"
    PREDEFINED = "predefined"
    DEFINE = "define"


@dataclass(frozen=True)
class AgentPolicy:
    """Defines the permissions granted to an agent.

    Attributes:
        name: Policy name for identification.
        allowed_tools: Tool names the agent may use.
        can_send_messages: Whether the agent can send messages to channels.
        can_create_channel: Whether the agent can create new channels.
        can_create_agents: Whether the agent can spawn child agents.
        child_policy_mode: How the agent assigns policies to children.
        allowed_child_policies: Policy names allowed when mode is PREDEFINED.
    """

    name: str
    allowed_tools: frozenset[str] = frozenset()
    can_send_messages: bool = True
    can_create_channel: bool = False
    can_create_agents: bool = False
    child_policy_mode: ChildPolicyMode = ChildPolicyMode.NONE
    allowed_child_policies: tuple[str, ...] = ()
