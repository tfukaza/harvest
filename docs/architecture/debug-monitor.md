# Debug Monitor

**Files:** `harvest/debug/server.py`, `harvest/debug/registry.py`, `harvest/debug/snapshot.py`
**Frontend:** `gui/`

The debug monitor is a live observation tool for running sandboxes. It provides a WebSocket-based server that streams sandbox state to a Slack-style SvelteKit frontend.

## Architecture

```
BasicSandbox ──register──→ SandboxRegistry ←──snapshot──→ DebugMonitorServer ──WebSocket──→ Browser
                                                              │
                                                              └── Static file serving (gui/build/)
```

The debug server supports a bidirectional WebSocket — the frontend can inject admin messages into sandbox channels.

## SandboxRegistry

`harvest/debug/registry.py`

An in-process registry that tracks active `BasicSandbox` instances:

```python
registry = SandboxRegistry()
registry.register("my-sandbox", sandbox)
snapshots = registry.snapshot_all()  # list[SandboxSnapshot]
```

The registry builds snapshots by reading each sandbox's public APIs:
- `list_agents()` + `get_agent_handle()` for agent info and thread liveness
- `chat_router.list_channels()` for channel info
- Message buffer (bounded `deque(maxlen=500)`) populated via `on_new_message` callbacks

## DebugMonitorServer

`harvest/debug/server.py`

Flask-based server with `flask-sock` for WebSocket support:

```python
from harvest.agent_sandbox.admin_queue import AdminMessageQueue

admin_queue = AdminMessageQueue()
server = DebugMonitorServer(
    registry=registry,
    host="127.0.0.1",
    port=8100,
    static_dir="gui/build/",  # optional
    admin_queue=admin_queue,  # optional; enables admin mode
)
server.start()  # runs in background thread
```

### WebSocket Protocol

**On connect:** sends a full snapshot immediately.

**Every ~1 second (server → client):** if new messages exist, sends a delta containing only new messages.

**Every ~5 seconds (server → client):** sends a full re-sync snapshot regardless of changes. Corrects client-side drift and picks up structural changes.

**Client → server:** `admin_send` messages inject content into sandbox channels as the "admin" sender.

#### Server-to-client message types

```json
{"type": "snapshot", "timestamp": "...", "sandboxes": [...]}
{"type": "delta", "timestamp": "...", "messages": [...]}
{"type": "typing", "sandbox_id": "...", "channel_id": "...", "agent_id": "...", "active": true}
{"type": "agent_status", "sandbox_id": "...", "agent_id": "...", "status": "active"}
{"type": "admin_queued", "sandbox_id": "...", "channel_id": "...", "message_id": "..."}
{"type": "admin_blocked", "reason": "..."}
```

#### Client-to-server message types

```json
{"type": "admin_send", "sandbox_id": "...", "channel_id": "...", "content": "..."}
```

The server places the message into an `AdminMessageQueue`. The sandbox should poll `admin_queue.drain()` on each tick to inject pending messages via `chat_router.send_message("admin", channel_id, content, ...)`.

The "admin" sender bypasses channel membership checks (`_sender_allowed` returns `True` for `sender_id == "admin"`).

### REST Endpoint

`GET /api/snapshot` — returns current snapshot as JSON (useful for `curl` debugging).

## Frontend

The SvelteKit frontend (`gui/`) renders a Slack-style UI:

### Sidebar (purple, #3f0e40)
- Sandbox name with connection indicator
- Clickable channel list (filters messages)
- Agent list with thread-alive indicators

### Message Pane
- Slack-style message grouping (consecutive messages from same sender collapsed)
- Deterministic colored avatars based on agent ID hash
- Channel badges when viewing "all messages"
- System/seed messages as centered dividers
- Auto-scroll to bottom on new messages
- Markdown rendering via `marked`

### Tech Stack
- SvelteKit with `@sveltejs/adapter-static`
- Tailwind CSS v4 (via `@tailwindcss/vite` plugin)
- TypeScript
- WebSocket with auto-reconnect (1s, 2s, 4s, max 10s backoff)

### Structured Logging

All frontend logging goes through `gui/src/lib/logger.ts` with `[harvest]` prefix and subsystem tags (`[ws]`, `[state]`, `[render]`). This is designed for AI-assisted debugging via console output.

### Build

```bash
cd gui && npm run build
```

Output goes to `gui/build/`. The `DebugMonitorServer` serves from this directory when `static_dir` is provided.

## CLI Integration

The debug monitor starts automatically with `harvest sandbox`:

```bash
harvest sandbox demos/conspiracy.yaml          # monitor on by default at :8100
harvest sandbox demos/conspiracy.yaml --no-monitor  # disable monitor
harvest sandbox demos/conspiracy.yaml --port 9000   # custom port
```

Or run standalone:

```bash
harvest debug-server --port 8100 --static-dir gui/build/
```
