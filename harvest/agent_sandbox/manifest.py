"""YAML sandbox manifest loader for declarative multi-agent ecosystems."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from harvest.agent_sandbox.channels import ChannelType, NotificationMode
from harvest.policy import AgentPolicy
from harvest.policy_registry import PolicyRegistry, _parse_policy


@dataclass
class AgentManifestEntry:
    """Parsed agent entry from a sandbox manifest."""

    agent_id: str
    policy_name: str
    model: str
    system_prompt: str


@dataclass
class ChannelManifestEntry:
    """Parsed channel entry from a sandbox manifest."""

    channel_id: str
    channel_type: ChannelType
    description: str = ""
    member_ids: list[str] = field(default_factory=list)
    publisher_ids: list[str] = field(default_factory=list)
    subscriber_ids: list[str] = field(default_factory=list)
    batch_threshold: int = 1
    notification_mode: NotificationMode = NotificationMode.AMBIENT


@dataclass
class SeedEntry:
    """A seed message to inject into a channel at startup."""

    channel_id: str
    content: str
    recipients: list[str] | None = None


@dataclass
class SandboxManifest:
    """Parsed representation of a sandbox YAML manifest."""

    name: str
    policies: dict[str, AgentPolicy]
    agents: dict[str, AgentManifestEntry]
    channels: dict[str, ChannelManifestEntry]
    seeds: list[SeedEntry] = field(default_factory=list)


_CHANNEL_TYPE_MAP = {
    "dm": ChannelType.DM,
    "group": ChannelType.GROUP,
    "processor_gated": ChannelType.PROCESSOR_GATED,
    "processor_aggregation": ChannelType.PROCESSOR_AGGREGATION,
}


def load_manifest(
    path: str | Path,
    *,
    registry: PolicyRegistry | None = None,
) -> SandboxManifest:
    """Parse and validate a sandbox YAML manifest file.

    Policy resolution: merges sandbox-local policies (from the manifest's
    policies section) with the shared PolicyRegistry. Sandbox-local wins
    on name conflicts.

    Args:
        path: Path to the YAML manifest file.
        registry: Optional shared PolicyRegistry.

    Returns:
        Parsed SandboxManifest.

    Raises:
        ValueError: If validation fails.
    """
    with open(path) as f:
        data = yaml.safe_load(f) or {}

    sandbox_data = data.get("sandbox", data)
    name = sandbox_data.get("name", "unnamed")

    # Parse sandbox-local policies
    local_policies: dict[str, AgentPolicy] = {}
    for policy_name, policy_data in sandbox_data.get("policies", {}).items():
        local_policies[policy_name] = _parse_policy(policy_name, policy_data)

    # Build merged policy set for validation
    all_policies: dict[str, AgentPolicy] = {}
    if registry is not None:
        for pname in registry.list_policies():
            all_policies[pname] = registry.get(pname)
    all_policies.update(local_policies)

    # Parse agents
    agents: dict[str, AgentManifestEntry] = {}
    for agent_id, agent_data in sandbox_data.get("agents", {}).items():
        policy_name = agent_data.get("policy", "")
        if policy_name and policy_name not in all_policies:
            raise ValueError(
                f"Agent '{agent_id}' references undefined policy '{policy_name}'"
            )
        agents[agent_id] = AgentManifestEntry(
            agent_id=agent_id,
            policy_name=policy_name,
            model=agent_data.get("model", ""),
            system_prompt=agent_data.get("system_prompt", ""),
        )

    # Parse channels
    channels: dict[str, ChannelManifestEntry] = {}
    for channel_id, channel_data in sandbox_data.get("channels", {}).items():
        type_str = channel_data.get("type", "group")
        channel_type = _CHANNEL_TYPE_MAP.get(type_str)
        if channel_type is None:
            raise ValueError(f"Unknown channel type: {type_str}")

        member_ids = channel_data.get("members", [])
        publisher_ids = channel_data.get("publishers", [])
        subscriber_ids = channel_data.get("subscribers", [])

        # Validate member/publisher/subscriber references
        for mid in member_ids + publisher_ids + subscriber_ids:
            if mid not in agents:
                raise ValueError(
                    f"Channel '{channel_id}' references undefined agent '{mid}'"
                )

        if channel_type == ChannelType.DM and len(member_ids) != 2:
            raise ValueError(
                f"DM channel '{channel_id}' must have exactly 2 members, got {len(member_ids)}"
            )

        if channel_type in (ChannelType.PROCESSOR_GATED, ChannelType.PROCESSOR_AGGREGATION):
            if not publisher_ids:
                raise ValueError(
                    f"Processor channel '{channel_id}' must have at least 1 publisher"
                )
            if not subscriber_ids:
                raise ValueError(
                    f"Processor channel '{channel_id}' must have at least 1 subscriber"
                )

        notif_str = channel_data.get("notification_mode", "ambient")
        notif_mode = NotificationMode(notif_str)

        channels[channel_id] = ChannelManifestEntry(
            channel_id=channel_id,
            channel_type=channel_type,
            description=channel_data.get("description", ""),
            member_ids=member_ids,
            publisher_ids=publisher_ids,
            subscriber_ids=subscriber_ids,
            batch_threshold=channel_data.get("batch_threshold", 1),
            notification_mode=notif_mode,
        )

    # Parse seeds
    seeds: list[SeedEntry] = []
    for seed_data in sandbox_data.get("seeds", []):
        ch_id = seed_data.get("channel")
        if not ch_id:
            raise ValueError("Seed entry missing 'channel' field")
        if ch_id not in channels:
            raise ValueError(f"Seed references undefined channel '{ch_id}'")
        content = seed_data.get("content", "")
        recipients = seed_data.get("recipients")
        if recipients is not None:
            for rid in recipients:
                if rid not in agents:
                    raise ValueError(
                        f"Seed recipient '{rid}' is not a defined agent"
                    )
        seeds.append(SeedEntry(channel_id=ch_id, content=content, recipients=recipients))

    return SandboxManifest(
        name=name,
        policies=all_policies,
        agents=agents,
        channels=channels,
        seeds=seeds,
    )
