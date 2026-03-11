# Architecture

## Overview

Harvest is a trading framework with two architectural paths that currently coexist:

1. The legacy runtime built around `BrokerHub` in `harvest/trader/trader.py`.
2. The newer service-oriented runtime built around `Orchestrator` in `harvest/orchestrator.py`.

New work should generally prefer the orchestrator and service path unless the task is specifically about compatibility with the legacy runtime.

## Core Domains

### Algorithms

- `harvest/algorithm.py` contains the newer `Algorithm` abstraction.
- `harvest/algo.py` contains the legacy `BaseAlgo` abstraction that is still used by the CLI flow.
- Algorithms define trading logic, watchlists, and indicator-driven behavior.

### Brokers

- `harvest/broker/_base.py` defines the broker contract.
- Concrete implementations live under `harvest/broker/`.
- Brokers are responsible for market data access, order placement, account access, and broker-specific capabilities.

### Storage

- `harvest/storage/_base.py` defines local and central storage models.
- `LocalAlgorithmStorage` is algorithm-local.
- `CentralStorage` is shared storage for price history and account-level data.
- Duplication between local and central storage code is intentional and should not be removed casually.

### Services

- `harvest/services/` contains the newer service-oriented architecture.
- Key services include market data, broker access, algorithms, central storage, and service discovery.
- `Orchestrator` wires these services together and manages lifecycle.

### Events

- `harvest/events/event_bus.py` provides the event bus.
- `harvest/events/events.py` defines event payload types.
- The orchestrator path is event-driven and uses these abstractions to decouple components.

## Entry Points

### CLI

- The `harvest` console script points to `harvest.cli:main`.
- `harvest start` scans a directory for `BaseAlgo` subclasses and runs them through the legacy `BrokerHub` flow.
- This means the default CLI behavior is still tied more closely to legacy APIs than to the newer orchestrator path.

### Examples

- `examples/` contains the clearest examples of intended usage.
- `examples/orchestrator_example.py` is the best starting point for the service-oriented direction.

## Current Architectural Reality

The repo is not fully migrated to one runtime model.

- The legacy path is still user-visible via the CLI.
- The orchestrator path expresses the newer direction and should guide platform evolution.
- Some service-oriented pieces are present but not yet fully integrated across the whole project.

When making changes, state explicitly which of these you are affecting:

- Legacy `BrokerHub` runtime
- Service-oriented `Orchestrator` runtime
- Shared broker/storage/event abstractions used by both

## Stable Invariants

- Python 3.12 is the minimum supported version.
- UTC is the internal time standard.
- Domain data should be represented with typed structures rather than loose dictionaries when practical.
- Documentation and code should evolve together when architecture changes.

## Known Tensions

- The CLI still reflects older abstractions.
- The orchestrator path reflects newer architecture but is not the only active path.

Treat these tensions as normal project context, not as reasons to rewrite large portions of the codebase during unrelated tasks.
