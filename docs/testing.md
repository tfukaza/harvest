# Testing

## Test Layout

- `tests/unittest/` — main automated test suite
- `tests/e2e/` — end-to-end tests (mocked LLM, full pipeline)
- `tests/livetest/` — live broker and integration tests (require credentials)
- `pytest.ini` — repository-level pytest configuration

### Unit Test Organization

Tests are organized by subsystem:

| Directory | Coverage |
|-----------|----------|
| `tests/unittest/agent/` | HarvestAgent, conversation history, tool calling |
| `tests/unittest/channels/` | ChatRouter, channel types, mention system, notification modes |
| `tests/unittest/sandbox/` | BasicSandbox, hibernation loop, wake event formatting |
| `tests/unittest/contracts/` | Architecture contracts (Agent, Runtime, Resource) |
| `tests/unittest/scaffolding/` | Placeholder schema and sanity checks |
| `tests/unittest/events/` | Event bus, event payloads |
| `tests/unittest/services/` | Service-oriented runtime tests |
| `tests/unittest/storage/` | Storage backends, ChatStore, ConversationStore |
| `tests/unittest/broker/` | Broker integrations |
| `tests/unittest/cli/` | CLI commands |
| `tests/unittest/server/` | Event server and client |
| `tests/unittest/debug/` | Debug monitor, SandboxRegistry, snapshots |

### End-to-End Tests

`tests/e2e/test_alice_bob.py` tests the full multi-agent pipeline with mocked LLM completions:

- Manifest loading and validation
- Sandbox creation from manifest
- Channel wiring and seed injection
- Multi-turn agent conversation through ChatRouter
- CLI argument parsing and integration

## Default Validation Flow

For most backend changes:

```bash
uv run pytest tests/unittest
```

For full validation (excluding live tests):

```bash
uv run pytest tests/ --ignore=tests/livetest
```

For changes to the agent sandbox system specifically:

```bash
uv run pytest tests/unittest/channels/ tests/unittest/sandbox/ tests/e2e/
```

## Live Testing

- Do not run live tests casually.
- Never commit secrets.
- Prefer unit coverage and mocked LLM tests over live API calls.

## Validation by Change Type

### Agent sandbox changes

- Run `tests/unittest/channels/` for ChatRouter and channel behavior
- Run `tests/unittest/sandbox/` for sandbox hosting and hibernation
- Run `tests/e2e/` for full pipeline validation

### CLI changes

- Run `tests/unittest/cli/` for CLI parsing
- Run `tests/e2e/` for CLI integration tests

### Storage changes

- Run `tests/unittest/storage/` for persistence

### Frontend changes

- `cd gui && npm run build` — verify the build succeeds
- Manual verification via the debug monitor

### Documentation changes

- Ensure links, commands, and file paths are current
- Ensure docs match current code behavior
