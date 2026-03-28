"""Event bus HTTP server using aiohttp.

Provides HTTP endpoints for publishing events to, polling events from,
and streaming events via SSE from a Harvest EventBus instance.

This is the boundary layer between external HTTP clients (which speak
in string event types and JSON dicts) and the internal typed
``bubus``-backed event bus.  An ``HttpBridgeEvent`` is used for
payloads that arrive over the wire.  All internal typed events are
serialised to JSON dicts when fanned out to polling / SSE clients.
"""


import asyncio
import json
import logging
import re
import time
from collections import defaultdict, deque
from typing import Any
from uuid import uuid4

from aiohttp import web
from pydantic import Field

from harvest.events.event_bus import EventBus
from harvest.events.base import HarvestEvent

logger = logging.getLogger(__name__)

# Maximum number of events buffered per client for polling.
_MAX_BUFFER_PER_CLIENT = 1000


class HttpBridgeEvent(HarvestEvent):
    """Lightweight event used to bridge HTTP payloads onto the typed bus."""

    http_event_type: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class EventBusServer:
    """HTTP server that bridges external clients to an in-process EventBus.

    The server exposes three endpoints:

    * ``POST /api/events/publish`` -- publish an event to the bus.
    * ``GET  /api/events/listen``  -- poll queued events for a client.
    * ``GET  /api/events/stream``  -- SSE stream of real-time events.
    """

    def __init__(self, event_bus: EventBus | None = None, host: str = "127.0.0.1", port: int = 8000) -> None:
        self._event_bus = event_bus or EventBus()
        self._host = host
        self._port = port

        # Per-client event buffers keyed by (client_id, event_type).
        self._client_buffers: dict[tuple[str, str], deque[dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=_MAX_BUFFER_PER_CLIENT)
        )

        # Active SSE queues keyed by subscription id.
        self._sse_queues: dict[str, asyncio.Queue[dict[str, Any] | None]] = {}

        # Event types we have registered handlers for.
        self._subscribed_event_types: set[str] = set()

        # Whether the bus fan-out handler has been registered.
        self._bus_handler_registered: bool = False

        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None

    # -- properties ----------------------------------------------------------

    @property
    def event_bus(self) -> EventBus:
        """Return the underlying Harvest EventBus."""
        return self._event_bus

    @property
    def app(self) -> web.Application | None:
        """Return the aiohttp Application if built."""
        return self._app

    # -- lifecycle -----------------------------------------------------------

    def _build_app(self) -> web.Application:
        app = web.Application()
        app.router.add_post("/api/events/publish", self._handle_publish)
        app.router.add_get("/api/events/listen", self._handle_listen)
        app.router.add_get("/api/events/stream", self._handle_stream)
        return app

    async def start(self) -> None:
        """Start the HTTP server."""
        self._ensure_bus_handler_registered()
        self._app = self._build_app()
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self._host, self._port)
        await self._site.start()
        logger.info("EventBusServer listening on %s:%s", self._host, self._port)

    async def stop(self) -> None:
        """Stop the HTTP server and clean up."""
        # Signal all SSE clients to disconnect.
        for q in self._sse_queues.values():
            try:
                q.put_nowait(None)
            except asyncio.QueueFull:
                pass

        self._subscribed_event_types.clear()
        self._bus_handler_registered = False

        if self._runner:
            await self._runner.cleanup()
            self._runner = None
        self._site = None
        self._app = None
        logger.info("EventBusServer stopped")

    # -- internal subscription management ------------------------------------

    def _ensure_subscribed(self, event_type: str) -> None:
        """Ensure we capture events that should be fanned out to HTTP clients.

        This records the requested event type so polling and SSE clients
        can declare their interest. The server registers one internal
        bus handler that receives every ``HarvestEvent`` and fans it out.
        """
        if event_type not in self._subscribed_event_types:
            self._subscribed_event_types.add(event_type)

        self._ensure_bus_handler_registered()

    def _ensure_bus_handler_registered(self) -> None:
        """Register a single wildcard bus handler for all events."""
        if self._bus_handler_registered:
            return

        def _on_event(event: Any) -> None:
            if isinstance(event, HttpBridgeEvent):
                self._fan_out(event_type=event.http_event_type, data=event.data)
                return

            if isinstance(event, HarvestEvent):
                event_type = self._to_wire_event_type(event)
                payload = self._event_payload(event)
                self._fan_out(event_type=event_type, data=payload)

        # Use "*" wildcard — bubus does not match parent-class handlers for
        # child events, so registering on HarvestEvent would miss subclasses.
        self._event_bus.bus.on("*", _on_event)
        self._bus_handler_registered = True

    def _to_wire_event_type(self, event: HarvestEvent) -> str:
        """Convert typed event classes to wire-friendly event_type strings."""
        name = event.__class__.__name__
        override_map = {
            "PriceUpdated": "price_update",
            "AllPricesUpdated": "all_prices_update",
            "PeriodicTick": "periodic_event",
            "OrderPlaced": "order_placed",
            "OrderFilled": "order_filled",
            "OrderCancelled": "order_cancelled",
            "AccountUpdated": "account_update",
            "PositionUpdated": "position_update",
            "AlgorithmStarted": "algorithm_started",
            "AlgorithmStopped": "algorithm_stopped",
            "RuntimeLifecycleChanged": "runtime_lifecycle",
            "AgentLifecycleChanged": "agent_lifecycle",
            "ToolCallRequested": "tool_call",
            "ToolCallCompleted": "tool_result",
            "ResourceUpdated": "resource_update",
            "ServiceHealthChanged": "service_health_changed",
            "ErrorOccurred": "error",
            "LogEmitted": "log",
        }
        if name in override_map:
            return override_map[name]

        snake = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
        if snake.endswith("_event"):
            snake = snake[: -len("_event")]
        return snake

    def _event_payload(self, event: HarvestEvent) -> dict[str, Any]:
        """Serialize a typed event to a JSON-compatible payload."""
        return event.model_dump(mode="json")

    def _fan_out(self, event_type: str, data: dict[str, Any]) -> None:
        """Distribute an event to all polling buffers and SSE queues."""
        record: dict[str, Any] = {
            "event_type": event_type,
            "data": data,
            "server_timestamp": time.time(),
        }

        # Polling buffers -- push to every client that registered for this type.
        for (cid, et), buf in list(self._client_buffers.items()):
            if et == event_type:
                buf.append(record)

        # SSE queues -- best-effort push.
        for q in list(self._sse_queues.values()):
            try:
                q.put_nowait(record)
            except asyncio.QueueFull:
                pass

    # -- HTTP handlers -------------------------------------------------------

    async def _handle_publish(self, request: web.Request) -> web.Response:
        """``POST /api/events/publish`` -- publish an event to the bus."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON body"}, status=400)

        event_type = body.get("event_type")
        data = body.get("data")

        if not event_type or not isinstance(event_type, str):
            return web.json_response({"error": "missing or invalid event_type"}, status=400)
        if data is None or not isinstance(data, dict):
            return web.json_response({"error": "missing or invalid data dict"}, status=400)

        self._ensure_subscribed(event_type)

        event = HttpBridgeEvent(
            http_event_type=event_type,
            data=data,
            source="http_bridge",
        )
        await self._event_bus.dispatch_async(event)

        return web.json_response({"status": "ok", "event_type": event_type})

    async def _handle_listen(self, request: web.Request) -> web.Response:
        """``GET /api/events/listen`` -- poll queued events for a client."""
        event_type = request.query.get("event_type")
        client_id = request.query.get("client_id")

        if not event_type:
            return web.json_response({"error": "missing event_type query param"}, status=400)
        if not client_id:
            return web.json_response({"error": "missing client_id query param"}, status=400)

        self._ensure_subscribed(event_type)

        key = (client_id, event_type)
        if key not in self._client_buffers:
            self._client_buffers[key]  # triggers defaultdict creation

        buf = self._client_buffers[key]
        events = list(buf)
        buf.clear()

        return web.json_response({"events": events, "count": len(events)})

    async def _handle_stream(self, request: web.Request) -> web.StreamResponse:
        """``GET /api/events/stream`` -- SSE stream of real-time events."""
        event_type = request.query.get("event_type")
        if not event_type:
            return web.json_response({"error": "missing event_type query param"}, status=400)

        self._ensure_subscribed(event_type)

        response = web.StreamResponse(
            status=200,
            reason="OK",
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
        await response.prepare(request)

        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=256)
        stream_id = str(uuid4())
        self._sse_queues[stream_id] = queue

        try:
            while True:
                record = await queue.get()
                if record is None:
                    break
                if record.get("event_type") != event_type:
                    continue
                payload = json.dumps(record)
                try:
                    await response.write(f"data: {payload}\n\n".encode())
                except (ConnectionResetError, ConnectionAbortedError):
                    break
        finally:
            self._sse_queues.pop(stream_id, None)

        return response


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Convenience entry point to run the server from the CLI."""
    event_bus = EventBus()
    server = EventBusServer(event_bus=event_bus, host=host, port=port)

    async def _run() -> None:
        await server.start()
        print(f"Event bus server running on http://{host}:{port}")
        print("Press Ctrl+C to stop.")
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            pass
        finally:
            await server.stop()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass
