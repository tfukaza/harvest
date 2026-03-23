"""Harvest event bus backed by bubus.

This module provides a thin Harvest-owned wrapper around ``bubus.EventBus``
that standardises bus creation, typed dispatch, and handler registration
for the rest of the codebase.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, TypeVar

import bubus

from harvest.events.base import HarvestEvent

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=HarvestEvent)


class EventBus:
    """Harvest system event bus.

    Wraps a ``bubus.EventBus`` instance and exposes a small opinionated
    surface for dispatching and subscribing to typed ``HarvestEvent``
    subclasses.
    """

    def __init__(self, name: str = "harvest") -> None:
        """Create a new Harvest event bus.

        Args:
            name: Human-readable name for the underlying bubus bus.
        """
        self._bus = bubus.EventBus(name=name)

    # -- dispatch ------------------------------------------------------------

    def dispatch(self, event: HarvestEvent) -> HarvestEvent:
        """Dispatch a typed event onto the bus.

        Args:
            event: A ``HarvestEvent`` subclass instance.

        Returns:
            The dispatched event (can be awaited for completion).
        """
        return self._bus.dispatch(event)

    async def dispatch_async(self, event: HarvestEvent) -> HarvestEvent:
        """Dispatch and wait for all handlers to finish.

        Args:
            event: A ``HarvestEvent`` subclass instance.

        Returns:
            The completed event.
        """
        return await self._bus.dispatch(event)

    def dispatch_sync(self, event: HarvestEvent) -> HarvestEvent:
        """Dispatch an event and process it synchronously.

        Useful when no async event loop is running (e.g. inside broker
        polling threads).  Uses ``bubus.EventBus.step`` which processes
        one event synchronously.

        Args:
            event: A ``HarvestEvent`` subclass instance.

        Returns:
            The dispatched event.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            async def _dispatch_and_step() -> HarvestEvent:
                dispatched_event = self._bus.dispatch(event)
                await self._bus.step(dispatched_event)
                return dispatched_event

            return asyncio.run(_dispatch_and_step())

        raise RuntimeError("dispatch_sync() cannot be used while an event loop is running; use dispatch_async() instead")

    # -- subscribe -----------------------------------------------------------

    def on(
        self,
        event_type: type[T],
        handler: Callable[[T], Any],
    ) -> None:
        """Register a handler for a typed event class.

        Args:
            event_type: The ``HarvestEvent`` subclass to listen for.
            handler: Sync or async callable that receives the event.
        """
        self._bus.on(event_type, handler)

    def off(
        self,
        event_type: type[T],
        handler: Callable[[T], Any],
    ) -> None:
        """Unsubscribe a handler from a typed event class.

        Args:
            event_type: The ``HarvestEvent`` subclass to stop listening for.
            handler: The handler to remove.
        """
        key = event_type.__name__
        handlers = self._bus.handlers.get(key, [])
        try:
            handlers.remove(handler)
        except ValueError:
            pass

    # -- lifecycle -----------------------------------------------------------

    async def stop(self) -> None:
        """Stop the underlying bubus bus and clean up resources."""
        await self._bus.stop(clear=True)

    @property
    def bus(self) -> bubus.EventBus:
        """Access the underlying bubus ``EventBus`` for advanced usage."""
        return self._bus
