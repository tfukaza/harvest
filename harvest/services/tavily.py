"""TavilyService — DATA_SOURCE service wrapping the Tavily API.

Phase 21 service implementation.
API: https://api.tavily.com
Endpoints: /search, /extract, /crawl
Requires: ``requests``
"""


import json
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
from harvest.tools.result_buffer import ServiceResult

_API_BASE = "https://api.tavily.com"
_VALID_SEARCH_DEPTHS = {"basic", "advanced"}
_VALID_TOPICS = {"general", "news", "finance"}
_VALID_TIME_RANGES = {"day", "week", "month", "year"}
_VALID_EXTRACT_DEPTHS = {"basic", "advanced"}


class TavilyService(Service):
    """DATA_SOURCE service backed by the Tavily web-search, extract, and crawl API.

    Exposes three tools:
    - ``tavily_search`` — web search with answer and ranked results
    - ``tavily_extract`` — extract content from specific URLs
    - ``tavily_crawl`` — graph-based website crawling

    Args:
        api_key: Tavily API key (Bearer token).
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._session: requests.Session | None = None

    # ------------------------------------------------------------------
    # Service identity
    # ------------------------------------------------------------------

    @property
    def service_id(self) -> str:
        return "tavily"

    @property
    def roles(self) -> frozenset[ServiceRole]:
        return frozenset({ServiceRole.DATA_SOURCE})

    def get_capabilities(self) -> list[str]:
        return ["web_search", "extract", "crawl"]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self, event_bus: Any = None) -> None:
        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {self._api_key}"
        self._session.headers["Content-Type"] = "application/json"
        # Validate key with a minimal search request
        resp = self._session.post(
            f"{_API_BASE}/search",
            json={"query": "ping", "max_results": 1, "search_depth": "basic"},
            timeout=15,
        )
        if resp.status_code == 401:
            raise RuntimeError("Tavily authentication failed — check api key")
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise RuntimeError(f"Tavily startup check failed: {resp.status_code}: {detail}")

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
            "search": self._search,
            "extract": self._extract,
            "crawl": self._crawl,
        })

    # ------------------------------------------------------------------
    # ACTION: not applicable
    # ------------------------------------------------------------------

    async def execute(self, command: ActionCommand) -> ActionResult:
        raise NotImplementedError("TavilyService has no ACTION role")

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    def get_tools(self, role: ServiceRole | None = None) -> list[InterfaceTool]:
        if role is not None and role != ServiceRole.DATA_SOURCE:
            return []
        return [self._search_tool(), self._extract_tool(), self._crawl_tool()]

    def _search_tool(self) -> InterfaceTool:
        def _handler(
            agent_id: str,
            query: str,
            search_depth: str = "basic",
            topic: str = "general",
            max_results: int = 5,
            include_answer: bool = True,
            time_range: str = "",
        ) -> ServiceResult | str:
            params: dict[str, Any] = {
                "query": query,
                "search_depth": search_depth,
                "topic": topic,
                "max_results": max_results,
                "include_answer": include_answer,
            }
            if time_range:
                params["time_range"] = time_range
            raw = self._fetch_callback(agent_id, self.service_id, "search", params)  # type: ignore[attr-defined]
            try:
                data = json.loads(raw)
                if "error" in data:
                    return raw
                results = data.get("results", [])
                n = len(results)
                return ServiceResult.from_dict(
                    data,
                    summary=f"{n} search results for \"{query}\", answer included" if data.get("answer") else f"{n} search results for \"{query}\"",
                )
            except (json.JSONDecodeError, TypeError):
                return raw

        return InterfaceTool(
            name="tavily_search",
            short_description="Web search with answer and ranked results via Tavily.",
            full_description=(
                "Search the web using Tavily and get a synthesized answer plus "
                "ranked results with titles, URLs, content snippets, and relevance scores. "
                "Use topic to constrain to general, news, or finance. "
                "Use time_range to filter by recency (day, week, month, year)."
            ),
            arguments=[
                ToolArgument(name="query", type="string", description="The search query in natural language"),
                ToolArgument(name="search_depth", type="string", description="basic (faster) or advanced (more thorough)", required=False, default="basic"),
                ToolArgument(name="topic", type="string", description="general|news|finance", required=False, default="general"),
                ToolArgument(name="max_results", type="integer", description="Number of results (1-20)", required=False, default="5"),
                ToolArgument(name="include_answer", type="boolean", description="Include AI-generated answer", required=False, default="true"),
                ToolArgument(name="time_range", type="string", description="day|week|month|year — filter by recency", required=False),
            ],
            returns_description="JSON object {answer, results: [{title, url, content, score}], response_time}",
            service_id=self.service_id,
            service_type="data_source",
            handler=_handler,
        )

    def _extract_tool(self) -> InterfaceTool:
        def _handler(
            agent_id: str,
            urls: str,
            extract_depth: str = "basic",
        ) -> ServiceResult | str:
            params: dict[str, Any] = {
                "urls": urls,
                "extract_depth": extract_depth,
            }
            raw = self._fetch_callback(agent_id, self.service_id, "extract", params)  # type: ignore[attr-defined]
            try:
                data = json.loads(raw)
                if "error" in data:
                    return raw
                results = data.get("results", [])
                failed = data.get("failed_results", [])
                return ServiceResult.from_list(
                    results,
                    summary=f"Extracted {len(results)} page(s){f', {len(failed)} failed' if failed else ''}",
                )
            except (json.JSONDecodeError, TypeError):
                return raw

        return InterfaceTool(
            name="tavily_extract",
            short_description="Extract content from specific URLs via Tavily.",
            full_description=(
                "Extract and read the full content of one or more web pages. "
                "Pass a single URL or multiple comma-separated URLs. "
                "Returns the raw markdown content of each page."
            ),
            arguments=[
                ToolArgument(name="urls", type="string", description="Single URL or comma-separated URLs to extract content from"),
                ToolArgument(name="extract_depth", type="string", description="basic or advanced (handles JS-rendered pages)", required=False, default="basic"),
            ],
            returns_description="JSON object {results: [{url, raw_content}], failed_results}",
            service_id=self.service_id,
            service_type="data_source",
            handler=_handler,
        )

    def _crawl_tool(self) -> InterfaceTool:
        def _handler(
            agent_id: str,
            url: str,
            max_depth: int = 1,
            max_breadth: int = 20,
            limit: int = 50,
            instructions: str = "",
        ) -> ServiceResult | str:
            params: dict[str, Any] = {
                "url": url,
                "max_depth": max_depth,
                "max_breadth": max_breadth,
                "limit": limit,
            }
            if instructions:
                params["instructions"] = instructions
            raw = self._fetch_callback(agent_id, self.service_id, "crawl", params)  # type: ignore[attr-defined]
            try:
                data = json.loads(raw)
                if "error" in data:
                    return raw
                results = data.get("results", [])
                return ServiceResult.from_list(
                    results,
                    summary=f"Crawled {len(results)} page(s) from {data.get('base_url', url)}",
                )
            except (json.JSONDecodeError, TypeError):
                return raw

        return InterfaceTool(
            name="tavily_crawl",
            short_description="Crawl a website and extract content from multiple pages.",
            full_description=(
                "Graph-based website crawler that explores a site starting from the given URL. "
                "Follows links up to max_depth levels deep and max_breadth links per page. "
                "Use instructions to guide the crawler with natural language (e.g. "
                "'focus on the about page and team bios'). Returns content from each crawled page."
            ),
            arguments=[
                ToolArgument(name="url", type="string", description="Root URL to start crawling from"),
                ToolArgument(name="max_depth", type="integer", description="How many link-hops deep to crawl (1-5)", required=False, default="1"),
                ToolArgument(name="max_breadth", type="integer", description="Max links to follow per page (1-50)", required=False, default="20"),
                ToolArgument(name="limit", type="integer", description="Total max pages to crawl", required=False, default="50"),
                ToolArgument(name="instructions", type="string", description="Natural language guidance for the crawler", required=False),
            ],
            returns_description="JSON object {base_url, results: [{url, raw_content}]}",
            service_id=self.service_id,
            service_type="data_source",
            handler=_handler,
        )

    # ------------------------------------------------------------------
    # Internal API helpers
    # ------------------------------------------------------------------

    def _make_request(self, endpoint: str, body: dict[str, Any], timeout: int = 30) -> dict:
        """Make a POST request to a Tavily API endpoint."""
        session = self._session or requests.Session()
        if not self._session:
            session.headers["Authorization"] = f"Bearer {self._api_key}"
            session.headers["Content-Type"] = "application/json"

        resp = session.post(f"{_API_BASE}/{endpoint}", json=body, timeout=timeout)
        if resp.status_code == 401:
            raise RuntimeError("Tavily authentication failed — check api key")
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After", "")
            msg = "Tavily rate limit exceeded"
            if retry_after:
                msg += f" (retry after {retry_after}s)"
            raise RuntimeError(msg)
        if resp.status_code == 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise RuntimeError(f"Tavily bad request: {detail}")
        if resp.status_code >= 400:
            try:
                msg = resp.json().get("detail", resp.text)
            except Exception:
                msg = resp.text
            raise RuntimeError(f"Tavily error {resp.status_code}: {msg}")

        return resp.json()

    def _search(
        self,
        query: str,
        search_depth: str = "basic",
        topic: str = "general",
        max_results: int = 5,
        include_answer: bool = True,
        time_range: str = "",
    ) -> dict:
        if search_depth not in _VALID_SEARCH_DEPTHS:
            search_depth = "basic"
        if topic not in _VALID_TOPICS:
            topic = "general"
        max_results = max(1, min(20, max_results))

        body: dict[str, Any] = {
            "query": query,
            "search_depth": search_depth,
            "topic": topic,
            "max_results": max_results,
            "include_answer": include_answer,
        }
        if time_range and time_range in _VALID_TIME_RANGES:
            body["time_range"] = time_range

        data = self._make_request("search", body)
        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
                "score": r.get("score", 0),
            }
            for r in data.get("results", [])
        ]
        return {
            "answer": data.get("answer", ""),
            "results": results,
            "response_time": data.get("response_time", 0),
        }

    def _extract(
        self,
        urls: str,
        extract_depth: str = "basic",
    ) -> dict:
        if extract_depth not in _VALID_EXTRACT_DEPTHS:
            extract_depth = "basic"

        # Support comma-separated URLs
        url_list = [u.strip() for u in urls.split(",") if u.strip()]
        if not url_list:
            return {"error": "No valid URLs provided", "results": [], "failed_results": []}

        body: dict[str, Any] = {
            "urls": url_list if len(url_list) > 1 else url_list[0],
            "extract_depth": extract_depth,
            "format": "markdown",
        }

        data = self._make_request("extract", body)
        results = [
            {"url": r.get("url", ""), "raw_content": r.get("raw_content", "")}
            for r in data.get("results", [])
        ]
        failed = [
            {"url": r.get("url", ""), "error": r.get("error", "")}
            for r in data.get("failed_results", [])
        ]
        return {"results": results, "failed_results": failed}

    def _crawl(
        self,
        url: str,
        max_depth: int = 1,
        max_breadth: int = 20,
        limit: int = 50,
        instructions: str = "",
    ) -> dict:
        max_depth = max(1, min(5, max_depth))
        max_breadth = max(1, min(50, max_breadth))
        limit = max(1, limit)

        body: dict[str, Any] = {
            "url": url,
            "max_depth": max_depth,
            "max_breadth": max_breadth,
            "limit": limit,
            "format": "markdown",
        }
        if instructions:
            body["instructions"] = instructions

        data = self._make_request("crawl", body, timeout=160)
        results = [
            {"url": r.get("url", ""), "raw_content": r.get("raw_content", "")}
            for r in data.get("results", [])
        ]
        return {
            "base_url": data.get("base_url", url),
            "results": results,
        }
