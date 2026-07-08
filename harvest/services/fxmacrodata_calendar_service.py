import asyncio
import datetime as dt
import os
from typing import Any

import requests

from .service_interface import Service


class FXMacroDataCalendarService(Service):
    """Read-only FXMacroData release-calendar service."""

    def __init__(self, base_url: str = "https://fxmacrodata.com/api/v1"):
        super().__init__("fxmacrodata_calendar")
        self.base_url = base_url.rstrip("/")
        self._last_event_count = 0

    async def start(self) -> None:
        self.is_running = True
        self._start_time = dt.datetime.utcnow().timestamp()

    async def stop(self) -> None:
        self.is_running = False

    def health_check(self) -> dict[str, Any]:
        return {
            "status": "healthy" if self.is_running else "stopped",
            "last_event_count": self._last_event_count,
        }

    def get_capabilities(self) -> list[str]:
        return [
            "macro_release_calendar",
            "central_bank_events",
            "inflation_and_employment_events",
        ]

    async def fetch_release_calendar(
        self,
        currency: str = "usd",
        *,
        limit: int = 50,
        min_tier: int | None = 2,
    ) -> list[dict[str, Any]]:
        """Fetch upcoming macro events for strategy scheduling."""

        return await asyncio.to_thread(
            self._fetch_release_calendar_sync,
            currency,
            limit,
            min_tier,
        )

    def _fetch_release_calendar_sync(
        self,
        currency: str,
        limit: int,
        min_tier: int | None,
    ) -> list[dict[str, Any]]:
        limit_count = max(1, min(int(limit), 100))
        params: dict[str, str] = {"limit": str(limit_count)}
        api_key = os.getenv("FXMACRODATA_API_KEY")
        if api_key:
            params["api_key"] = api_key

        response = requests.get(
            f"{self.base_url}/calendar/{currency.lower()}",
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        events = response.json().get("data", [])
        if min_tier is not None:
            events = [
                event
                for event in events
                if int(event.get("market_tier") or 99) <= min_tier
            ]
        events = events[:limit_count]
        self._last_event_count = len(events)
        return events
