# Testing

## Test Layout

- `tests/unittest/`: main automated test suite
- `tests/livetest/`: live broker and integration tests that require real external systems
- `pytest.ini`: repository-level pytest configuration

The unit-test suite is organized into subdirectories that reflect the surviving architecture rather than the removed legacy runtime model.

The target layout for the refactor is:

- `tests/unittest/contracts/` for high-level architecture contracts such as `Agent`, `Runtime`, and `Resource`
- `tests/unittest/scaffolding/` for placeholder `agent_runner` schemas and sanity checks
- `tests/unittest/events/` for event bus and event payload coverage
- `tests/unittest/services/` for service-oriented runtime tests
- `tests/unittest/storage/` for storage tests
- `tests/unittest/broker/` for broker tests
- `tests/unittest/cli/` only for any CLI surface that still survives after legacy deletion

## Default Validation Flow

For most backend changes, run:

```bash
uv run pytest tests/unittest
```

For formatting-only or documentation-only changes, test scope can be narrower, but call that out explicitly in review or changelog notes.

## Live Testing

Live tests are higher risk and may require credentials or external service availability.

- Do not run live tests casually.
- Never commit secrets.
- Prefer unit coverage and targeted local validation unless the change actually affects broker integrations.

## Validation Expectations By Change Type

### Documentation changes

- Ensure links, commands, and file paths are current.
- Ensure docs match current code behavior.

### CLI or workflow changes

- Validate the documented command still works.
- Update `README.md`, `CONTRIBUTING.md`, and any affected docs together.

### Runtime or storage changes

- Run targeted unit tests where possible.
- Prefer root-cause fixes over compatibility shims.
- Be explicit about whether the change affects legacy runtime, orchestrator, or both.

### Test-suite reorganization

- Remove tests that only preserve deleted legacy behavior.
- Prefer moving tests into architecture-aligned subdirectories instead of keeping a flat namespace.
- Rewrite surviving tests so they validate the current architecture rather than historical entrypoints.
- Keep scaffolding tests intentionally light: import checks, contract checks, schema checks, and basic shape validation are usually enough.
- Do not write deep behavior tests for components that are still placeholders by design.

## TDD Expectations For Phase 1 Architecture Work

- Write or update focused unit tests before implementing new Phase 1 architecture code.
- Keep Phase 1 tests centered on interfaces, typed contracts, and component boundaries.
- Treat `Agent` as the self-contained AI loop abstraction. It should own its own reasoning state and tool-use decisions.
- Treat `Runtime` as the sandbox and integration boundary. It should own event-bus integration, resource binding, tool exposure, lifecycle management, and framework mediation for one or more hosted agents.
- Do not couple `Agent` tests directly to event bus wiring, service discovery, or resource capability advertisement.
- Do not over-specify implementation details for autonomous multi-agent collaboration in Phase 1.
- Reserve detailed inter-agent messaging, group chat behavior, multi-agent routing semantics, and deeper runtime coordination behavior for Phase 2.

For Phase 1, the goal is to lock down the architectural seams so the later autonomous multi-agent system can be implemented on top of stable contracts.

## Known Gaps

- Test coverage is uneven across legacy and newer architecture.
- Coverage for scaffold-only code is intentionally light and focused on contracts, imports, and basic schema shape.
- Treat missing tests as a signal to add focused coverage, not as a reason to broaden the change scope unnecessarily.
