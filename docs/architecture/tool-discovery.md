# Tool Discovery

**Files:** `harvest/interfaces/tool_definition.py`, `harvest/interfaces/tool_registry.py`, `harvest/agent_sandbox/service_router.py`

The tool discovery system lets agents learn about and activate service-specific tools on demand, rather than having every tool's full specification injected into the system prompt at startup.

## The Problem

A sandbox may have dozens of service tools available. Injecting every tool's full documentation into the system prompt on startup would consume significant token budget even for tools the agent never uses. Tool discovery solves this with a two-phase approach:

1. **Catalogue** — lightweight listing of available tool names and short descriptions (low token cost)
2. **Activation** — full spec injection into the system prompt when the agent requests a specific tool

## InterfaceTool

Each operation a service exposes is described by an `InterfaceTool`:

```python
@dataclass
class InterfaceTool:
    name: str                   # stable, sandbox-unique (e.g. "alpaca_get_stock_bars")
    short_description: str      # one sentence for the catalogue listing
    full_description: str       # detailed docs injected on activation
    arguments: list[ToolArgument]
    returns_description: str
    service_id: str             # owning service
    service_type: str           # "data_source" | "action" | "event_source"
    handler: Callable[..., str] # executes the operation, returns JSON
```

`ToolArgument` carries: `name`, `type` (JSON schema primitive), `description`, `required`, `default`.

### Conversion

```python
tool.to_tool_spec()          # → OpenAI function-calling dict (uses full_description)
tool.to_system_prompt_block() # → markdown block for system prompt injection
```

`to_system_prompt_block()` produces:
```
### alpaca_get_stock_bars
Fetch historical OHLCV bar data for a stock symbol.
Service: alpaca [data_source]

Arguments:
  - symbol (string, required): Stock ticker symbol
  - timeframe (string, optional): Bar width (default: '1d')
  - limit (integer, optional): Number of bars to fetch (default: 100)

Returns: JSON with list of OHLCV bars {t, o, h, l, c, v}

---
```

## ToolRegistry

`ToolRegistry` aggregates `InterfaceTool` instances from all registered services:

```python
registry = ToolRegistry()
registry.register(tool)                    # raises ValueError on name collision
tools = registry.tools_for_policy(policy)  # filters by AgentPolicy.allowed_services
tool = registry.get_tool("alpaca_get_stock_bars")
names = registry.list_tool_names()
```

Thread-safe. Tool names must be globally unique within a sandbox. `tools_for_policy(None)` returns all tools (admin mode).

**Policy filtering** in `tools_for_policy(policy)`:
- For each `InterfaceTool`, check if `policy.allowed_services` contains a `ServicePermission` for its `service_id`
- If the permission's `roles` is `None`, all roles pass
- If `roles` is specified, the tool's `service_type` must match one of the permitted roles
- `EVENT_SOURCE` tools are never exposed (events follow the inbox model)

## discover_tools Tool

The `discover_tools` tool is registered on every agent that has at least one permitted service:

```
discover_tools(tool_name?: string)
```

**Called with no argument** — returns a JSON array (the catalogue):

```json
[
  {"name": "alpaca_get_stock_bars", "short_description": "Fetch historical OHLCV bars.", "service_id": "alpaca", "service_type": "data_source"},
  {"name": "alpaca_place_order", "short_description": "Place a market or limit order.", "service_id": "alpaca", "service_type": "action"},
  {"name": "newsapi_get_top_headlines", "short_description": "Fetch top news headlines.", "service_id": "newsapi", "service_type": "data_source"}
]
```

**Called with `tool_name`** — injects the full spec into the agent's system prompt and returns the spec as JSON:

```json
{
  "name": "alpaca_get_stock_bars",
  "full_description": "...",
  "arguments": [...],
  "returns_description": "...",
  "activated": true
}
```

After activation, the tool's markdown block is appended to the `"tool_specs"` section of the agent's `SystemPromptBuilder`. This section is **permanent for the session** — specs are never cleared once injected.

## Auto-Registration vs. Discovery

Two mechanisms make tools available to agents:

| Mechanism | When | How | Token cost |
|-----------|------|-----|-----------|
| **Auto-registration** | Sandbox startup | `wire_agent_tools()` registers tool callables directly on the agent | Zero (no prompt injection) |
| **Discovery** | On demand, agent-initiated | `discover_tools(tool_name)` injects full spec into system prompt | Paid on first activation |

All permitted tools are auto-registered as callables. The agent can call them immediately without discovery. Discovery is optional but recommended — without the spec in the system prompt, the LLM must infer argument names and types, which is unreliable.

## Tool Spec Injection Flow

```
Agent calls discover_tools("alpaca_get_stock_bars")
    ↓
SandboxServiceRouter.make_discovery_tool() handler
    ↓ tool found in ToolRegistry
inject_callback(agent_id, tool_name) called
    ↓
BasicSandbox._inject_tool_spec(agent_id, tool_name)
    ↓
SystemPromptBuilder.append("tool_specs", tool.to_system_prompt_block())
    ↓ event emitted
ToolSpecsInjected (audit event on event bus)
    ↓
Returns full spec JSON to agent
```

The inject callback is provided by `BasicSandbox` when it calls `router.make_discovery_tool(agent_id, policy, inject_callback=...)`. This decouples the router from the sandbox's SystemPromptBuilder.

## ToolsAutoRegistered Event

When `wire_agent_tools()` completes, a `ToolsAutoRegistered` event is emitted on the event bus listing all registered tool names. This provides an audit record of the agent's initial tool set.
