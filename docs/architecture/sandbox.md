# Agent Sandbox

**File:** `harvest/agent_sandbox/basic_sandbox.py`

The `BasicSandbox` is the concrete sandbox implementation that hosts multiple LLM-backed agents. It owns the ChatRouter, manages agent threads, enforces policies, and mediates between agents and the framework.

## Core Responsibilities

- Agent registration, lifecycle, and per-agent threading
- ChatRouter instance ownership (one per sandbox)
- Policy enforcement (tool access, channel permissions, child agent creation)
- Event bus integration (receive framework events, fan out to agents)
- Hibernation loop (agents sleep, wake on events, run LLM step)

## Internal State

```python
class BasicSandbox(AgentSandbox):
    _config: AgentSandboxConfig
    _agents: dict[str, _AgentHandle]      # agent_id → handle
    _lock: threading.Lock                  # protects _agents
    _chat_router: ChatRouter               # one per sandbox
    _policy_registry: PolicyRegistry | None
    _event_bus: EventBus | None
    _running: bool
```

Each agent is wrapped in an `_AgentHandle`:

```python
class _AgentHandle:
    agent: Agent
    policy: AgentPolicy | None
    thread: threading.Thread | None
    stop_event: threading.Event
    wake_signal: threading.Event
    event_sources: list[EventSource]
```

## Agent Threading

Each registered agent gets its own daemon thread running the hibernation loop (see [hibernation.md](hibernation.md)). Threads are started when the sandbox starts, or immediately on registration if the sandbox is already running.

```
register_agent(agent_id, agent, policy=policy)
  → creates _AgentHandle
  → wires agent to ChatRouter (sets agent_id, _chat_router, calls _wire_chat_router)
  → adds InboxEventSource
  → registers wake-on-message callback
  → starts thread if sandbox is running
```

## Agent Wiring

When an agent is registered, the sandbox:

1. Sets `agent.agent_id` and `agent._chat_router`
2. Calls `agent._wire_chat_router(router, policy)` — registers chat tools (send_message, read_messages, list_channels, get_username) filtered by the agent's policy
3. Calls `agent._wire_service_router(service_router)` — registers service tools (fetch_data, execute_action, read_event_notifications, discover_tools) and auto-registers interface tools from permitted services
4. Creates a `SystemPromptBuilder` for the agent
5. Sets `agent._system_prompt_fn` to a closure that calls `builder.build(agent.config.system_prompt)` on every LLM invocation
6. Adds an `InboxEventSource` to the agent's event sources
7. Registers a callback on the ChatRouter's `on_new_message` hook so incoming messages for this agent trigger `wake_signal.set()`

See [service-router.md](service-router.md) for service tool details and [system-prompt.md](system-prompt.md) for dynamic section management.

## Event Fan-Out

`handle_event(event_type, payload)` translates a framework event into an agent-facing input and calls `step()` on every hosted agent. Results are recorded in `_last_dispatch_results`.

## Lifecycle

```python
await sandbox.start()   # set _running, start all agent threads
await sandbox.stop()    # signal stop, shutdown agents, join threads, clear registry
```

`health_check()` returns per-agent thread liveness and running state.

## from_manifest()

The `from_manifest()` class method creates a fully wired sandbox from a YAML manifest file:

1. Parses the manifest via `load_manifest(path)`
2. Creates the sandbox with merged PolicyRegistry
3. For each agent in the manifest:
   - Creates a `HarvestAgentConfig` with the agent's model and system prompt
   - Injects an **identity footer** into the system prompt telling the agent its ID and mention conventions
   - Creates a `HarvestAgent` and registers it with the sandbox
4. For each channel in the manifest:
   - Creates the appropriate channel type (DM, Group, GatedProcessor, AggregationProcessor)
   - Registers it on the ChatRouter with the correct notification mode
5. Returns the sandbox in a ready-but-not-started state

### Identity Footer

Every agent gets an auto-injected footer appended to its system prompt:

```
---
Your agent ID is `alice`. Other agents and the system refer to you as @alice.
When you see a message from @alice, that is *you* — do not respond to your own
messages. When another agent or the moderator mentions @alice in their message,
they are addressing you directly and you should respond.
```

This ensures agents know their own identity without requiring it in the manifest's system prompt.

## AdminMessageQueue

The `BasicSandbox` accepts an optional `admin_queue` parameter (`AdminMessageQueue`) at construction. When provided, it enables human-in-the-loop message injection via the debug monitor. The queue's `on_enqueue` callback is wired to `_handle_admin_message`, which injects the human message into the appropriate channel or agent. This allows operators to intervene in live simulations without restarting the sandbox.

## SyncEventBus

Each sandbox creates a per-sandbox synchronous event bus (`sandbox_bus`, an instance of `SyncEventBus`) named `sandbox-{runner_id}`. Internal components (ChatRouter, ServiceRouter, SandboxGateway) subscribe to and dispatch events on this bus. The `SandboxGateway` relays whitelisted event types between the `sandbox_bus` and the orchestrator-level `event_bus`, providing event isolation — sandbox-internal events stay local unless explicitly promoted.

## Parent-Child Agent Tracking

`BasicSandbox` tracks the lifecycle of dynamically created child agents through three maps:

- `_parent_map: dict[str, str]` — maps each child `agent_id` to its `parent_id`
- `_agent_policies: dict[str, AgentPolicy]` — stores the policy for every registered agent
- `_shutdown_reasons: dict[str, str]` — records why each agent was stopped (e.g., parent request, error)

The sandbox listens for `CreateAgentRequest`, `ShutdownAgentRequest`, and `GetAgentStatusRequest` events on the `sandbox_bus`. Parent agents can only shut down their own children (verified against `_parent_map`). `AgentStarted` and `AgentStopped` events are dispatched on the bus so other components can react to lifecycle changes.
