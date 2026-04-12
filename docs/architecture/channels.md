# Channels and Notifications

**File:** `harvest/agent_sandbox/channels.py`

All inter-agent communication flows through channels. From an agent's perspective, the interface is identical regardless of channel type — `send_message` and `read_messages` work the same way.

## Channel Types

```python
class ChannelType(Enum):
    GROUP = "group"
    PROCESSOR_GATED = "processor_gated"
    PROCESSOR_AGGREGATION = "processor_aggregation"
```

### Group Channel

N agents, all can send and receive. This is the only member-based channel type — it covers both 1-on-1 and multi-member conversations.

```python
GroupChannel(
    channel_id="team-discussion",
    member_ids=["alice", "bob", "charlie"],
    notification_mode=NotificationMode.AMBIENT,
)

# Two-member channel with no write locking
GroupChannel(
    channel_id="alice-bob",
    member_ids=["alice", "bob"],
    staking_enabled=False,
)
```

The `staking_enabled` flag controls whether the channel uses write locking (FIFO staking). When enabled (the default), agents must acquire an exclusive write lock before sending, preventing concurrent writes. Small channels can disable this for immediate sends.

### Processor Channels

Channels with publisher/subscriber roles and buffered delivery:

**Gated** — subscribers receive messages only after ALL publishers have sent at least one message. Once the gate opens, subsequent messages pass through immediately.

```python
GatedProcessorChannel(
    channel_id="etl-gate",
    publisher_ids=["data-agent", "model-agent"],
    subscriber_ids=["report-agent"],
)
```

**Aggregation** — subscribers receive messages in batches when a count threshold is reached.

```python
AggregationProcessorChannel(
    channel_id="batch-collector",
    publisher_ids=["worker"],
    subscriber_ids=["summarizer"],
    batch_threshold=5,
)
```

## Notification Modes

```python
class NotificationMode(Enum):
    AMBIENT = "ambient"
    MENTION = "mention"
```

Notification mode controls how the ChatRouter tags messages with `mention_type` metadata, which in turn controls how the hibernation system formats wake prompts for agents.

### AMBIENT Mode (default)

All messages are treated as direct notifications. Every recipient gets `mention_type: "mention"`. This is the simple default — every message in the channel triggers a full notification for every member.

Use case: small channels where all messages are relevant to all members.

### MENTION Mode

Messages are parsed for `@here` and `@agent-name` mentions:

- **`@here`** — all members get `mention_type: "mention"`
- **`@agent-name`** — only the named agent gets `mention_type: "mention"`
- **Unmentioned members** get `mention_type: "ambient"`

Use case: larger channels or channels where not every message requires every agent's attention.

## How Notifications Reach Agents

The mention metadata flows through the system:

1. **ChatRouter** sets `metadata={"mention_type": "mention"|"ambient"}` on each `SandboxMessage`
2. **InboxEventSource** propagates `mention_type` from message metadata into `WakeEvent.payload`
3. **Hibernation loop** formats wake events:
   - Mention events → `@sender in #channel: content` (full message, strong signal)
   - Ambient events → `N new messages in #channel` (soft summary, weak signal)

This mimics Slack's behavior: mentioned messages show full content with a red badge, while unmentioned channel activity shows a bold channel name without urgency.

## YAML Configuration

In a manifest, channels specify their type and notification mode:

```yaml
channels:
  team-discussion:
    type: group
    members: [alice, bob, charlie]
    notification_mode: ambient    # default

  alice-bob:
    type: group
    members: [alice, bob]
    staking_enabled: false        # no write locking for small channels

  large-channel:
    type: group
    members: [alice, bob, charlie, dave, eve]
    notification_mode: mention    # only @mentions trigger strong notifications
```
