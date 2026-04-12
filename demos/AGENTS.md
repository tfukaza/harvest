# Demo YAML Authoring Guide

## Running a Demo

First, install the package in editable mode (one-time setup):

```bash
uv pip install -e .
```

Source your `.env` file before running — the CLI does not auto-load dotenv files:

```bash
set -a && source .env && set +a
```

Start a sandbox from a YAML manifest:

```bash
harvest sandbox demos/researcher.yaml
```

The debug monitor starts at `http://localhost:8100` by default. Use `--port` to
change it, or `--no-monitor` to disable it.

To send a message to a running sandbox:

```bash
harvest admin research "Your message here"
```

The admin command connects via WebSocket to `ws://localhost:8100/ws`, auto-detects
the sandbox, and injects the message into the specified channel.

---

## Tool References in System Prompts

**Do not hardcode tool names or descriptions in agent system prompts.**

Tools are automatically registered and made available to agents based on their
policy configuration (`allowed_services`, `cognitive_tools`). The LLM receives
tool specs via the OpenAI function-calling format, so it already knows what
tools are available and how to call them.

If an agent needs to discover detailed tool specs at runtime, it can call
`discover_tools` — this is auto-registered for all agents.

System prompts should describe **workflow and strategy** (e.g., "search the web,
then extract promising pages, save findings to memory") rather than listing
specific tool names. This keeps prompts portable across service configurations
and avoids drift when tools are added or renamed.
