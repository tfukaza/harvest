# Development

## Environment

- Python 3.12+
- Dependency and environment management via `uv`
- Frontend development under `gui/` uses npm and Svelte

## Core Commands

### Sync dependencies

```bash
uv sync --extra dev
```

### Run unit tests

```bash
uv run python -m unittest discover -s tests/unittest
```

### Format Python

```bash
uv format --preview-features format
```

### Run Black directly

```bash
uv run python -m black .
```

### Frontend dev server

```bash
cd gui
npm run dev
```

## Coding Expectations

- Use modern Python type hints.
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

## Documentation Practice

- `AGENTS.md` stays short and navigational.
- Add or update focused docs in `docs/` when workflows or architecture change.
- Prefer one canonical explanation per topic.

## Frontend Notes

- The editable frontend workspace is `gui/`.
- Built assets are written into `harvest/gui`.
- Keep frontend documentation aligned with the actual build and runtime flow.
