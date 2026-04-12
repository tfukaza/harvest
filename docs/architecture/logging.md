# Structured Logging

**File:** `harvest/logging_config.py`

Harvest provides structured JSON logging for machine-readable audit trails alongside human-readable console output.

## Setup

```python
from harvest.logging_config import setup_logging

setup_logging(
    log_file="harvest.jsonl",  # newline-delimited JSON
    level=logging.INFO,
    json_file=True,
    console=True,              # human-readable stdout
)
```

This configures the `"harvest"` logger with two handlers:
- `FileHandler` using `JSONFormatter` → writes to `harvest.jsonl`
- `StreamHandler` using the standard text formatter → writes to stdout

## JSONFormatter

`JSONFormatter` converts log records to JSON lines with these fields:

```json
{
  "timestamp": "2026-03-22T10:00:00.000000+00:00",
  "level": "INFO",
  "logger": "harvest.agent_sandbox.basic_sandbox",
  "message": "agent.step.start",
  "event": "agent.step.start",
  "sandbox_id": "my-sandbox",
  "agent_id": "researcher",
  "data": {"input_length": 42}
}
```

The `event`, `sandbox_id`, `agent_id`, and `data` fields are added by `log_event()` via `extra=`.

## log_event() Helper

```python
from harvest.logging_config import log_event
import logging

logger = logging.getLogger(__name__)

log_event(
    logger,
    "agent.step.start",
    sandbox_id="my-sandbox",
    agent_id="researcher",
    data={"input_length": len(message)},
)
```

## Event Taxonomy

| Event | When |
|-------|------|
| `sandbox.start` | BasicSandbox starts |
| `sandbox.stop` | BasicSandbox stops |
| `agent.registered` | Agent added to sandbox |
| `agent.step.start` | Agent step begins |
| `agent.step.end` | Agent step completes |
| `agent.llm.call` | LLM completion requested |
| `agent.llm.response` | LLM response received |
| `agent.tool.call` | Tool invoked |
| `agent.tool.result` | Tool returned |
| `agent.tool.error` | Tool raised exception |
| `message.sent` | Message delivered to channel |
| `service.fetch` | Data fetch routed through service router |
| `service.execute` | Action executed through service router |
| `service.discover` | Agent called discover_tools |
| `context.compact` | Conversation history compacted |
| `admin.message.queued` | Admin message placed in queue |

## Integration

Call `setup_logging()` before starting the sandbox or debug server:

```python
from harvest.logging_config import setup_logging

setup_logging("run.jsonl")

sandbox = BasicSandbox.from_manifest("demos/trading.yaml")
sandbox.start()
```

The JSON log file can be queried with `jq`:

```bash
jq 'select(.event == "agent.tool.call")' run.jsonl
jq 'select(.agent_id == "trader")' run.jsonl
```
