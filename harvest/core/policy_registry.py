"""YAML-backed policy registry for named agent policies."""


from pathlib import Path

import yaml

from harvest.interfaces.service import ServicePermission, ServiceRole
from harvest.core.policy import AgentPolicy, ChildPolicyMode, EventSubscriptions


class PolicyRegistry:
    """Loads and serves named policies from a YAML config file."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        """Initialize the registry, optionally loading from YAML.

        Args:
            config_path: Path to a YAML file defining named policies.
        """
        self._policies: dict[str, AgentPolicy] = {}
        if config_path:
            self._load(config_path)

    def _load(self, path: str | Path) -> None:
        """Load policies from a YAML file.

        Args:
            path: Path to the YAML file.
        """
        with open(path) as f:
            data = yaml.safe_load(f) or {}

        policies_data = data.get("policies", {})
        for name, policy_data in policies_data.items():
            self._policies[name] = _parse_policy(name, policy_data)

    def get(self, name: str) -> AgentPolicy:
        """Get a policy by name.

        Args:
            name: Policy name.

        Returns:
            The named AgentPolicy.

        Raises:
            KeyError: If the policy name is not found.
        """
        return self._policies[name]

    def list_policies(self) -> list[str]:
        """Return all registered policy names.

        Returns:
            Sorted list of policy names.
        """
        return sorted(self._policies.keys())

    def register(self, policy: AgentPolicy) -> None:
        """Programmatically register a policy.

        Args:
            policy: The policy to register.
        """
        self._policies[policy.name] = policy


def _parse_policy(name: str, data: dict) -> AgentPolicy:
    """Parse a policy from YAML dict data.

    Args:
        name: Policy name.
        data: Dict from YAML.

    Returns:
        Parsed AgentPolicy.
    """
    allowed_tools = frozenset(data.get("allowed_tools", []))
    can_send = data.get("can_send_messages", True)
    can_create_channel = data.get("can_create_channel", False)
    can_create_agents = data.get("can_create_agents", False)
    child_mode_str = data.get("child_policy_mode", "none")
    child_mode = ChildPolicyMode(child_mode_str)
    allowed_child = tuple(data.get("allowed_child_policies", []))
    allowed_services = _parse_allowed_services(data.get("allowed_services", []))
    cognitive_tools = frozenset(data.get("cognitive_tools", []))

    event_subs_data = data.get("event_subscriptions")
    event_subs = None
    if event_subs_data is not None:
        evt_types = event_subs_data.get("allowed_event_types")
        wake_sources = event_subs_data.get("allowed_wake_sources")
        event_subs = EventSubscriptions(
            allowed_event_types=frozenset(evt_types) if evt_types is not None else None,
            allowed_wake_sources=frozenset(wake_sources) if wake_sources is not None else None,
        )

    return AgentPolicy(
        name=name,
        allowed_tools=allowed_tools,
        can_send_messages=can_send,
        can_create_channel=can_create_channel,
        can_create_agents=can_create_agents,
        child_policy_mode=child_mode,
        allowed_child_policies=allowed_child,
        allowed_services=allowed_services,
        event_subscriptions=event_subs,
        cognitive_tools=cognitive_tools,
    )


def _parse_allowed_services(entries: list) -> tuple[ServicePermission, ...]:
    """Parse the allowed_services list from YAML.

    Supports two forms::

        # Bare string — all roles:
        - alpaca

        # Dict with optional role filter:
        - service_id: alpaca
          roles: [data_source]

    Args:
        entries: Raw YAML list.

    Returns:
        Tuple of :class:`~harvest.interfaces.service.ServicePermission` instances.
    """
    result: list[ServicePermission] = []
    for entry in entries:
        if isinstance(entry, str):
            # Bare string = all roles
            result.append(ServicePermission(service_id=entry))
        elif isinstance(entry, dict):
            service_id = entry.get("service_id", "")
            if not service_id:
                raise ValueError(f"allowed_services entry missing 'service_id': {entry}")
            raw_roles = entry.get("roles")
            if raw_roles is None:
                roles = None
            else:
                roles = frozenset(ServiceRole(r) for r in raw_roles)
            result.append(ServicePermission(service_id=service_id, roles=roles))
        else:
            raise ValueError(f"Invalid allowed_services entry: {entry!r}")
    return tuple(result)
