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

## Known Gaps

- Test coverage is uneven across legacy and newer architecture.
- Treat missing tests as a signal to add focused coverage, not as a reason to broaden the change scope unnecessarily.
