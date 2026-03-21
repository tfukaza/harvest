"""Tests for the EventBusServer component."""

from __future__ import annotations

import asyncio
import json
from uuid import uuid4

import pytest
import pytest_asyncio

from harvest.events.event_bus import EventBus

pytest_plugins = ["aiohttp.pytest_plugin"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_server():
    """Create an EventBusServer with a fresh EventBus (import deferred)."""
    from harvest.event_server import EventBusServer

    bus = EventBus(name=f"test_server_{uuid4().hex}")
    server = EventBusServer(event_bus=bus, host="127.0.0.1", port=0)
    return server, bus


async def _poll_until(client, event_type: str, client_id: str, *, timeout: float = 2.0):
    """Poll the listen endpoint until at least one event is returned.

    bubus processes events asynchronously so a single sleep is unreliable.
    """
    import time as _time

    deadline = _time.monotonic() + timeout
    while _time.monotonic() < deadline:
        resp = await client.get(
            "/api/events/listen",
            params={"event_type": event_type, "client_id": client_id},
        )
        body = await resp.json()
        if body["count"] > 0:
            return body
        await asyncio.sleep(0.02)
    return body  # return last (empty) result so the assertion can fail with a clear message


# ---------------------------------------------------------------------------
# Unit tests for EventBusServer without HTTP
# ---------------------------------------------------------------------------

class TestEventBusServerUnit:
    """Tests that exercise the server object without starting HTTP."""

    def test_ensure_subscribed_registers_on_bus(self):
        server, bus = _make_server()
        server._ensure_subscribed("price_update")

        assert "price_update" in server._subscribed_event_types
        assert server._bus_handler_registered is True
        # Calling again should be idempotent.
        server._ensure_subscribed("price_update")
        assert "price_update" in server._subscribed_event_types
        assert server._bus_handler_registered is True

    def test_fan_out_buffers_for_registered_client(self):
        server, bus = _make_server()
        # Register a client buffer.
        key = ("client-a", "price_update")
        _ = server._client_buffers[key]

        server._fan_out("price_update", {"symbol": "AAPL"})

        assert len(server._client_buffers[key]) == 1
        record = server._client_buffers[key][0]
        assert record["event_type"] == "price_update"
        assert record["data"]["symbol"] == "AAPL"
        assert "server_timestamp" in record

    def test_fan_out_does_not_buffer_for_wrong_type(self):
        server, _bus = _make_server()
        key = ("client-a", "order_placed")
        _ = server._client_buffers[key]

        server._fan_out("price_update", {"symbol": "AAPL"})

        assert len(server._client_buffers[key]) == 0

    def test_fan_out_pushes_to_sse_queues(self):
        server, _bus = _make_server()
        queue: asyncio.Queue = asyncio.Queue(maxsize=16)
        server._sse_queues["test-stream"] = queue

        server._fan_out("price_update", {"symbol": "AAPL"})

        assert not queue.empty()
        record = queue.get_nowait()
        assert record["event_type"] == "price_update"

    def test_buffer_max_size_evicts_oldest(self):
        from harvest.event_server import _MAX_BUFFER_PER_CLIENT

        server, _bus = _make_server()
        key = ("client-a", "price_update")
        _ = server._client_buffers[key]

        for i in range(_MAX_BUFFER_PER_CLIENT + 50):
            server._fan_out("price_update", {"seq": i})

        buf = server._client_buffers[key]
        assert len(buf) == _MAX_BUFFER_PER_CLIENT
        # Oldest events should have been evicted.
        assert buf[0]["data"]["seq"] == 50


# ---------------------------------------------------------------------------
# Integration tests with aiohttp test client
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def event_bus():
    bus = EventBus(name=f"test_fixture_{uuid4().hex}")
    yield bus
    await bus.stop()


@pytest.fixture
def event_server_app(event_bus):
    from harvest.event_server import EventBusServer

    server = EventBusServer(event_bus=event_bus)
    app = server._build_app()
    # Attach server to the app so tests can access it.
    app["_server"] = server
    return app


class TestPublishEndpoint:
    """Tests for POST /api/events/publish."""

    async def test_publish_returns_ok(self, aiohttp_client, event_server_app):
        client = await aiohttp_client(event_server_app)
        resp = await client.post(
            "/api/events/publish",
            json={"event_type": "price_update", "data": {"symbol": "AAPL"}},
        )
        assert resp.status == 200
        body = await resp.json()
        assert body["status"] == "ok"
        assert body["event_type"] == "price_update"

    async def test_publish_missing_event_type(self, aiohttp_client, event_server_app):
        client = await aiohttp_client(event_server_app)
        resp = await client.post(
            "/api/events/publish",
            json={"data": {"symbol": "AAPL"}},
        )
        assert resp.status == 400

    async def test_publish_missing_data(self, aiohttp_client, event_server_app):
        client = await aiohttp_client(event_server_app)
        resp = await client.post(
            "/api/events/publish",
            json={"event_type": "price_update"},
        )
        assert resp.status == 400

    async def test_publish_invalid_json(self, aiohttp_client, event_server_app):
        client = await aiohttp_client(event_server_app)
        resp = await client.post(
            "/api/events/publish",
            data=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400


class TestListenEndpoint:
    """Tests for GET /api/events/listen."""

    async def test_listen_returns_empty_initially(self, aiohttp_client, event_server_app):
        client = await aiohttp_client(event_server_app)
        resp = await client.get(
            "/api/events/listen",
            params={"event_type": "price_update", "client_id": "c1"},
        )
        assert resp.status == 200
        body = await resp.json()
        assert body["events"] == []
        assert body["count"] == 0

    async def test_listen_returns_published_events(self, aiohttp_client, event_server_app):
        client = await aiohttp_client(event_server_app)

        # Register the client first so the buffer exists.
        await client.get(
            "/api/events/listen",
            params={"event_type": "price_update", "client_id": "c1"},
        )

        # Publish an event.
        await client.post(
            "/api/events/publish",
            json={"event_type": "price_update", "data": {"symbol": "AAPL"}},
        )

        # Poll with retries — bubus processes events asynchronously.
        body = await _poll_until(client, "price_update", "c1")
        assert body["count"] >= 1
        assert body["events"][0]["data"]["symbol"] == "AAPL"

    async def test_listen_clears_buffer_after_poll(self, aiohttp_client, event_server_app):
        client = await aiohttp_client(event_server_app)

        # Register.
        await client.get(
            "/api/events/listen",
            params={"event_type": "price_update", "client_id": "c1"},
        )

        await client.post(
            "/api/events/publish",
            json={"event_type": "price_update", "data": {"symbol": "AAPL"}},
        )

        # First poll drains the buffer.
        await _poll_until(client, "price_update", "c1")

        # Second poll should be empty.
        resp = await client.get(
            "/api/events/listen",
            params={"event_type": "price_update", "client_id": "c1"},
        )
        body = await resp.json()
        assert body["count"] == 0

    async def test_listen_missing_params(self, aiohttp_client, event_server_app):
        client = await aiohttp_client(event_server_app)
        resp = await client.get("/api/events/listen")
        assert resp.status == 400

        resp = await client.get(
            "/api/events/listen",
            params={"event_type": "price_update"},
        )
        assert resp.status == 400


class TestStreamEndpoint:
    """Tests for GET /api/events/stream (SSE)."""

    async def test_stream_missing_event_type(self, aiohttp_client, event_server_app):
        client = await aiohttp_client(event_server_app)
        resp = await client.get("/api/events/stream")
        assert resp.status == 400

    async def test_stream_receives_published_event(self, aiohttp_client, event_server_app):
        client = await aiohttp_client(event_server_app)
        server = event_server_app["_server"]

        # Start the SSE stream in a task.
        resp = await client.get(
            "/api/events/stream",
            params={"event_type": "price_update"},
        )
        assert resp.status == 200
        assert resp.headers["Content-Type"] == "text/event-stream"

        # Publish an event through the server fan_out (simulates bus delivery).
        server._fan_out("price_update", {"symbol": "TSLA"})

        # Read the first SSE line.
        line = await asyncio.wait_for(resp.content.readline(), timeout=2.0)
        decoded = line.decode().strip()
        assert decoded.startswith("data: ")
        payload = json.loads(decoded[len("data: "):])
        assert payload["data"]["symbol"] == "TSLA"


class TestServerLifecycle:
    """Tests for start/stop lifecycle."""

    async def test_start_and_stop(self):
        from harvest.event_server import EventBusServer

        bus = EventBus()
        server = EventBusServer(event_bus=bus, host="127.0.0.1", port=0)
        # Use _build_app to verify it creates a valid app.
        app = server._build_app()
        assert app is not None

    async def test_stop_cleans_up_subscriptions(self):
        server, bus = _make_server()
        server._ensure_subscribed("price_update")
        assert "price_update" in server._subscribed_event_types
        assert server._bus_handler_registered is True

        await server.stop()
        assert len(server._subscribed_event_types) == 0
        assert server._bus_handler_registered is False
