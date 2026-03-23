# Channel Processors

**Files:** `harvest/agent_sandbox/gated_processor.py`, `harvest/agent_sandbox/aggregation_processor.py`, `harvest/agent_sandbox/processors.py`

Processor channels intercept messages and apply buffering logic before delivering them to subscribers. From the sender's perspective, they behave identically to group channels — `send_message` works the same way.

See [channels.md](channels.md) for channel type overview and notification modes.

## Abstract Contract

```python
class MessageProcessor(ABC):
    endpoint: EndpointAddress

    def process_message(self, message: SandboxMessage) -> list[SandboxMessage]:
        """Accept a message and return zero or more messages to deliver."""

    def flush(self) -> list[SandboxMessage]:
        """Force-release any buffered messages."""

    def get_state_snapshot(self) -> dict:
        """Return a JSON-serializable snapshot for debugging."""
```

The `ChatRouter` calls `process_message()` on each incoming message. If the processor returns a non-empty list, those messages are delivered to subscribers. If empty, delivery is held.

## GatedProcessor

**File:** `harvest/agent_sandbox/gated_processor.py`

Buffers messages from all publishers until each required publisher has sent at least one message. When the gate opens, all buffered messages are released at once. After that, messages flow through immediately.

```
Publisher A sends → buffered
Publisher B sends → buffered (gate still closed)
Publisher C sends → gate opens! A+B+C messages released
Publisher A sends again → delivered immediately (gate stays open)
```

This is useful when multiple agents each produce a piece of required context before a downstream agent should act. The `GatedProcessorChannel` ensures the subscriber never processes partial context.

```python
GatedProcessorChannel(
    channel_id="research-gate",
    publisher_ids=["data-agent", "model-agent", "sentiment-agent"],
    subscriber_ids=["decision-agent"],
)
```

**Thread safety:** Internal state protected by a `threading.Lock`.

**`flush()`:** Releases all buffered messages immediately regardless of gate state. Used by `ChatRouter` when a sandbox stops.

## AggregationProcessor

**File:** `harvest/agent_sandbox/aggregation_processor.py`

Buffers messages until a configurable count threshold is reached, then releases the entire batch.

```
Worker sends message 1 → buffered (count: 1)
Worker sends message 2 → buffered (count: 2)
...
Worker sends message N → batch released (count reached threshold)
```

This is useful when a summarizer should process a batch of inputs rather than each item individually.

```python
AggregationProcessorChannel(
    channel_id="work-batch",
    publisher_ids=["worker"],
    subscriber_ids=["summarizer"],
    batch_threshold=5,
)
```

**Thread safety:** Internal state protected by a `threading.Lock`.

**`flush()`:** Releases any buffered messages even if the threshold hasn't been reached.

## Processor Configs

```python
@dataclass
class GatedReleaseProcessorConfig:
    processor_id: str
    required_dependency_ids: tuple[str, ...]  # publisher IDs that must all send
    output_recipient_id: str

@dataclass
class AggregationProcessorConfig:
    processor_id: str
    release_after_message_count: int
    output_recipient_id: str
```

These configs are used by the `ChatRouter` when constructing processor channels from manifest definitions. The `output_recipient_id` is the subscriber that receives the released batch.

## YAML Configuration

```yaml
channels:
  research-gate:
    type: processor_gated
    publishers: [data-agent, model-agent]
    subscribers: [decision-agent]

  work-batches:
    type: processor_aggregation
    publishers: [worker]
    subscribers: [summarizer]
    batch_threshold: 5
```

## How ChatRouter Uses Processors

When a message is sent to a processor channel:

1. `ChatRouter._send_message_internal()` detects the channel is a `ProcessorChannel`
2. Calls `processor.process_message(message)`
3. If the processor returns messages, delivers them to `subscriber_ids`
4. If empty, silently buffers — the sender receives `{"status": "ok"}` regardless

Publishers do not need to know whether their messages were buffered or delivered immediately.
