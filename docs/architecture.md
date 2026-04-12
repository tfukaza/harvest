# Architecture

This document has been split into focused subsystem documents under `architecture/`.

## Quick Navigation

### Agent Sandbox

| Document | Scope |
|----------|-------|
| [architecture/overview.md](architecture/overview.md) | High-level system diagram, runtime paths, shared infrastructure |
| [architecture/sandbox.md](architecture/sandbox.md) | BasicSandbox: hosting, threading, lifecycle, from_manifest() |
| [architecture/agent.md](architecture/agent.md) | HarvestAgent: LLM loop, tools, identity, conversation compaction, multi-LLM |
| [architecture/manifest.md](architecture/manifest.md) | YAML manifest format, loading, validation, seeds |
| [architecture/policies.md](architecture/policies.md) | AgentPolicy, PolicyRegistry, service permissions, child policy modes |

### Communication

| Document | Scope |
|----------|-------|
| [architecture/chat-router.md](architecture/chat-router.md) | ChatRouter: message routing, delivery, staking, agent tools |
| [architecture/channels.md](architecture/channels.md) | Channel types (group, processor), mention system, notification modes |
| [architecture/processors.md](architecture/processors.md) | GatedProcessor and AggregationProcessor channel buffering |
| [architecture/hibernation.md](architecture/hibernation.md) | Hibernation loop, EventSources, wake event formatting |

### Services & Tools

| Document | Scope |
|----------|-------|
| [architecture/services.md](architecture/services.md) | Unified Service ABC, ServiceRole, concrete services (Alpaca, Paper, NewsAPI, Perplexity) |
| [architecture/service-router.md](architecture/service-router.md) | SandboxServiceRouter: two-level policy, generic tools, audit events |
| [architecture/tool-discovery.md](architecture/tool-discovery.md) | InterfaceTool, ToolRegistry, discover_tools, spec injection |
| [architecture/system-prompt.md](architecture/system-prompt.md) | SystemPromptBuilder: dynamic sections, tool specs, event notifications |

### Infrastructure

| Document | Scope |
|----------|-------|
| [architecture/events.md](architecture/events.md) | Event bus, typed event taxonomy, audit trail |
| [architecture/storage.md](architecture/storage.md) | ChatStore, ConversationStore, market/account storage, FlexibleStorage |
| [architecture/debug-monitor.md](architecture/debug-monitor.md) | Debug server, bidirectional WebSocket, admin mode, SvelteKit frontend |
| [architecture/logging.md](architecture/logging.md) | JSONFormatter, log_event(), structured logging setup |
| [architecture/cli.md](architecture/cli.md) | CLI commands: sandbox, agent, debug-server, event-server |

Start with [overview.md](architecture/overview.md) for the big picture, then drill into the subsystem that matches your task.

## Historical Context

The original agent-runner design docs are preserved for reference:

- `agent.md` — original agent behavior boundary design
- `agent-runner.md` — original sandbox/runner design vision (pre-implementation)
- `phase-*.md` — implementation plans for each development phase
