"""YAML-backed policy registry for named agent policies."""

from __future__ import annotations

from pathlib import Path

import yaml

from harvest.policy import AgentPolicy, ChildPolicyMode


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

    return AgentPolicy(
        name=name,
        allowed_tools=allowed_tools,
        can_send_messages=can_send,
        can_create_channel=can_create_channel,
        can_create_agents=can_create_agents,
        child_policy_mode=child_mode,
        allowed_child_policies=allowed_child,
    )
