"""Tests for the event_client helpers."""


import json
from unittest.mock import MagicMock, patch

import pytest

from harvest.http.event_client import poll_events, publish_event, stream_events


# ---------------------------------------------------------------------------
# publish_event
# ---------------------------------------------------------------------------


class TestPublishEvent:
    def test_publish_event_sends_post(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "ok", "event_type": "price_update"}
        mock_resp.raise_for_status = MagicMock()

        with patch("harvest.http.event_client.requests.post", return_value=mock_resp) as mock_post:
            result = publish_event("http://localhost:8000", "price_update", {"symbol": "AAPL"})

        mock_post.assert_called_once_with(
            "http://localhost:8000/api/events/publish",
            json={"event_type": "price_update", "data": {"symbol": "AAPL"}},
            timeout=10,
        )
        assert result["status"] == "ok"

    def test_publish_event_strips_trailing_slash(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "ok"}
        mock_resp.raise_for_status = MagicMock()

        with patch("harvest.http.event_client.requests.post", return_value=mock_resp) as mock_post:
            publish_event("http://localhost:8000/", "test", {})

        url_used = mock_post.call_args[0][0]
        assert "//" not in url_used.replace("http://", "")


# ---------------------------------------------------------------------------
# poll_events
# ---------------------------------------------------------------------------


class TestPollEvents:
    def test_poll_events_sends_get(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"events": [{"event_type": "price_update", "data": {}}], "count": 1}
        mock_resp.raise_for_status = MagicMock()

        with patch("harvest.http.event_client.requests.get", return_value=mock_resp) as mock_get:
            events = poll_events("http://localhost:8000", "price_update", "client-a")

        mock_get.assert_called_once_with(
            "http://localhost:8000/api/events/listen",
            params={"event_type": "price_update", "client_id": "client-a"},
            timeout=10,
        )
        assert len(events) == 1

    def test_poll_events_returns_empty_list_on_no_events(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"events": [], "count": 0}
        mock_resp.raise_for_status = MagicMock()

        with patch("harvest.http.event_client.requests.get", return_value=mock_resp):
            events = poll_events("http://localhost:8000", "price_update", "client-a")

        assert events == []


# ---------------------------------------------------------------------------
# stream_events
# ---------------------------------------------------------------------------


class TestStreamEvents:
    def test_stream_events_yields_parsed_events(self):
        record = {"event_type": "price_update", "data": {"symbol": "AAPL"}}
        lines = [
            f"data: {json.dumps(record)}",
            "",  # blank line separating SSE frames
            f"data: {json.dumps(record)}",
        ]

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.iter_lines.return_value = iter(lines)

        with patch("harvest.http.event_client.requests.get", return_value=mock_resp):
            results = list(stream_events("http://localhost:8000", "price_update"))

        assert len(results) == 2
        assert results[0]["data"]["symbol"] == "AAPL"

    def test_stream_events_skips_non_data_lines(self):
        lines = [
            ": keepalive",
            "data: {\"event_type\":\"x\",\"data\":{}}",
        ]

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.iter_lines.return_value = iter(lines)

        with patch("harvest.http.event_client.requests.get", return_value=mock_resp):
            results = list(stream_events("http://localhost:8000", "x"))

        assert len(results) == 1

    def test_stream_events_skips_invalid_json(self):
        lines = [
            "data: not-json",
            "data: {\"event_type\":\"x\",\"data\":{}}",
        ]

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.iter_lines.return_value = iter(lines)

        with patch("harvest.http.event_client.requests.get", return_value=mock_resp):
            results = list(stream_events("http://localhost:8000", "x"))

        assert len(results) == 1
