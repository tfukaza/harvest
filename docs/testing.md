# Testing

## Test Layout

- `tests/unittest/`: main automated test suite
- `tests/livetest/`: live broker and integration tests that require real external systems
- `pytest.ini`: repository-level pytest configuration

## Default Validation Flow

For most backend changes, run:

```bash
uv run python -m unittest discover -s tests/unittest
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
- Treat missing tests as a signal to add focused coverage, not as a reason to broaden the change scope unnecessarily.
