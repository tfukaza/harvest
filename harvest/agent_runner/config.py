"""Configuration scaffolding for future agent-runner implementations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class AgentRunnerConfig:
    """Defines the minimal scaffold configuration for an agent runner.

    This configuration intentionally describes where future runtime pieces
    should connect without claiming that the runtime behavior already exists.

    Attributes:
        runner_id: Stable identifier for the runner instance.
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
