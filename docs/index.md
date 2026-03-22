# Documentation Index

This directory is the repository-local source of truth for project knowledge that coding agents and contributors need during development.

Start small. Read only the document that matches the task.

## Core Documents

- Repository map and agent entrypoint: `../AGENTS.md`
- User-facing overview and installation: `../README.md`
- Project goals and design values: `../ABOUT.md`
- Contributor workflow: `../CONTRIBUTING.md`

## Architecture

The architecture docs live under `architecture/` and cover the current implemented state of the system.

- **[architecture/overview.md](architecture/overview.md)** — Start here. High-level system diagram, two runtime paths (Orchestrator + Agent Sandbox), shared infrastructure.
- **[architecture/sandbox.md](architecture/sandbox.md)** — BasicSandbox: agent hosting, per-agent threading, lifecycle, from_manifest(), identity footer.
- **[architecture/chat-router.md](architecture/chat-router.md)** — ChatRouter: unified message routing, send/read flow, mention parsing, agent tools, seed injection.
- **[architecture/channels.md](architecture/channels.md)** — Channel types (DM, group, processor), NotificationMode (AMBIENT vs MENTION), @here/@name conventions.
- **[architecture/hibernation.md](architecture/hibernation.md)** — Hibernation loop, jittered sleep, wake signals, EventSources, wake event formatting.
- **[architecture/manifest.md](architecture/manifest.md)** — YAML manifest format, section reference, validation, seed messages, demo manifests.
- **[architecture/policies.md](architecture/policies.md)** — AgentPolicy, PolicyRegistry, ChildPolicyMode, policy resolution in manifests.
- **[architecture/agent.md](architecture/agent.md)** — HarvestAgent: LiteLLM integration, tool system, step(), conversation compaction.
- **[architecture/debug-monitor.md](architecture/debug-monitor.md)** — Debug server (Flask + WebSocket), SandboxRegistry, Slack-style SvelteKit frontend, Tailwind CSS.
- **[architecture/cli.md](architecture/cli.md)** — CLI reference: `harvest sandbox`, `harvest agent`, `harvest debug-server`, etc.

## Historical Design Docs

These documents capture the original design vision before implementation. The architecture/ docs above reflect the current state.

- Agent behavior boundary (original design): `agent.md`
- Agent runner sandbox design (original vision): `agent-runner.md`

## Engineering Docs

- Local development workflow and conventions: `development.md`
- Testing strategy and validation commands: `testing.md`

## Phase Plans

Implementation plans for each development phase (historical reference):

- Phase 1: `phase-1.md` — Deconstruction and runtime foundations
- Phase 2: `phase-2.md` — Agent and runner scaffolding
- Phase 3: `phase-3.md` — Legacy runtime removal
- Phase 4: `phase-4.md` — First agent proof-of-concept
- Phase 4.5: `phase-4.5.md` — Storage infrastructure decoupling
- Phase 5: `phase-5.md` — First agent-runner proof-of-concept
- Phase 6: `phase-6.md` — Event bus server and test clients
- Phase 7: `phase-7.md` — Conversation compaction
- Phase 8: `phase-8.md` — Bubus event bus migration
- Phase 9: `phase-9.md` — Unified channel-based chat system
- Phase 10: `phase-10.md` — Agent lifecycle, policy system, ChatRouter wiring
- Phase 11: `phase-11.md` — Concrete BasicSandbox, YAML manifest
- Phase 12: `phase-12.md` — Debug monitor server and SvelteKit frontend
- Phase 12.5: `phase-12.5.md` — Alice & Bob end-to-end demo

## How To Use This Directory

- Use `AGENTS.md` as the table of contents for quick navigation.
- Start with `architecture/overview.md` for the big picture.
- Drill into the specific subsystem doc that matches your task.
- Phase docs are historical plans — check architecture/ for current state.
- Update docs when behavior, workflows, or architecture materially changes.
