"""PerplexityService — DATA_SOURCE service wrapping the Perplexity AI API.

Phase 16 concrete service implementation.
API: OpenAI-compatible chat completions at https://api.perplexity.ai/chat/completions
Requires: ``requests``
"""

from __future__ import annotations

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

_API_URL = "https://api.perplexity.ai/chat/completions"
_DEFAULT_MODEL = "sonar"
_VALID_MODELS = {"sonar", "sonar-pro", "sonar-reasoning"}


class PerplexityService(Service):
    """DATA_SOURCE service backed by the Perplexity AI web-search API.

    Exposes two tools:
    - ``perplexity_search`` — general search with citations
    - ``perplexity_search_focused`` — domain-constrained search

    Args:
        api_key: Perplexity API key (Bearer token).
        default_model: Model used when the caller does not specify one.
    """

    def __init__(self, api_key: str, default_model: str = _DEFAULT_MODEL) -> None:
        self._api_key = api_key
        self._default_model = default_model
        self._session: requests.Session | None = None

    # ------------------------------------------------------------------
    # Service identity
    # ------------------------------------------------------------------

    @property
    def service_id(self) -> str:
        return "perplexity"

    @property
    def roles(self) -> frozenset[ServiceRole]:
        return frozenset({ServiceRole.DATA_SOURCE})

    def get_capabilities(self) -> list[str]:
        return ["web_search", "focused_search"]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self, event_bus: Any = None) -> None:
        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {self._api_key}"
        self._session.headers["Content-Type"] = "application/json"
        # Validate key with a minimal request
        resp = self._session.post(
            _API_URL,
            json={
                "model": self._default_model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
            },
            timeout=15,
        )
        if resp.status_code == 401:
            raise RuntimeError("Perplexity authentication failed — check api key")
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise RuntimeError(f"Perplexity startup check failed: {resp.status_code}: {detail}")

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
            "search_focused": self._search_focused,
        })

    # ------------------------------------------------------------------
    # ACTION: not applicable
    # ------------------------------------------------------------------

    async def execute(self, command: ActionCommand) -> ActionResult:
        raise NotImplementedError("PerplexityService has no ACTION role")

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    def get_tools(self, role: ServiceRole | None = None) -> list[InterfaceTool]:
        if role is not None and role != ServiceRole.DATA_SOURCE:
            return []
        return [self._search_tool(), self._focused_tool()]

    def _search_tool(self) -> InterfaceTool:
        def _handler(
            agent_id: str,
            query: str,
            model: str = "",
            system_prompt: str = "",
        ) -> str:
            params: dict[str, Any] = {"query": query}
            if model:
                params["model"] = model
            if system_prompt:
                params["system_prompt"] = system_prompt
            return self._fetch_callback(agent_id, self.service_id, "search", params)  # type: ignore[attr-defined]

        return InterfaceTool(
            name="perplexity_search",
            short_description="Web-search-augmented answer with citations via Perplexity.",
            full_description=(
                "Ask a question and get a web-search-augmented answer with source citations. "
                "Perplexity searches the web and synthesizes a response."
            ),
            arguments=[
                ToolArgument(name="query", type="string", description="The question or search query in natural language"),
                ToolArgument(name="model", type="string", description="sonar (default)|sonar-pro|sonar-reasoning", required=False, default="sonar"),
                ToolArgument(name="system_prompt", type="string", description="System instruction to guide response style", required=False),
            ],
            returns_description="JSON object {answer, citations, model, usage}",
            service_id=self.service_id,
            service_type="data_source",
            handler=_handler,
        )

    def _focused_tool(self) -> InterfaceTool:
        def _handler(
            agent_id: str,
            query: str,
            search_focus: str,
            model: str = "",
        ) -> str:
            params: dict[str, Any] = {"query": query, "search_focus": search_focus}
            if model:
                params["model"] = model
            return self._fetch_callback(agent_id, self.service_id, "search_focused", params)  # type: ignore[attr-defined]

        return InterfaceTool(
            name="perplexity_search_focused",
            short_description="Domain-constrained web search via Perplexity.",
            full_description=(
                "Search with a specific focus area for more targeted results. "
                "Use search_focus to constrain the search domain."
            ),
            arguments=[
                ToolArgument(name="query", type="string", description="The question or search query"),
                ToolArgument(name="search_focus", type="string", description="web|news|academic|finance"),
                ToolArgument(name="model", type="string", description="sonar (default)|sonar-pro|sonar-reasoning", required=False, default="sonar"),
            ],
            returns_description="JSON object {answer, citations, model, usage}",
            service_id=self.service_id,
            service_type="data_source",
            handler=_handler,
        )

    # ------------------------------------------------------------------
    # Internal API helpers
    # ------------------------------------------------------------------

    def _call_api(
        self,
        query: str,
        model: str = "",
        system_prompt: str = "",
        search_focus: str = "",
    ) -> dict:
        chosen_model = model if model in _VALID_MODELS else self._default_model
        messages = []
        effective_system = system_prompt or ""
        if search_focus:
            domain_hints = {
                "news": "Focus on recent news articles and current events.",
                "academic": "Focus on academic research papers and scientific literature.",
                "finance": "Focus on financial data, market analysis, and economic information.",
                "web": "",
            }
            hint = domain_hints.get(search_focus, "")
            if hint:
                effective_system = f"{effective_system} {hint}".strip() if effective_system else hint
        if effective_system:
            messages.append({"role": "system", "content": effective_system})
        messages.append({"role": "user", "content": query})

        body: dict[str, Any] = {"model": chosen_model, "messages": messages}
        if search_focus and search_focus != "web":
            body["search_domain_filter"] = [search_focus]

        session = self._session or requests.Session()
        if not self._session:
            session.headers["Authorization"] = f"Bearer {self._api_key}"
            session.headers["Content-Type"] = "application/json"

        resp = session.post(_API_URL, json=body, timeout=30)
        if resp.status_code == 401:
            raise RuntimeError("Perplexity authentication failed — check api key")
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After", "")
            msg = "Perplexity rate limit exceeded"
            if retry_after:
                msg += f" (retry after {retry_after}s)"
            raise RuntimeError(msg)
        if resp.status_code == 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise RuntimeError(f"Perplexity bad request: {detail}")
        if resp.status_code >= 400:
            try:
                msg = resp.json().get("detail", resp.text)
            except Exception:
                msg = resp.text
            raise RuntimeError(f"Perplexity error {resp.status_code}: {msg}")

        data = resp.json()
        answer = ""
        choices = data.get("choices", [])
        if choices:
            answer = choices[0].get("message", {}).get("content", "")
        citations = data.get("citations", [])
        usage = data.get("usage", {})
        return {
            "answer": answer,
            "citations": citations,
            "model": chosen_model,
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
            },
        }

    def _search(
        self,
        query: str,
        model: str = "",
        system_prompt: str = "",
    ) -> dict:
        return self._call_api(query=query, model=model, system_prompt=system_prompt)

    def _search_focused(
        self,
        query: str,
        search_focus: str,
        model: str = "",
    ) -> dict:
        return self._call_api(query=query, model=model, search_focus=search_focus)
