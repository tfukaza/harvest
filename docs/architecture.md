# Architecture

This document has been split into focused subsystem documents under `architecture/`.

## Quick Navigation

| Document | Scope |
|----------|-------|
| [architecture/overview.md](architecture/overview.md) | High-level system diagram, runtime paths, shared infrastructure |
| [architecture/sandbox.md](architecture/sandbox.md) | BasicSandbox: hosting, threading, lifecycle, from_manifest() |
| [architecture/chat-router.md](architecture/chat-router.md) | ChatRouter: message routing, delivery, agent tools |
| [architecture/channels.md](architecture/channels.md) | Channel types (DM, group, processor), mention system, notification modes |
| [architecture/hibernation.md](architecture/hibernation.md) | Hibernation loop, EventSources, wake event formatting |
| [architecture/manifest.md](architecture/manifest.md) | YAML manifest format, loading, validation, seeds |
| [architecture/policies.md](architecture/policies.md) | AgentPolicy, PolicyRegistry, child policy modes |
| [architecture/agent.md](architecture/agent.md) | HarvestAgent: LLM loop, tools, identity, conversation compaction |
| [architecture/debug-monitor.md](architecture/debug-monitor.md) | Debug server, WebSocket protocol, Slack-style SvelteKit frontend |
| [architecture/cli.md](architecture/cli.md) | CLI commands: sandbox, agent, debug-server, event-server |

Start with [overview.md](architecture/overview.md) for the big picture, then drill into the subsystem that matches your task.

## Historical Context

The original agent-runner design docs are preserved for reference:

- `agent.md` — original agent behavior boundary design
- `agent-runner.md` — original sandbox/runner design vision (pre-implementation)
- `phase-*.md` — implementation plans for each development phase
