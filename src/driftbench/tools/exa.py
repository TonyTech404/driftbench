"""Exa web search (exa.ai): `auto` search with highlights, as Exa's API reference recommends.

Needs EXA_API_KEY; skipped otherwise. Exa's own cost estimate for each search is kept in the
row's meta, so a run's spend is visible.
"""

from __future__ import annotations

import os

import httpx

from ..questions import Question
from .base import Tool, ToolResponse, timed

URL = "https://api.exa.ai/search"


class Exa(Tool):
    name = "exa"

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self.client = httpx.Client(headers={"User-Agent": "driftbench"}, timeout=60, transport=transport)

    def available(self) -> tuple[bool, str]:
        if not os.environ.get("EXA_API_KEY"):
            return False, "EXA_API_KEY not set"
        return True, ""

    def ask(self, q: Question, query: str, variant: str) -> ToolResponse:
        def go() -> ToolResponse:
            resp = self.client.post(
                URL,
                headers={"x-api-key": os.environ["EXA_API_KEY"]},
                json={"query": query, "type": "auto", "numResults": 10, "contents": {"highlights": True}},
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results") or []
            parts = []
            for r in results:
                body = "\n".join(r.get("highlights") or []) or r.get("text") or ""
                parts.append(f"Source: {r.get('url', '')}\n{body}")
            meta = {
                "urls": [r.get("url") for r in results],
                "cost_dollars": (data.get("costDollars") or {}).get("total"),
                "request_id": data.get("requestId"),
            }
            return ToolResponse(text="\n\n".join(parts), meta=meta)

        return timed(go)
