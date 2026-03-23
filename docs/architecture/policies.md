# Policy System

**Files:** `harvest/policy.py`, `harvest/policy_registry.py`

Policies define what an agent is allowed to do within a sandbox. Every agent can have an associated `AgentPolicy` that the sandbox enforces at tool-call time.

## AgentPolicy

```python
@dataclass
class AgentPolicy:
    name: str
    allowed_tools: list[str]
    can_send_messages: bool = True
    can_create_channel: bool = False
    can_create_agents: bool = False
    child_policy_mode: ChildPolicyMode = ChildPolicyMode.NONE
    allowed_child_policies: list[str] = field(default_factory=list)
```

### Fields

| Field | Effect |
|-------|--------|
| `allowed_tools` | Only these tool names are exposed to the agent |
| `can_send_messages` | Controls access to `send_message` tool |
| `can_create_channel` | Controls access to `create_channel` tool |
| `can_create_agents` | Controls access to `create_agent` tool |
| `child_policy_mode` | How child agent policies are determined |
| `allowed_child_policies` | For `PREDEFINED` mode: list of policy names the agent can assign to children |

### Child Policy Modes

```python
class ChildPolicyMode(Enum):
    NONE = "none"          # Cannot create children
    CLONE = "clone"        # Children inherit parent's policy
    PREDEFINED = "predefined"  # Children must use a named policy from the registry
    DEFINE = "define"      # Parent can define a custom policy for each child
```

## PolicyRegistry

A shared registry of named policies that can be referenced by manifests and sandbox configurations:

```python
registry = PolicyRegistry()
registry.register(policy)                    # register by policy.name
policy = registry.get("analyst")             # retrieve by name
names = registry.list_policies()             # list all registered names
```

Can be loaded from a YAML file:

```python
registry = PolicyRegistry.from_yaml("policies.yaml")
```

## Policy Resolution in Manifests

When loading a manifest, policies are resolved in this order:

1. **Sandbox-local** — defined inline in the manifest's `policies` section
2. **Shared registry** — from the `PolicyRegistry` passed to `load_manifest()`

Sandbox-local definitions win on name conflicts. This lets a manifest customize a shared policy without modifying the global registry.

## Service Permissions

`allowed_services` is a tuple of `ServicePermission` entries controlling which external services an agent can access:

```python
@dataclass(frozen=True)
class ServicePermission:
    service_id: str
    roles: frozenset[ServiceRole] | None  # None = all roles the service declares
```

This is the second level of a two-level policy system:

- **Level 1 (sandbox):** Only services registered with `SandboxServiceRouter.register_service()` are available at all
- **Level 2 (agent):** `allowed_services` controls which of those the agent can reach, and with which roles

```python
AgentPolicy(
    name="analyst",
    can_send_messages=True,
    allowed_services=(
        ServicePermission("alpaca", roles=frozenset({ServiceRole.DATA_SOURCE})),
        ServicePermission("newsapi"),   # all roles (data source only anyway)
        ServicePermission("perplexity"),
    ),
)
```

In this example, the analyst can read market data from Alpaca but cannot place orders (`ACTION` role denied).

### YAML Format

```yaml
policies:
  analyst:
    can_send_messages: true
    can_create_agents: false
    allowed_services:
      - alpaca                        # all roles alpaca declares
      - service_id: newsapi
        roles: [data_source]          # explicit role restriction
      - perplexity                    # shorthand: all roles

  trader:
    can_send_messages: true
    allowed_services:
      - service_id: alpaca
        roles: [data_source, action]  # data reads + order placement
      - newsapi
```

### Enforcement

Service permission enforcement happens in `SandboxServiceRouter._do_fetch()` and `_do_execute()`. When an agent calls `fetch_data` or `execute_action`, the router checks both levels before calling the service. Denied requests return `{"error": "policy_denied"}` and emit a `DataFetchCompleted` or `ActionCompleted` audit event with the error set.

For interface tools (auto-registered via `wire_agent_tools()`), filtering happens at registration time: the `ToolRegistry.tools_for_policy()` method only returns tools for services and roles the agent is permitted to access.

## Event Subscriptions

`event_subscriptions` controls which events an agent receives. Without this field, agents receive all events (backward-compatible default). When set, it filters two independent dispatch paths:

- **`allowed_event_types`** — filters framework events delivered via `BasicSandbox.handle_event()`. Values are `HarvestEvent` class names (e.g. `ExternalEventFired`, `PriceUpdated`, `AgentLifecycleChanged`). `None` means all; an empty list means none.
- **`allowed_wake_sources`** — filters `WakeEvent` source types during the agent's hibernation poll loop. Values are source type strings (e.g. `inbox`, `silence`). `None` means all; an empty list means none.

### YAML Format

```yaml
policies:
  # Chat-only agent: only wakes for inbox messages, no framework events
  chatter:
    can_send_messages: true
    event_subscriptions:
      allowed_wake_sources:
        - inbox

  # Parent using a processor-gated channel: suppresses lifecycle events
  # since the channel processor already aggregates child completion
  parent_with_processor:
    can_create_agents: true
    child_policy_mode: clone
    event_subscriptions:
      allowed_event_types:
        - ExternalEventFired
        - PriceUpdated

  # Service agent: wakes on inbox + external events only
  analyst:
    allowed_services:
      - newsapi
      - perplexity
    event_subscriptions:
      allowed_wake_sources:
        - inbox
      allowed_event_types:
        - ExternalEventFired
```

### Enforcement

Event subscription filtering happens at dispatch time:

- **`handle_event()`** in `BasicSandbox` checks `allowed_event_types` before forwarding the event to `agent.step()`
- **`_agent_loop()`** in `BasicSandbox` checks `allowed_wake_sources` after polling `EventSource`s, filtering out non-subscribed wake events before formatting the wake prompt

## Enforcement Summary

| What | Where enforced | How |
|------|---------------|-----|
| Chat tools (`send_message`, etc.) | `HarvestAgent._wire_chat_router()` | Only permitted tools registered |
| Service data access (`fetch_data`) | `SandboxServiceRouter._do_fetch()` | Runtime check before each call |
| Service actions (`execute_action`) | `SandboxServiceRouter._do_execute()` | Runtime check before each call |
| Interface tool auto-registration | `ToolRegistry.tools_for_policy()` | Filtered at agent wiring time |
| Child agent creation | `HarvestAgent._register_create_agent_tool()` | Tool only registered if `can_create_agents=True` |
| Framework events | `BasicSandbox.handle_event()` | Skipped if `event_type` not in `allowed_event_types` |
| Wake events | `BasicSandbox._agent_loop()` | Filtered by `allowed_wake_sources` after polling |
