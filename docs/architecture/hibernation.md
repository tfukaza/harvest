# Hibernation System

**File:** `harvest/agent_sandbox/hibernation.py`
**Loop:** `harvest/agent_sandbox/basic_sandbox.py` (`_agent_loop`)

Agents don't run continuously. They hibernate — sleeping in jittered intervals, waking when events arrive, running one LLM step, then going back to sleep.

## Why Hibernation

Without hibernation, every agent would spin in a tight loop calling the LLM on every iteration, consuming API quota even when there's nothing to do. Hibernation solves this:

- **Rate limiting** — jittered sleep throttles API calls naturally
- **Staggering** — random intervals prevent all agents from responding to the same message simultaneously
- **Event-driven wake** — agents can be interrupted immediately when something relevant happens

## The Loop

```
while not stop_event:
    1. Sleep for random(HIBERNATION_POLL_MIN, HIBERNATION_POLL_MAX) seconds
       (or until wake_signal is set)
    2. Poll all EventSources for this agent
    3. If no events → go back to sleep
    4. Format events into a prompt string
    5. Call agent.step(prompt)
    6. Clean up any channel stakes
```

**Timing constants:**
- `HIBERNATION_POLL_MIN = 1.0` seconds
- `HIBERNATION_POLL_MAX = 5.0` seconds

The jitter is per-wake-cycle, not fixed. Each sleep duration is independently randomized.

## Wake Signals

Each agent has a `threading.Event` called `wake_signal`. When a new message arrives for the agent (via the ChatRouter's `on_new_message` callback), the signal is set, interrupting the sleep immediately. This means agents respond to messages within milliseconds rather than waiting for the next poll cycle.

## EventSources

An `EventSource` is a pluggable component that produces `WakeEvent`s when polled:

```python
class EventSource(ABC):
    @abstractmethod
    def poll(self, agent_id: str) -> list[WakeEvent]

@dataclass
class WakeEvent:
    source_type: str       # e.g., "inbox", "silence_detector"
    payload: dict[str, Any]
```

### Built-in EventSources

**InboxEventSource** — reads the agent's inbox from the ChatRouter. Produces one `WakeEvent` per unread message with payload:

```python
{
    "channel_id": "team-discussion",
    "sender_id": "alice",
    "content": "Hey, what do you think about...",
    "mention_type": "mention"  # or "ambient"
}
```

The `mention_type` is propagated from the message's metadata (set by the ChatRouter based on channel notification mode and mention parsing).

**SilenceDetectorSource** — fires a wake event after N seconds of no messages in any channel. Useful for having agents check in or initiate conversation when things go quiet.

### Custom EventSources

Additional event sources can be registered via `sandbox.add_event_source(agent_id, source)`. This allows extending the wake system for:

- External API polling
- Timer-based periodic tasks
- Cross-sandbox signals
- Custom monitoring triggers

## Wake Event Formatting

`_format_wake_events(events)` converts `WakeEvent`s into a prompt string:

**Mention events** (DMs, @here, @name):
```
@alice in #team-discussion: Hey, what do you think about...
```

**Ambient events** (group messages without a mention):
```
3 new messages in #team-discussion
```

**Non-inbox events** (silence detector, custom sources):
```
[event:silence_detector] {"seconds_silent": 30}
```

Mention events show full content — the agent sees exactly what was said. Ambient events show only a count — the agent knows something happened but must use `read_messages` to see the content. This directly implements the Slack-style notification hierarchy.
