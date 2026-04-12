# Development

## Environment

- Python 3.12+
- Dependency and environment management via `uv`
- Frontend development under `gui/` uses npm and SvelteKit

## Core Commands

### Sync dependencies

```bash
uv sync --extra dev
```

### Run unit tests

```bash
uv run pytest tests/unittest
```

### Run end-to-end tests

```bash
uv run pytest tests/e2e
```

### Run all tests (excluding live tests)

```bash
uv run pytest tests/ --ignore=tests/livetest
```

### Format Python

```bash
uv run python -m black .
```

### Frontend dev server

```bash
cd gui
npm install
npm run dev
```

### Build frontend

```bash
cd gui
npm run build
```

Output goes to `gui/build/`. The debug monitor server serves from this directory.

### Run a sandbox demo

```bash
harvest sandbox demos/alice-bob.yaml
harvest sandbox demos/conspiracy.yaml
```

### Run single-agent chat

```bash
harvest agent --model anthropic/claude-haiku-4-5-20251001
```

## Coding Expectations

- Use modern Python type hints (`list[str]`, `X | Y`, `X | None`).
- Add docstrings for public and non-trivial code.
- Prefer enums and dataclasses over magic strings and ad-hoc shapes.
- Keep changes narrow and avoid unrelated cleanup unless it directly improves the task.
- Preserve existing user-facing behavior unless the change is intentionally a migration.

## Logging and Diagnostics

Follow the logging guidance in `CONTRIBUTING.md`.

- `DEBUG` for internal decisions and execution detail.
- `INFO` for important user-triggered events.
- `WARNING` for recoverable issues.
- `ERROR` for user-fixable failures.
- Raise exceptions for unrecoverable states.

The `harvest sandbox` command suppresses LiteLLM/httpx/harvest INFO logs by default to keep console output focused.

## Documentation Practice

- Architecture docs live in `docs/architecture/` (see `docs/index.md`).
- Phase plans are historical records in `docs/phase-*.md`.
- `AGENTS.md` stays short and navigational.
- Add or update focused docs in `docs/` when workflows or architecture change.
- Prefer one canonical explanation per topic.

## Frontend Notes

- The SvelteKit project is in `gui/`.
- Uses Tailwind CSS v4 via `@tailwindcss/vite` plugin.
- Built assets go to `gui/build/`.
- The `DebugMonitorServer` auto-detects `gui/build/` relative to the package root.
- Import CSS as `@import "tailwindcss"` in `gui/src/app.css`.
