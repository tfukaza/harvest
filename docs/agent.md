# Agent

## Purpose

The `Agent` document defines the behavior of the agent itself, separate from the `Agent Runner` that hosts it.

An agent is the decision-making unit. The runner is the sandbox and integration layer around it.

## Tech Stack

Harvest agents are intended to use `LiteLLM`.

That choice is deliberate. The goal is not to adopt a framework with a large amount of built-in agent behavior. The goal is to keep the core model layer lightweight so Harvest can control the surrounding behavior itself.

This matters because the platform is expected to support custom mechanisms such as:

- agent-to-agent communication
- runtime-created group chats
- sandbox-local messaging policies
- message processors and staged coordination
- custom persistence for reasoning, tool results, and session state

## What LiteLLM Provides

For now, `LiteLLM` is expected to provide the minimal model-facing pieces that are already useful:

- model invocation
- tool calling support
- a basic agent loop

These are useful primitives, but they are not the full Harvest agent system.

## Execution Ownership

The execution loop is owned by the `Agent`, not the `Agent Runner`.

That is an intentional design choice. The agent is the individual unit of thinking. The runner hosts the agent, supplies the sandbox around it, and exposes runtime capabilities, but it does not own the agent's core thinking loop.

## What Harvest Must Build Around It

Everything outside the minimal model loop should be treated as Harvest-owned behavior.

That includes:

- integration with the `Agent Runner`
- messaging between agents
- runtime-created group chats
- message processors and release policies
- local and central persistence decisions
- sandbox lifecycle and topology changes
- tool exposure and tool-result handling beyond the basic model interface

In other words, `LiteLLM` provides the narrow agent core. Harvest defines the actual agent platform around that core.

## Behavioral Boundary

The `Agent` should stay focused on agent-local behavior:

- consume agent-facing input
- reason over that input
- own its own execution loop
- decide what to do next
- call tools when needed
- expose reasoning history

The `Agent` should not own framework wiring such as:

- orchestrator event bus integration
- sandbox topology management
- message routing policy
- resource discovery
- persistence architecture

Those responsibilities belong to the `Agent Runner`.

## Design Direction

The intent is to keep the agent layer simple and controllable.

Harvest should avoid pushing too much policy into the model library itself. The more coordination behavior that lives in Harvest rather than inside a batteries-included agent framework, the easier it is to support custom agent workflows later.
