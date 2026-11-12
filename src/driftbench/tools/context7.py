"""Context7 (context7.com), called the same way its MCP server does: resolve the library, then fetch docs.

Works without an API key at low volume. Set CONTEXT7_API_KEY for higher rate limits.
"""

from __future__ import annotations

import os

import httpx

from ..questions import Question
from .base import Tool, ToolResponse, timed

BASE = "https://context7.com/api/v2"


class Context7(Tool):
    name = "context7"

    def __init__(self) -> None:
        headers = {"User-Agent": "driftbench"}
        if key := os.environ.get("CONTEXT7_API_KEY"):
            headers["Authorization"] = f"Bearer {key}"
        self.client = httpx.Client(headers=headers, timeout=60)

    def ask(self, q: Question, query: str, variant: str) -> ToolResponse:
        def go() -> ToolResponse:
            search = self.client.get(f"{BASE}/libs/search", params={"libraryName": q.library, "query": query})
            search.raise_for_status()
            results = search.json().get("results") or []
            if not results:
                return ToolResponse(text="", meta={"library_id": None})
            lib = results[0]
            docs = self.client.get(
                f"{BASE}/context",
                params={"libraryId": lib["id"], "query": query, "type": "txt"},
            )
            if docs.status_code == 404:
                return ToolResponse(text="No documentation found.", meta={"library_id": lib["id"]})
            docs.raise_for_status()
            return ToolResponse(text=docs.text, meta={"library_id": lib["id"]})

        return timed(go)
