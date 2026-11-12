"""Exa's hosted MCP server (mcp.exa.ai), using its web_search_exa tool with default settings.

This is how coding agents usually reach Exa. Exa allows keyless search at a free rate limit
(over a direct IPv4 connection); set EXA_API_KEY to use your own quota, sent as the x-api-key
header per Exa's MCP docs. The `exa` tool calls Exa's search API directly instead.
"""

from __future__ import annotations

import os

import httpx

from ..questions import Question
from .base import Tool, ToolResponse, timed
from .mcp import McpClient

URL = "https://mcp.exa.ai/mcp"


class ExaMcp(Tool):
    name = "exa-mcp"

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        key = os.environ.get("EXA_API_KEY")
        headers = {"x-api-key": key} if key else None
        self.mcp = McpClient(URL, transport=transport, timeout=90, headers=headers)

    def ask(self, q: Question, query: str, variant: str) -> ToolResponse:
        def go() -> ToolResponse:
            text, is_error = self.mcp.call_tool("web_search_exa", {"query": query})
            return ToolResponse(text=text, error=text if is_error else None)

        return timed(go)
