"""Event bus helpers for blocking request/response patterns.

Agent threads use these to communicate with server-side components (ChatRouter,
BasicSandbox, SandboxServiceRouter) through the sandbox event bus.

Both helpers park the calling thread. The bus itself dispatches events
synchronously on the calling thread -- handler execution is immediate.

Also provides ``SyncEventBus``, a lightweight synchronous event bus for
sandbox-internal use. Unlike the bubus-backed ``EventBus``, this does not
require an async event loop and is safe to use from agent threads.
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from typing import Any, Callable

from harvest.events.base import HarvestEvent

logger = logging.getLogger(__name__)


class SyncEventBus:
    """Lightweight synchronous event bus for sandbox-internal communication.

    Dispatches events synchronously on the calling thread. Handlers are
    invoked in registration order. Thread-safe.
    """

    def __init__(self, name: str = "") -> None:
        self._name = name
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._lock = threading.Lock()

    def on(self, event_type: type, handler: Callable) -> None:
        """Register a handler for an event type."""
        key = event_type.__name__
        with self._lock:
            self._handlers[key].append(handler)

    def off(self, event_type: type, handler: Callable) -> None:
        """Unsubscribe a handler."""
        key = event_type.__name__
        with self._lock:
            handlers = self._handlers.get(key, [])
            try:
                handlers.remove(handler)
            except ValueError:
                pass

    def dispatch(self, event: Any) -> None:
        """Dispatch an event synchronously. All handlers run on the calling thread."""
        key = type(event).__name__
        with self._lock:
            handlers = list(self._handlers.get(key, []))
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "Handler %s failed for event %s on bus %s",
                    handler, key, self._name,
                )


def wait_for_event(
    bus: SyncEventBus,
    event_types: tuple[type[HarvestEvent], ...],
    filter_fn: Callable[[HarvestEvent], bool],
    timeout: float,
) -> HarvestEvent | None:
    """Subscribe, block until a matching event arrives, unsubscribe.

    Use this when the request has already been dispatched or when waiting
    for an unsolicited event (e.g. StakeGranted arriving later after a
    StakeQueued, or a child's AgentStopped).

    Args:
        bus: The event bus to listen on.
        event_types: Event classes to subscribe to.
        filter_fn: Predicate that must return True for the desired event.
        timeout: Maximum seconds to wait.

    Returns:
        The first matching event, or None on timeout.
    """
    gate = threading.Event()
    captured: list[HarvestEvent] = []

    def _handler(event: HarvestEvent) -> None:
        if filter_fn(event):
            captured.append(event)
            gate.set()

    # Subscribe
    for t in event_types:
        bus.on(t, _handler)

    # Block
    gate.wait(timeout=timeout)

    # Cleanup
    for t in event_types:
        bus.off(t, _handler)

    return captured[0] if captured else None


def dispatch_and_wait(
    bus: SyncEventBus,
    request: HarvestEvent,
    response_types: tuple[type[HarvestEvent], ...],
    filter_fn: Callable[[HarvestEvent], bool],
    timeout: float,
) -> HarvestEvent | None:
    """Subscribe first, dispatch request, block until matching response.

    The subscribe-before-dispatch ordering prevents the race where a
    response arrives before the subscription is registered.

    Args:
        bus: The event bus.
        request: The request event to dispatch.
        response_types: Event classes to listen for as responses.
        filter_fn: Predicate for matching the desired response.
        timeout: Maximum seconds to wait.

    Returns:
        The first matching response event, or None on timeout.
    """
    gate = threading.Event()
    captured: list[HarvestEvent] = []

    def _handler(event: HarvestEvent) -> None:
        if filter_fn(event):
            captured.append(event)
            gate.set()

    # 1. Subscribe FIRST
    for t in response_types:
        bus.on(t, _handler)

    # 2. THEN dispatch the request
    bus.dispatch(request)

    # 3. Wait for response
    gate.wait(timeout=timeout)

    # 4. Cleanup
    for t in response_types:
        bus.off(t, _handler)

    return captured[0] if captured else None
