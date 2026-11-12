"""Exa web search (exa.ai), with the fast + highlights setup Exa recommends for coding questions.

Needs EXA_API_KEY; skipped otherwise.
"""

from __future__ import annotations

import os

import httpx

from ..questions import Question
from .base import Tool, ToolResponse, timed


class Exa(Tool):
    name = "exa"

    def available(self) -> tuple[bool, str]:
        if not os.environ.get("EXA_API_KEY"):
            return False, "EXA_API_KEY not set"
        return True, ""

    def ask(self, q: Question, query: str, variant: str) -> ToolResponse:
        def go() -> ToolResponse:
            resp = httpx.post(
                "https://api.exa.ai/search",
                headers={"x-api-key": os.environ["EXA_API_KEY"], "User-Agent": "driftbench"},
                json={"query": query, "type": "fast", "numResults": 10, "contents": {"highlights": True}},
                timeout=60,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            parts = []
            for r in results:
                body = "\n".join(r.get("highlights") or []) or r.get("text", "")
                parts.append(f"Source: {r.get('url', '')}\n{body}")
            return ToolResponse(text="\n\n".join(parts), meta={"urls": [r.get("url") for r in results]})

        return timed(go)
