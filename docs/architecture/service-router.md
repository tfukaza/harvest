# Service Router

**File:** `harvest/agent_sandbox/service_router.py`

The `SandboxServiceRouter` is the "corporate firewall" between agents and external services. Every fetch, action, and event an agent interacts with goes through it. Agents never hold direct references to `Service` instances.

## Responsibilities

- Maintain the sandbox-level service registry (Level 1 policy)
- Enforce per-agent `AgentPolicy.allowed_services` (Level 2 policy) on every interaction
- Register four generic agent tools: `fetch_data`, `execute_action`, `read_event_notifications`, `discover_tools`
- Emit audit events to the event bus for every interaction
- Deliver external events to subscribed agents and wake them

## Architecture

```
Agent thread
    ↓ calls tool
fetch_data / execute_action / read_event_notifications / discover_tools
    ↓
SandboxServiceRouter._do_fetch() / _do_execute()
    ↓ policy check (Level 1 ∩ Level 2)
Service.fetch() / Service.execute()
    ↓ returns DataResult / ActionResult
JSON string returned to agent
    + audit event emitted on event bus
```

One `SandboxServiceRouter` is created per `BasicSandbox`. It is wired into `BasicSandbox` at construction time.

## Two-Level Policy

**Level 1 — Sandbox registry:** Only services registered with `register_service()` are accessible at all. Unregistered services cannot be reached regardless of agent policy.

**Level 2 — Agent policy:** `AgentPolicy.allowed_services` is a tuple of `ServicePermission` entries. Each entry specifies a `service_id` and an optional `roles` frozenset. When `roles` is `None`, all roles the service declares are permitted.

Both levels must pass for a request to reach the service. If either fails, the request returns `{"error": "policy_denied"}` and a corresponding audit event is emitted.

```python
# Level 2 check
for perm in policy.allowed_services:
    if perm.service_id == service_id:
        if perm.roles is None or role in perm.roles:
            return True  # permitted
return False  # denied
```

## Generic Agent Tools

Four tools are registered on every agent (subject to policy):

### `fetch_data(service_id, query_type, params?)`

Wraps `Service.fetch()` for DATA_SOURCE services.

```json
{"service_id": "newsapi", "query_type": "top_headlines", "params": {"page_size": 5}}
```

Returns JSON string. Error key is set on failure.

### `execute_action(service_id, command_type, params?)`

Wraps `Service.execute()` for ACTION services.

```json
{"service_id": "paper", "command_type": "place_order", "params": {"symbol": "AAPL", "side": "buy", "qty": 10}}
```

Returns JSON string.

### `read_event_notifications()`

Drains the agent's pending event queue. Returns a JSON list of notification objects. Each has `source_id`, `event_type`, and `payload`. After calling, the queue is empty and the `event_notifications` section of the system prompt is cleared.

### `discover_tools(tool_name?)`

See [tool-discovery.md](tool-discovery.md).

## Sync/Async Bridge

Agent tools run in threads managed by `BasicSandbox`. Services are async. The router bridges this with `_run_coro()`:

```python
def _run_coro(coro):
    try:
        asyncio.get_running_loop()
        # Already in an async context (unusual) — use a dedicated thread
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        # No running loop (normal for agent threads)
        return asyncio.run(coro)
```

This is called for every `fetch()` and `execute()` invocation.

## Event Bus Audit Trail

Every interaction emits a pair of events:

| Interaction | Events emitted |
|-------------|----------------|
| `fetch_data` | `DataFetchRequested` → `DataFetchCompleted` |
| `execute_action` | `ActionRequested` → `ActionCompleted` |
| External event delivery | `ExternalEventDelivered` (per agent) |
| Auto-registration | `ToolsAutoRegistered` |
| Spec injection | `ToolSpecsInjected` |

The `error` field on completed events is non-empty when policy denied or the service raised an exception.

## Event Subscriptions

When a service has `EVENT_SOURCE` role, agents can subscribe to receive its events:

```python
router.subscribe_agent("analyst", "alpaca")
```

When the service publishes an `ExternalEventFired` event on the bus, the router:
1. Delivers it to all subscribed agents' pending queues
2. Calls the agent's wake callback so the hibernation loop processes it
3. Calls the event notification callback to add a note to the system prompt

Agents drain their queue with `read_event_notifications()`.

## Interface Tool Auto-Registration

`wire_agent_tools(agent_id, policy)` returns `(tool_spec, callable)` pairs for all `InterfaceTool` entries the policy permits. These are registered directly on the agent's `_tools` and `_tool_map`. The agent can call them by name from the LLM tool loop — no `fetch_data` indirection needed for these.

See [tool-discovery.md](tool-discovery.md) for how tools are discovered and their specs injected.

## Usage

```python
from harvest.agent_sandbox.service_router import SandboxServiceRouter
from harvest.services.paper_broker import PaperBrokerService

router = SandboxServiceRouter(sandbox_id="my-sandbox", event_bus=bus)
router.register_service(PaperBrokerService())

# Wire generic tools onto an agent
service_tools, service_tool_map = router.make_service_tools(agent_id, policy)
agent._tools.extend(service_tools)
agent._tool_map.update(service_tool_map)

# Wire interface tools (auto-registered)
pairs = router.wire_agent_tools(agent_id, policy)
for spec, fn in pairs:
    agent._tools.append(spec)
    agent._tool_map[spec["function"]["name"]] = fn
```

`BasicSandbox` handles all of this automatically in `register_agent()`.
