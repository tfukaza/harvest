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

## Enforcement

The sandbox enforces policies at tool registration time via `HarvestAgent._wire_chat_router()`. Only tools listed in `allowed_tools` are registered with the agent's LLM toolset. An agent never sees tools it's not allowed to use — they're simply not in its tool list.
