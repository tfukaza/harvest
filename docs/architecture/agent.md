# HarvestAgent

**File:** `harvest/harvest_agent.py`

The `HarvestAgent` is the LLM-backed agent implementation. It wraps LiteLLM for model invocation and tool calling, manages conversation history, and integrates with the ChatRouter for inter-agent communication.

## Design Philosophy

The agent owns its thinking loop. The sandbox provides the environment. This separation is deliberate — the agent decides what to do, the sandbox controls what it's allowed to do.

LiteLLM is used as the model layer specifically because it's lightweight. Harvest controls the surrounding behavior (messaging, policies, persistence, coordination) rather than delegating to a batteries-included agent framework.

## Configuration

```python
@dataclass
class HarvestAgentConfig:
    model: str                          # LiteLLM model identifier
    system_prompt: str                  # Agent's system prompt
    context_limit: int = 128000         # Max context window tokens
    compaction_threshold: float = 0.75  # Trigger compaction at this fraction
    api_base: str | None = None         # Custom API base URL (for local/self-hosted LLMs)
    api_key_env: str | None = None      # Env var name to read the API key from
```

Default model: `anthropic/claude-haiku-4-5-20251001`

### Multi-LLM Support

`api_base` and `api_key_env` enable routing agents to different LLM providers:

```python
# OpenAI-compatible local model
HarvestAgentConfig(
    model="openai/my-model",
    api_base="http://localhost:11434/v1",
    api_key_env="MY_LOCAL_API_KEY",
)
```

Both fields are also supported in YAML manifests:

```yaml
agents:
  local-agent:
    type: llm_agent
    config:
      model: "openai/llama3"
      api_base: "http://localhost:11434/v1"
      api_key_env: "OLLAMA_API_KEY"
      system_prompt: "You are a helpful assistant."
```

## Tool System

Agents interact with the sandbox through tools registered at startup:

| Tool | Description |
|------|-------------|
| `send_message(channel_id, content)` | Send a message to a channel |
| `read_messages(channel_id?)` | Read inbox overview or specific channel |
| `list_channels()` | List channels the agent belongs to |
| `get_username()` | Get the agent's own ID |
| `create_channel(...)` | Create a new channel (policy-gated) |
| `create_agent(...)` | Spawn a child agent (policy-gated) |

Tools are registered via `_wire_chat_router(router, policy)`, which filters the tool list based on the agent's `AgentPolicy.allowed_tools`.

## step() Method

`step(message)` is the core execution method:

1. Adds the message to conversation history
2. Calls the LLM via LiteLLM with the current conversation + tools
3. If the LLM returns tool calls, executes them and loops
4. Returns the assistant's text response

The method handles the case where the LLM responds with only tool calls and no text (common when agents communicate solely through `send_message`). In this case, it returns `""` rather than raising an error.

## Conversation Compaction

When conversation history approaches the context limit (controlled by `compaction_threshold`), the agent compacts older messages into a summary. This allows long-running agents to maintain context without hitting token limits.

## Identity

Each agent has an `agent_id` set by the sandbox at registration time. The sandbox also injects an identity footer into the system prompt (see [sandbox.md](sandbox.md)) so the agent knows:

- Its own name
- How other agents refer to it (`@agent-id`)
- Not to respond to its own messages
- That `@agent-id` mentions are addressed to it

## Behavioral Boundary

The agent should own:
- Consuming agent-facing input and reasoning over it
- Its own execution loop
- Tool calling decisions
- Reasoning history

The agent should NOT own:
- Message routing policy (ChatRouter)
- Sandbox topology management
- Resource discovery
- Persistence architecture
- Policy enforcement

Those responsibilities belong to the sandbox.

## Tool Call Loop Cap

`step()` limits consecutive tool-call iterations via `config.tool_call_loop_cap` (default 25). If the LLM keeps issuing tool calls without producing a final text response, the loop terminates after this many iterations. This prevents runaway loops caused by models that endlessly call tools without converging on an answer.

## Result Buffer Integration

Large tool results are intercepted by `ResultBuffer` before being injected into the conversation context. The buffer applies a three-tier model: small results pass through unchanged, medium results are paginated (page 0 + navigation metadata), and large results are chunked with per-chunk summaries. The agent can call `browse_results(tool_call_id, mode, ...)` to navigate paginated or summarized data by page index, regex grep, or offset/count slice. See [result-buffer.md](result-buffer.md) for the full design.

## Cognitive Tools

Three optional tool families for agent-internal reasoning, enabled per-agent via `AgentPolicy.cognitive_tools`:

- **think** — private scratchpad for structured reasoning that does not appear in chat
- **memory** — persistent key-value store (`agent._memories`) for facts the agent wants to retain across turns
- **todo** — task list (`agent._todos`) the agent can add to, check off, and review

`_wire_cognitive_tools(enabled)` registers the corresponding tools from `harvest/cognitive_tools.py`. State lives directly on the agent instance and survives compaction.

## Base Class Stubs

The `Agent` base class provides stub attributes (`_tools`, `_tool_map`, `_chat_router`, `_result_buffer`, etc.) with safe defaults (empty lists, empty dicts, `None`). This ensures `BasicSandbox` wiring methods (`_wire_chat_router`, `_wire_service_router`, `_wire_cognitive_tools`) work uniformly without checking whether each attribute has been initialized.
