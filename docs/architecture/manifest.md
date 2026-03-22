# YAML Sandbox Manifest

**File:** `harvest/agent_sandbox/manifest.py`

A sandbox manifest is a YAML file that declaratively defines an entire multi-agent ecosystem: agents, channels, policies, and seed messages. Instead of assembling agents programmatically, write one YAML file and run `harvest sandbox manifest.yaml`.

## Format

```yaml
sandbox:
  name: "my-sandbox"

  policies:
    analyst:
      allowed_tools:
        - get_username
        - send_message
        - read_messages
        - list_channels
      can_send_messages: true
      can_create_channel: false
      can_create_agents: false
      child_policy_mode: none

  agents:
    alice:
      policy: analyst
      model: "anthropic/claude-haiku-4-5-20251001"
      system_prompt: |
        You are Alice, a senior engineer...

    bob:
      policy: analyst
      model: "anthropic/claude-haiku-4-5-20251001"
      system_prompt: |
        You are Bob, a pragmatic developer...

  channels:
    team-chat:
      type: group
      description: "Main team discussion channel."
      members:
        - alice
        - bob
      notification_mode: ambient

    private:
      type: dm
      members:
        - alice
        - bob

  seeds:
    - channel: team-chat
      content: "Let's discuss the new architecture proposal."
      recipients:
        - alice
        - bob
```

## Sections

### `sandbox.name`

Human-readable name for the sandbox instance. Used in debug monitor display and logging.

### `policies`

Optional sandbox-local policy definitions. Fields match `AgentPolicy`:

| Field | Type | Description |
|-------|------|-------------|
| `allowed_tools` | list[str] | Tools the agent can use |
| `can_send_messages` | bool | Whether the agent can send messages |
| `can_create_channel` | bool | Whether the agent can create channels |
| `can_create_agents` | bool | Whether the agent can spawn child agents |
| `child_policy_mode` | str | `none`, `clone`, `predefined`, `define` |
| `allowed_child_policies` | list[str] | For `predefined` mode: allowed policy names |

Policy resolution order: sandbox-local policies win over shared `PolicyRegistry` on name conflicts.

### `agents`

Keyed by `agent_id`. Each entry:

| Field | Type | Description |
|-------|------|-------------|
| `policy` | str | Name of a policy (local or from registry) |
| `model` | str | LiteLLM model identifier |
| `system_prompt` | str | The agent's system prompt (identity footer auto-injected) |

### `channels`

Keyed by `channel_id`. Each entry:

| Field | Type | Applies To | Description |
|-------|------|-----------|-------------|
| `type` | str | all | `dm`, `group`, `processor_gated`, `processor_aggregation` |
| `description` | str | all | Channel description |
| `members` | list[str] | dm, group | Agent IDs |
| `publishers` | list[str] | processor | Agents who can send |
| `subscribers` | list[str] | processor | Agents who receive on release |
| `batch_threshold` | int | aggregation | Messages before batch release |
| `notification_mode` | str | group | `ambient` (default) or `mention` |

### `seeds`

Optional list of messages to inject at startup:

| Field | Type | Description |
|-------|------|-------------|
| `channel` | str | Target channel ID (must be defined in `channels`) |
| `content` | str | Message content |
| `recipients` | list[str] | Optional: specific agents to notify (default: all channel members) |

Seeds are injected as system messages before agents start their hibernation loops.

## Validation

`load_manifest()` validates:

- Every agent references a defined policy (local or shared registry)
- Every channel member/publisher/subscriber references a defined agent
- DM channels have exactly 2 members
- Processor channels have at least 1 publisher and 1 subscriber
- Seed channels and recipients reference defined channels and agents

## Loading

```python
from harvest.agent_sandbox.manifest import load_manifest

manifest = load_manifest("path/to/manifest.yaml")
# manifest.name, manifest.agents, manifest.channels, manifest.policies, manifest.seeds
```

Or create a full sandbox directly:

```python
from harvest.agent_sandbox.basic_sandbox import BasicSandbox

sandbox = BasicSandbox.from_manifest("path/to/manifest.yaml")
await sandbox.start()
```

## Demos

Two demo manifests are included:

- `demos/alice-bob.yaml` — Two agents discussing a tech topic (simple hello-world)
- `demos/conspiracy.yaml` — Three agents, two channels, testing context separation and multi-channel awareness
