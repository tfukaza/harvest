"""NewsAPIService — DATA_SOURCE service wrapping NewsAPI.org.

Phase 16 concrete service implementation.
Requires: ``requests`` (standard HTTP client, no SDK dependency).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from harvest.interfaces.service import (
    ActionCommand,
    ActionResult,
    DataQuery,
    DataResult,
    Service,
    ServiceRole,
)
from harvest.interfaces.tool_definition import InterfaceTool, ToolArgument
from harvest.result_buffer import ServiceResult

_BASE_URL = "https://newsapi.org/v2"


class NewsAPIService(Service):
    """DATA_SOURCE service backed by NewsAPI.org.

    Exposes two tools:
    - ``newsapi_get_top_headlines`` — current top headlines
    - ``newsapi_search_articles`` — full-text article search

    Args:
        api_key: NewsAPI.org API key.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._session: requests.Session | None = None

    # ------------------------------------------------------------------
    # Service identity
    # ------------------------------------------------------------------

    @property
    def service_id(self) -> str:
        return "newsapi"

    @property
    def roles(self) -> frozenset[ServiceRole]:
        return frozenset({ServiceRole.DATA_SOURCE})

    def get_capabilities(self) -> list[str]:
        return ["top_headlines", "article_search"]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self, event_bus: Any = None) -> None:
        self._session = requests.Session()
        self._session.headers["X-Api-Key"] = self._api_key
        # Validate key with a lightweight request
        resp = self._session.get(
            f"{_BASE_URL}/top-headlines",
            params={"country": "us", "pageSize": 1},
            timeout=10,
        )
        if resp.status_code == 401:
            raise RuntimeError("NewsAPI authentication failed — check api key")
        if resp.status_code not in (200, 426):
            raise RuntimeError(f"NewsAPI startup check failed: {resp.status_code}")

    async def stop(self) -> None:
        if self._session:
            self._session.close()
            self._session = None

    def health_check(self) -> dict[str, Any]:
        return {"status": "healthy" if self._session else "stopped"}

    # ------------------------------------------------------------------
    # DATA_SOURCE: fetch
    # ------------------------------------------------------------------

    async def fetch(self, query: DataQuery) -> DataResult:
        return await self._dispatch_fetch(query, {
            "top_headlines": self._get_top_headlines,
            "search_articles": self._search_articles,
        })

    # ------------------------------------------------------------------
    # ACTION: not applicable
    # ------------------------------------------------------------------

    async def execute(self, command: ActionCommand) -> ActionResult:
        raise NotImplementedError("NewsAPIService has no ACTION role")

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    def get_tools(self, role: ServiceRole | None = None) -> list[InterfaceTool]:
        if role is not None and role != ServiceRole.DATA_SOURCE:
            return []
        return [self._headlines_tool(), self._search_tool()]

    def _headlines_tool(self) -> InterfaceTool:
        def _handler(
            agent_id: str,
            query: str = "",
            category: str = "",
            country: str = "",
            page_size: int = 10,
        ) -> ServiceResult | str:
            params: dict[str, Any] = {"page_size": page_size}
            if query:
                params["query"] = query
            if category:
                params["category"] = category
            if country:
                params["country"] = country
            raw = self._fetch_callback(agent_id, self.service_id, "top_headlines", params)  # type: ignore[attr-defined]
            try:
                data = json.loads(raw)
                if isinstance(data, list):
                    return ServiceResult.from_list(data, summary=f"{len(data)} top headlines")
                if "error" in data:
                    return raw
                return ServiceResult.from_list(data.get("articles", [data]), summary=f"Top headlines")
            except (json.JSONDecodeError, TypeError):
                return raw

        return InterfaceTool(
            name="newsapi_get_top_headlines",
            short_description="Fetch current top headlines from NewsAPI.",
            full_description=(
                "Fetches current top headlines, optionally filtered by keyword, "
                "category, or country."
            ),
            arguments=[
                ToolArgument(name="query", type="string", description="Keyword filter on headline text", required=False),
                ToolArgument(name="category", type="string", description="business|entertainment|general|health|science|sports|technology", required=False),
                ToolArgument(name="country", type="string", description="ISO 3166-1 alpha-2 country code, e.g. 'us'", required=False),
                ToolArgument(name="page_size", type="integer", description="Max results (default 10, max 20)", required=False, default=10),
            ],
            returns_description="JSON array of {title, description, url, published_at, source_name, author}",
            service_id=self.service_id,
            service_type="data_source",
            handler=_handler,
        )

    def _search_tool(self) -> InterfaceTool:
        def _handler(
            agent_id: str,
            query: str,
            from_date: str = "",
            to_date: str = "",
            sort_by: str = "relevancy",
            page_size: int = 10,
        ) -> ServiceResult | str:
            params: dict[str, Any] = {
                "query": query,
                "sort_by": sort_by,
                "page_size": page_size,
            }
            if from_date:
                params["from_date"] = from_date
            if to_date:
                params["to_date"] = to_date
            raw = self._fetch_callback(agent_id, self.service_id, "search_articles", params)  # type: ignore[attr-defined]
            try:
                data = json.loads(raw)
                if "error" in data:
                    return raw
                articles = data.get("articles", [])
                total = data.get("total_results", len(articles))
                return ServiceResult.from_list(
                    articles,
                    summary=f"{len(articles)} articles for \"{query}\" ({total} total)",
                )
            except (json.JSONDecodeError, TypeError):
                return raw

        return InterfaceTool(
            name="newsapi_search_articles",
            short_description="Full-text article search via NewsAPI.",
            full_description=(
                "Full-text article search across all indexed sources. "
                "Supports AND, OR, NOT operators in the query."
            ),
            arguments=[
                ToolArgument(name="query", type="string", description="Search terms (supports AND/OR/NOT operators)"),
                ToolArgument(name="from_date", type="string", description="Start date YYYY-MM-DD (default 7 days ago)", required=False),
                ToolArgument(name="to_date", type="string", description="End date YYYY-MM-DD (default today)", required=False),
                ToolArgument(name="sort_by", type="string", description="relevancy|popularity|publishedAt (default relevancy)", required=False, default="relevancy"),
                ToolArgument(name="page_size", type="integer", description="Max results (default 10, max 20)", required=False, default=10),
            ],
            returns_description="JSON object {total_results, articles: [{title, description, url, published_at, source_name, content_snippet}]}",
            service_id=self.service_id,
            service_type="data_source",
            handler=_handler,
        )

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    def _request(self, endpoint: str, params: dict) -> dict:
        session = self._session or requests.Session()
        if not self._session:
            session.headers["X-Api-Key"] = self._api_key
        resp = session.get(f"{_BASE_URL}/{endpoint}", params=params, timeout=10)
        if resp.status_code == 401:
            raise RuntimeError("NewsAPI authentication failed — check api key")
        if resp.status_code == 426:
            raise RuntimeError("NewsAPI plan limit: this endpoint requires a paid plan")
        if resp.status_code == 429:
            raise RuntimeError("NewsAPI rate limit exceeded")
        if resp.status_code >= 400:
            try:
                msg = resp.json().get("message", resp.text)
            except Exception:
                msg = resp.text
            raise RuntimeError(f"NewsAPI error {resp.status_code}: {msg}")
        return resp.json()

    def _get_top_headlines(
        self,
        query: str = "",
        category: str = "",
        country: str = "",
        page_size: int = 10,
    ) -> dict:
        params: dict[str, Any] = {"pageSize": min(page_size, 20)}
        if query:
            params["q"] = query
        if category:
            params["category"] = category
        if country:
            params["country"] = country
        data = self._request("top-headlines", params)
        articles = [
            self._format_article(a, author=a.get("author", ""))
            for a in data.get("articles", [])
        ]
        return {"articles": articles}

    def _search_articles(
        self,
        query: str,
        from_date: str = "",
        to_date: str = "",
        sort_by: str = "relevancy",
        page_size: int = 10,
    ) -> dict:
        today = datetime.now(timezone.utc)
        params: dict[str, Any] = {
            "q": query,
            "sortBy": sort_by,
            "pageSize": min(page_size, 20),
            "from": from_date or (today - timedelta(days=7)).strftime("%Y-%m-%d"),
            "to": to_date or today.strftime("%Y-%m-%d"),
        }
        data = self._request("everything", params)
        articles = [
            self._format_article(a, content_snippet=a.get("content", ""))
            for a in data.get("articles", [])
        ]
        return {
            "total_results": data.get("totalResults", 0),
            "articles": articles,
        }

    @staticmethod
    def _format_article(raw: dict, **extra: str) -> dict:
        """Extract common article fields from a raw NewsAPI article dict."""
        result = {
            "title": raw.get("title", ""),
            "description": raw.get("description", ""),
            "url": raw.get("url", ""),
            "published_at": raw.get("publishedAt", ""),
            "source_name": (raw.get("source") or {}).get("name", ""),
        }
        result.update(extra)
        return result
