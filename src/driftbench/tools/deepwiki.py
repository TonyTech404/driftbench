"""DeepWiki's public MCP server (mcp.deepwiki.com), using its ask_wiki_question tool.

No key needed. DeepWiki answers from the repository's current source, so the question is asked
about the library's GitHub repo.
"""

from __future__ import annotations

import httpx

from ..questions import Question
from .base import Tool, ToolResponse, timed
from .mcp import McpClient

URL = "https://mcp.deepwiki.com/mcp"


class DeepWiki(Tool):
    name = "deepwiki"

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self.mcp = McpClient(URL, transport=transport)

    def ask(self, q: Question, query: str, variant: str) -> ToolResponse:
        def go() -> ToolResponse:
            text, is_error = self.mcp.call_tool("ask_wiki_question", {"repoName": q.repo, "question": query})
            return ToolResponse(text=text, meta={"repo": q.repo}, error=text if is_error else None)

        return timed(go)
