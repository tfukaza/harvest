# Channels and Notifications

**File:** `harvest/agent_sandbox/channels.py`

All inter-agent communication flows through channels. From an agent's perspective, the interface is identical regardless of channel type — `send_message` and `read_messages` work the same way.

## Channel Types

```python
class ChannelType(Enum):
    DM = "dm"
    GROUP = "group"
    PROCESSOR_GATED = "processor_gated"
    PROCESSOR_AGGREGATION = "processor_aggregation"
```

### DM Channel

Two agents, bidirectional. Messages always notify the recipient (no ambient mode).

```python
DMChannel(channel_id="dm:alice:bob", member_ids=["alice", "bob"])
```

DM channel IDs follow the convention `dm:{sorted_id_1}:{sorted_id_2}` for deterministic lookup.

### Group Channel

N agents, all can send and receive. The primary channel type for team discussions.

```python
GroupChannel(
    channel_id="team-discussion",
    member_ids=["alice", "bob", "charlie"],
    notification_mode=NotificationMode.AMBIENT,
)
```

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

## DM Behavior

DMs always use mention-level notification regardless of any notification mode setting. When you send a DM, the recipient always gets the full message content in their wake prompt.

## YAML Configuration

In a manifest, channels specify their notification mode:

```yaml
channels:
  team-discussion:
    type: group
    members: [alice, bob, charlie]
    notification_mode: ambient    # default

  large-channel:
    type: group
    members: [alice, bob, charlie, dave, eve]
    notification_mode: mention    # only @mentions trigger strong notifications
```
