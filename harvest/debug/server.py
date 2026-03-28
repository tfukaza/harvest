"""Flask-based debug monitor server with WebSocket support."""


import dataclasses
import json
import logging
import queue
import threading
import time
from typing import Any

from harvest.debug.registry import SandboxRegistry

logger = logging.getLogger(__name__)


class DebugMonitorServer:
    """Flask server that streams sandbox state over WebSocket.

    Uses flask-sock for WebSocket support. Serves the SvelteKit build
    as static files when static_dir is provided.
    """

    def __init__(
        self,
        registry: SandboxRegistry,
        host: str = "127.0.0.1",
        port: int = 8100,
        batch_interval: float = 1.0,
        resync_interval: float = 5.0,
        static_dir: str | None = None,
    ) -> None:
        self._registry = registry
        self._host = host
        self._port = port
        self._batch_interval = batch_interval
        self._resync_interval = resync_interval
        self._static_dir = static_dir
        self._thread: threading.Thread | None = None
        self._app = self._create_app()

    def _create_app(self) -> Any:
        from flask import Flask, jsonify, send_from_directory
        from flask_sock import Sock

        if self._static_dir:
            app = Flask(__name__, static_folder=self._static_dir, static_url_path="")
        else:
            app = Flask(__name__)

        sock = Sock(app)

        registry = self._registry
        batch_interval = self._batch_interval
        resync_interval = self._resync_interval

        @app.route("/api/snapshot")
        def api_snapshot() -> Any:
            snapshots = registry.snapshot_all()
            data = {
                "type": "snapshot",
                "timestamp": _now_iso(),
                "sandboxes": [dataclasses.asdict(s) for s in snapshots],
            }
            return jsonify(data)

        if self._static_dir:
            @app.route("/")
            def index() -> Any:
                return send_from_directory(self._static_dir, "index.html")

        @sock.route("/ws")
        def ws_handler(ws: Any) -> None:
            # Send initial full snapshot
            snapshot_msg = _build_snapshot_message(registry)
            try:
                ws.send(json.dumps(snapshot_msg))
            except Exception:
                return

            last_resync = time.monotonic()
            # Track cursor per sandbox for delta messages
            cursors: dict[str, int] = {}
            for sid in registry.list_sandbox_ids():
                cursors[sid] = len(registry.get_message_buffer(sid))

            # Per-connection outbound queue for typing, status, and admin ack events
            typing_queue: queue.Queue[dict[str, Any]] = queue.Queue()
            closed = threading.Event()

            def _on_typing(sandbox_id: str, channel_id: str, agent_id: str, is_typing: bool) -> None:
                typing_queue.put({
                    "type": "typing",
                    "sandbox_id": sandbox_id,
                    "channel_id": channel_id,
                    "agent_id": agent_id,
                    "active": is_typing,
                })

            def _on_status(sandbox_id: str, agent_id: str, status: str) -> None:
                typing_queue.put({
                    "type": "agent_status",
                    "sandbox_id": sandbox_id,
                    "agent_id": agent_id,
                    "status": status,
                })

            registry.on_typing(_on_typing)
            registry.on_status_changed(_on_status)

            def _recv_loop() -> None:
                """Background thread that reads client messages."""
                while not closed.is_set():
                    try:
                        raw = ws.receive(timeout=1.0)
                    except Exception:
                        closed.set()
                        return
                    if raw is None:
                        continue
                    try:
                        msg = json.loads(raw)
                    except (json.JSONDecodeError, TypeError):
                        continue
                    msg_type = msg.get("type")
                    if msg_type == "admin_send":
                        import uuid
                        sandbox_id = msg.get("sandbox_id", "")
                        channel_id = msg.get("channel_id", "")
                        content = msg.get("content", "")
                        logger.info(
                            "[admin-ws] Received admin_send: sandbox=%r channel=%r content=%.60r",
                            sandbox_id, channel_id, content,
                        )
                        if sandbox_id and channel_id and content:
                            message_id = uuid.uuid4().hex
                            try:
                                sandbox = registry.get_sandbox(sandbox_id)
                                result = sandbox.chat_router.send_message(
                                    sender_id="admin",
                                    channel_id=channel_id,
                                    content=content,
                                    message_id=message_id,
                                )
                            except KeyError:
                                result = {"status": "error", "error": f"Unknown sandbox: {sandbox_id}"}
                            if result.get("status") == "error":
                                typing_queue.put({
                                    "type": "admin_blocked",
                                    "reason": result.get("error", "send failed"),
                                })
                            else:
                                typing_queue.put({
                                    "type": "admin_queued",
                                    "sandbox_id": sandbox_id,
                                    "channel_id": channel_id,
                                    "message_id": message_id,
                                })
                        else:
                            typing_queue.put({
                                "type": "admin_blocked",
                                "reason": "missing sandbox_id, channel_id, or content",
                            })

            recv_thread = threading.Thread(target=_recv_loop, daemon=True)
            recv_thread.start()

            while not closed.is_set():
                time.sleep(batch_interval)

                # Drain typing events first (immediate push)
                while not typing_queue.empty():
                    try:
                        evt = typing_queue.get_nowait()
                        ws.send(json.dumps(evt))
                    except queue.Empty:
                        break
                    except Exception:
                        closed.set()
                        return

                now = time.monotonic()
                if now - last_resync >= resync_interval:
                    # Periodic full re-sync
                    msg = _build_snapshot_message(registry)
                    try:
                        ws.send(json.dumps(msg))
                    except Exception:
                        break
                    last_resync = now
                    # Reset cursors
                    for sid in registry.list_sandbox_ids():
                        cursors[sid] = len(registry.get_message_buffer(sid))
                    continue

                # Collect deltas
                new_messages: list[dict[str, Any]] = []
                for sid in registry.list_sandbox_ids():
                    buf = registry.get_message_buffer(sid)
                    cursor = cursors.get(sid, 0)
                    buf_list = list(buf)
                    if len(buf_list) > cursor:
                        for mi in buf_list[cursor:]:
                            entry: dict[str, Any] = {
                                "sandbox_id": sid,
                                "message_id": mi.message_id,
                                "channel_id": mi.channel_id,
                                "sender_id": mi.sender_id,
                                "content": mi.content,
                                "timestamp": mi.timestamp,
                            }
                            if mi.reply_to:
                                entry["reply_to"] = mi.reply_to
                            new_messages.append(entry)
                        cursors[sid] = len(buf_list)

                if new_messages:
                    delta = {
                        "type": "delta",
                        "timestamp": _now_iso(),
                        "messages": new_messages,
                    }
                    try:
                        ws.send(json.dumps(delta))
                    except Exception:
                        break

            closed.set()

        return app

    def start(self) -> None:
        """Run Flask in a daemon thread (non-blocking)."""
        self._thread = threading.Thread(
            target=self._app.run,
            kwargs={"host": self._host, "port": self._port, "threaded": True},
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the server (best-effort — Flask doesn't have graceful shutdown)."""
        # Daemon thread will die when the process exits
        self._thread = None

    @property
    def app(self) -> Any:
        """Access the Flask app (for testing)."""
        return self._app


def _now_iso() -> str:
    import datetime as dt
    return dt.datetime.now(dt.UTC).isoformat()


def _build_snapshot_message(registry: SandboxRegistry) -> dict[str, Any]:
    snapshots = registry.snapshot_all()
    return {
        "type": "snapshot",
        "timestamp": _now_iso(),
        "sandboxes": [dataclasses.asdict(s) for s in snapshots],
    }
