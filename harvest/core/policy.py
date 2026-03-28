"""Agent policy system for the Harvest agent sandbox."""


import enum
from dataclasses import dataclass


class ChildPolicyMode(enum.Enum):
    """Controls how a spawning agent assigns policies to its children."""

    NONE = "none"
    CLONE = "clone"
    PREDEFINED = "predefined"
    DEFINE = "define"


@dataclass(frozen=True)
class EventSubscriptions:
    """Declarative filter for which events reach an agent.

    Attributes:
        allowed_event_types: Set of HarvestEvent class names the agent receives
            via handle_event(). e.g. {"ExternalEventFired", "PriceUpdated"}.
            None means all.
        allowed_wake_sources: Set of WakeEvent source_type strings the agent
            wakes for during hibernation. e.g. {"inbox", "silence"}.
            None means all.
    """

    allowed_event_types: frozenset[str] | None = None
    allowed_wake_sources: frozenset[str] | None = None


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
        allowed_services: Services the agent may access, with optional role
            restrictions.  Each entry is a
            :class:`~harvest.interfaces.service.ServicePermission` specifying
            a ``service_id`` and optionally a subset of
            :class:`~harvest.interfaces.service.ServiceRole` values.

            - ``ServicePermission("alpaca")`` — all roles
            - ``ServicePermission("alpaca", roles=frozenset({ServiceRole.DATA_SOURCE}))``
              — read-only access, no order placement
            - Default deny: an empty tuple means no service access.

        The sandbox-level service registry acts as Level 1 (allowlist);
        ``allowed_services`` is the Level 2 per-agent filter.
        cognitive_tools: Set of cognitive tool groups to enable for the agent.
            Valid values: ``"think"``, ``"memory"`` (save/get/list), ``"todo"``.
    """

    name: str
    allowed_tools: frozenset[str] = frozenset()
    can_send_messages: bool = True
    can_create_channel: bool = False
    can_create_agents: bool = False
    child_policy_mode: ChildPolicyMode = ChildPolicyMode.NONE
    allowed_child_policies: tuple[str, ...] = ()
    allowed_services: tuple = ()  # tuple[ServicePermission, ...]
    event_subscriptions: EventSubscriptions | None = None
    cognitive_tools: frozenset[str] = frozenset()  # e.g. {"think", "memory", "todo"}
