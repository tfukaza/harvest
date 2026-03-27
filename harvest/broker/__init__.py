"""Legacy broker implementations for the Orchestrator runtime path.

This package contains broker adapters (Alpaca, Robinhood, Webull, etc.)
used by :class:`~harvest.orchestrator.Orchestrator` — the original
non-agent trading system.

**New agent-based code should use** ``harvest.services.*Service`` **classes
instead**, which implement the unified :class:`~harvest.interfaces.service.Service`
interface with role-based policy enforcement.

See ``docs/architecture/services.md`` for the modern service architecture.
"""
