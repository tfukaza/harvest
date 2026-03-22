# ChatRouter

**File:** `harvest/agent_sandbox/chat.py`

The `ChatRouter` is the message routing core of the agent sandbox — one instance per sandbox, functioning as the sandbox's internal "Slack server." It manages all channels, routes messages, enforces channel membership, handles mentions, and persists chat history.

## Design Principles

- **Unified interface** — agents use the same tools (`send_message`, `read_messages`) regardless of channel type
- **Event-driven** — no dedicated thread, no polling; all work happens in response to events
- **Thread-safe** — a single `threading.Lock` serializes all state mutations
- **Mention-aware** — routes messages with per-recipient notification metadata

## Internal State

```python
class ChatRouter:
    _agents: dict[str, EndpointAddress]
    _channels: dict[str, ChannelDefinition]
    _processors: dict[str, Processor]
    _inboxes: dict[str, list[SandboxMessage]]
    _channel_counters: dict[str, int]
    _store: ChatStore | None
    _lock: threading.Lock
```

## Send Flow

When an agent calls `send_message(channel_id, content)`:

1. The tool handler calls `ChatRouter.send_message(sender_id, channel_id, content)`
2. Router validates: sender is registered, channel exists, sender has write permission
3. Creates a `SandboxMessage` with UUID, sender/recipient addresses, content, and metadata
4. Persists via `ChatStore` if configured
5. Routes by channel type:

### DM Channels
Delivers to the other member. Always sets `metadata={"mention_type": "mention"}` — DMs are inherently direct.

### Group Channels
Delivers to all members except sender. Behavior depends on the channel's `notification_mode`:

- **AMBIENT mode** (default): All messages treated as mentions — `metadata={"mention_type": "mention"}` for every recipient
- **MENTION mode**: Parses `@here` and `@agent-name` from content. Recipients who are mentioned get `mention_type: "mention"`, others get `mention_type: "ambient"`

### Processor Channels
Passes message to the processor's `accept_message()`. If the processor releases (gate opens or batch threshold met), delivers released batch to subscriber inboxes.

6. Fires `on_new_message` callbacks to wake recipient agents

## Mention Parsing

`_parse_mentions(content)` extracts:
- `@here` → `has_here = True` (notifies all members)
- `@agent-name` → adds to `mentioned_ids` set

The regex `@([\w-]+)` supports hyphenated agent IDs (e.g., `@macro-analyst`).

## Seed Injection

`inject_seed(channel_id, content, recipients=None)` injects a message from `"system"` sender into a channel without requiring a registered agent. Used by the CLI and manifest seeds to kick off conversations.

## Reading Messages

- `read_inbox(agent_id)` — returns and clears the agent's inbox
- `peek_inbox(agent_id)` — returns without clearing
- `load_channel_history(channel_id)` — returns full history from ChatStore

## Agent Tools

The ChatRouter exposes these tools to agents (filtered by policy):

| Tool | Purpose |
|------|---------|
| `send_message(channel_id, content)` | Send a message to any channel |
| `read_messages(channel_id?)` | Read inbox or specific channel messages |
| `list_channels()` | List channels the agent belongs to |
| `get_username()` | Get the agent's own ID |
| `create_channel(...)` | Create a new channel (if policy allows) |

## New Message Callbacks

`on_new_message(callback)` registers a callback fired on every message delivery. The callback receives:
```python
callback(channel_id, sender_id, recipient_ids, message_id, channel_type, content)
```

The sandbox uses this to set `wake_signal` on recipient agent handles, interrupting their hibernation sleep.
