# Dynamic System Prompt

**File:** `harvest/agent_sandbox/system_prompt_builder.py`

`SystemPromptBuilder` manages independent sections appended to an agent's base system prompt. Each section is owned by a different part of the system and can be updated or cleared without affecting others.

## Structure

The final system prompt assembled on every LLM call:

```
{base_system_prompt}

{section_1_content}

{section_2_content}
...
```

Sections are separated from each other and from the base prompt by a blank line. Empty sections are omitted entirely.

## API

```python
builder = SystemPromptBuilder()

builder.set("tool_specs", content)       # replace section entirely
builder.append("tool_specs", content)    # append with blank-line separator
builder.clear("tool_specs")             # remove section
builder.has_section("tool_specs")       # True if non-empty
prompt = builder.build(base_prompt)     # assemble final string
```

Sections are stored in insertion order (Python 3.7+ dict). `set()` on an existing key replaces content in-place, preserving order. `clear()` removes the key entirely — if re-added it appears at the end.

## Section Keys in Use

### `"tool_specs"` — Service Tool Documentation

Set by `_inject_tool_spec()` in `BasicSandbox` when an agent calls `discover_tools(tool_name)`. Each activation appends the tool's `to_system_prompt_block()` output.

**Never cleared** — injected specs are permanent for the session. Once an agent learns a tool's full spec, it stays in the prompt.

### `"event_notifications"` — External Event Alerts

Appended by `_add_event_notification()` in `BasicSandbox` when an EVENT_SOURCE service delivers an event to the agent.

**Cleared** by `_clear_event_notifications()` after the agent calls `read_event_notifications()`. This means the notification is only present in the system prompt for the one LLM turn where the agent processes the event.

## Example System Prompt

```
You are a financial research analyst. Use newsapi and perplexity tools
to research market conditions...

---
Your agent ID is `researcher`. Other agents and the system refer to you as @researcher.
...

## Available Tools

### newsapi_get_top_headlines
Fetch the top news headlines.
Service: newsapi [data_source]

Arguments:
  - category (string, optional): News category (default: 'general')
  - page_size (integer, optional): Number of headlines (default: 10)

Returns: JSON with list of article objects

---

## External Event Notifications

bar_update from alpaca: {"symbol": "AAPL", "close": 178.50, ...}
```

## Per-Agent Instances

Every registered agent gets its own `SystemPromptBuilder` instance, stored in `BasicSandbox._prompt_builders[agent_id]`. The sandbox creates a `_system_prompt_fn` closure for each agent:

```python
def _make_system_prompt_fn(agent_id):
    def _fn():
        base = agent.config.system_prompt
        return prompt_builders[agent_id].build(base)
    return _fn

agent._system_prompt_fn = _make_system_prompt_fn(agent_id)
```

`HarvestAgent._build_messages()` calls `self._system_prompt_fn()` on every LLM invocation to get the current system prompt with all active sections.

## Adding New Sections

Any component with access to the sandbox can add a new section:

```python
sandbox._prompt_builders["analyst"].set("memory", "Key facts you've established:\n- ...")
```

New section keys don't conflict with existing ones. The only constraint is that keys must be unique within an agent's builder.
