# Harvest

Harvest is a Python framework for algorithmic trading. It provides broker integrations, storage backends, eventing, and algorithm abstractions so users can focus on trading logic rather than infrastructure.

The codebase is in transition:
- The legacy runtime centers on `BrokerHub` in `harvest/trader/trader.py`.
- The newer direction is the service-oriented, event-driven `Orchestrator` in `harvest/orchestrator.py`.

## Read This First

- Product and install overview: `README.md`
- Project goals and principles: `ABOUT.md`
- Contributor workflow: `CONTRIBUTING.md`
- Documentation index: `docs/index.md`

## If You Are Working On...

- Runtime orchestration or service wiring: `docs/architecture.md`
- Setup, linting, formatting, or local workflows: `docs/development.md`
- Tests, validation, and safe change boundaries: `docs/testing.md`

## Repo Map

- `harvest/algorithm.py`: Modern algorithm abstraction.
- `harvest/algo.py`: Legacy algorithm API still used by the CLI flow.
- `harvest/cli.py`: CLI entrypoint exposed as `harvest`.
- `harvest/orchestrator.py`: Event-driven service orchestrator.
- `harvest/trader/trader.py`: Legacy `BrokerHub` runtime.
- `harvest/broker/`: Broker and market-data integrations.
- `harvest/storage/`: Local and central storage implementations.
- `harvest/services/`: Service-oriented building blocks.
- `harvest/events/`: Event bus and event definitions.
- `tests/unittest/`: Main automated test suite.
- `tests/livetest/`: Live brokerage/integration tests.
- `examples/`: Usage examples for current and emerging APIs.
- `gui/`: Svelte-based frontend development workspace.

## Non-Negotiable Project Invariants

- Python baseline is 3.12.
- All internal timestamps should be handled in UTC.
- Use modern built-in type hints like `list[str]`, not legacy `typing.List` style.
- Add docstrings for modules, classes, and functions.
- Prefer dataclasses and enums for structured domain data.
- Favor small, focused fixes over broad rewrites.
- Do not deduplicate `LocalAlgorithmStorage` and `CentralStorage` just for style; that duplication is intentional.

## Architectural Guidance

- Prefer extending the newer orchestrator and service architecture for new platform work unless the task is explicitly about the legacy runtime.
- Preserve CLI and legacy behavior unless the change is intentionally a migration.
- When documenting architecture changes, update the docs in `docs/` as part of the same change.

## Development Workflow

- Sync dependencies: `uv sync --extra dev`
- Run unit tests: `uv run python -m unittest discover -s tests/unittest`
- Format Python: `uv format --preview-features format`
- Run Black directly if needed: `uv run python -m black .`
- GUI development: run `npm run dev` from `gui/`

## Documentation Rules

- Keep AGENTS.md short and navigational.
- Put detailed, stable knowledge in `docs/`.
- Prefer updating an existing doc over duplicating the same guidance in multiple places.
- If code and docs disagree, fix the docs or the code in the same change.

## Change Checklist

- Update or add tests when behavior changes.
- Update docs when entrypoints, workflows, or architecture changes.
- Keep examples and CLI-facing guidance consistent with the current implementation.
- Call out whether a change targets the legacy runtime, the orchestrator path, or both.
