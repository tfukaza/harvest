"""Configuration scaffolding for agent-sandbox implementations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class AgentSandboxConfig:
    """Defines the minimal scaffold configuration for an agent sandbox.

    This configuration intentionally describes where future runtime pieces
    should connect without claiming that the runtime behavior already exists.

    Attributes:
        runner_id: Stable identifier for the sandbox instance.
        display_name: Human-readable name for diagnostics and tooling.
        sandbox_namespace: Namespace used for sandbox-local addressing.
        local_store_id: Identifier for the local persistence backend.
        orchestrator_channel: Name of the orchestrator-facing promotion target.
    """

    runner_id: str
    display_name: str
    sandbox_namespace: str = "sandbox"
    local_store_id: str = "default"
    orchestrator_channel: str = "orchestrator"
