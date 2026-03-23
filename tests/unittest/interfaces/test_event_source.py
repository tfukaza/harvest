"""Tests for Service with EVENT_SOURCE role (replaces EventSource ABC tests)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from harvest.interfaces.service import (
    ActionCommand,
    ActionResult,
    DataQuery,
    DataResult,
    Service,
    ServiceRole,
)


# ---------------------------------------------------------------------------
# Concrete stub
# ---------------------------------------------------------------------------


class _ManualEventService(Service):
    """Service with EVENT_SOURCE role that fires when told to."""

    def __init__(self) -> None:
        self._started = False
        self._stopped = False
        self._bus: Any = None

    @property
    def service_id(self) -> str:
        return "manual-source"

    @property
    def roles(self) -> frozenset[ServiceRole]:
        return frozenset({ServiceRole.EVENT_SOURCE})

    def get_capabilities(self) -> list[str]:
        return ["manual_fire"]

    async def fetch(self, query: DataQuery) -> DataResult:
        raise NotImplementedError("EVENT_SOURCE only")

    async def execute(self, command: ActionCommand) -> ActionResult:
        raise NotImplementedError("EVENT_SOURCE only")

    async def start(self, event_bus: Any = None) -> None:
        self._started = True
        self._bus = event_bus

    async def stop(self) -> None:
        self._stopped = True

    def health_check(self) -> dict[str, Any]:
        return {"status": "healthy", "started": self._started}

    def get_tools(self, role: ServiceRole | None = None) -> list:
        # EventSources have no tools (inbox model)
        return []

    def fire(self, event_type: str, payload: dict) -> None:
        """Test helper to manually publish an ExternalEventFired."""
        from harvest.events.base import ExternalEventFired

        if self._bus is not None:
            self._bus.dispatch(
                ExternalEventFired(
                    source_id=self.service_id,
                    event_type=event_type,
                    payload=payload,
                )
            )


# ---------------------------------------------------------------------------
# Contract compliance tests
# ---------------------------------------------------------------------------


def test_service_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        Service()  # type: ignore[abstract]


def test_concrete_subclass_satisfies_contract() -> None:
    svc = _ManualEventService()
    assert svc.service_id == "manual-source"
    assert ServiceRole.EVENT_SOURCE in svc.roles
    assert "manual_fire" in svc.get_capabilities()
    health = svc.health_check()
    assert health["status"] == "healthy"
    assert health["started"] is False


def test_start_stores_event_bus() -> None:
    import asyncio

    svc = _ManualEventService()
    mock_bus = MagicMock()
    asyncio.run(svc.start(mock_bus))
    assert svc._started is True
    assert svc._bus is mock_bus


def test_stop_sets_stopped_flag() -> None:
    import asyncio

    svc = _ManualEventService()
    asyncio.run(svc.stop())
    assert svc._stopped is True


def test_fire_dispatches_external_event_fired() -> None:
    import asyncio
    from harvest.events.base import ExternalEventFired

    svc = _ManualEventService()
    dispatched: list[Any] = []

    class _FakeBus:
        def dispatch(self, event: Any) -> None:
            dispatched.append(event)

    asyncio.run(svc.start(_FakeBus()))
    svc.fire("price_alert", {"symbol": "AAPL", "price": 150.0})

    assert len(dispatched) == 1
    event = dispatched[0]
    assert isinstance(event, ExternalEventFired)
    assert event.source_id == "manual-source"
    assert event.event_type == "price_alert"
    assert event.payload["symbol"] == "AAPL"


def test_event_source_has_no_tools() -> None:
    svc = _ManualEventService()
    assert svc.get_tools() == []
    assert svc.get_tools(role=ServiceRole.EVENT_SOURCE) == []


def test_service_roles_declared() -> None:
    svc = _ManualEventService()
    assert ServiceRole.EVENT_SOURCE in svc.roles
    assert ServiceRole.DATA_SOURCE not in svc.roles
    assert ServiceRole.ACTION not in svc.roles
