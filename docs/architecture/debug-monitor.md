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

The debug server is strictly read-only — it observes sandbox state but never mutates it.

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
server = DebugMonitorServer(
    registry=registry,
    host="127.0.0.1",
    port=8100,
    static_dir="gui/build/",  # optional
)
server.start()  # runs in background thread
```

### WebSocket Protocol

**On connect:** sends a full snapshot immediately.

**Every ~1 second:** if new messages exist, sends a delta containing only new messages.

**Every ~5 seconds:** sends a full re-sync snapshot regardless of changes. This corrects any client-side drift and picks up structural changes (agent added/removed, channel created/destroyed).

Message types:

```json
{"type": "snapshot", "timestamp": "...", "sandboxes": [...]}
{"type": "delta", "timestamp": "...", "messages": [...]}
```

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
