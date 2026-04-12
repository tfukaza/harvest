# CLI Reference

**File:** `harvest/cli.py`
**Entry point:** `harvest` (installed via `pyproject.toml` console script)

## Commands

### `harvest sandbox <manifest.yaml>`

Run a multi-agent sandbox from a YAML manifest. This is the primary way to run agent sandboxes.

```bash
harvest sandbox demos/alice-bob.yaml
harvest sandbox demos/conspiracy.yaml --no-monitor
harvest sandbox demos/alice-bob.yaml --topic "microservices vs monoliths"
```

**Arguments:**

| Flag | Default | Description |
|------|---------|-------------|
| `manifest` | (required) | Path to YAML manifest file |
| `--topic` | none | Seed message to inject (in addition to manifest seeds) |
| `--seed-channel` | first group channel | Channel for `--topic` seed |
| `--kickstart` | all members | Specific agent to receive the seed |
| `--no-monitor` | false | Disable the debug monitor server |
| `--host` | 127.0.0.1 | Debug monitor bind address |
| `--port` | 8100 | Debug monitor port |

**Behavior:**

1. Loads the manifest and creates a `BasicSandbox` via `from_manifest()`
2. Starts the debug monitor (unless `--no-monitor`)
3. Injects manifest-level seeds first, then any `--topic` seed
4. Starts the sandbox — agents run autonomously via hibernation loop
5. Blocks until Ctrl+C

**Logging:** Suppresses LiteLLM, httpx, and harvest INFO logging to keep console output focused on agent conversations.

### `harvest agent`

Run a single-agent interactive chat session.

```bash
harvest agent --model anthropic/claude-sonnet-4-20250514
harvest agent --message "What is 2+2?"
harvest agent --session my-session --no-compaction
```

| Flag | Default | Description |
|------|---------|-------------|
| `--model` | from env | LiteLLM model name |
| `--system-prompt` | default | System prompt |
| `--message` | none | One-shot message (non-interactive) |
| `--session` | none | Session name for persistence |
| `--no-persist` | false | Skip conversation persistence |
| `--context-limit` | 128000 | Context window size |
| `--compaction-threshold` | 0.75 | Compaction trigger ratio |
| `--no-compaction` | false | Disable compaction |

### `harvest debug-server`

Start the debug monitor server standalone (with an empty registry).

```bash
harvest debug-server --port 8100 --static-dir gui/build/
```

### `harvest event-server`

Start the HTTP event bus server.

```bash
harvest event-server --port 8000
```

### `harvest event-client`

Interact with the event bus server.

```bash
harvest event-client send --event-type test --payload '{"key": "value"}'
harvest event-client listen --event-type test --client-id my-client
harvest event-client stream --event-type test
```

### `harvest visualize`

Render a chart from a Harvest data file.

```bash
harvest visualize data.csv
harvest visualize data.pickle
```
