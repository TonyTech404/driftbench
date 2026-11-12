"""DeepWiki's public MCP server (mcp.deepwiki.com), using its ask_wiki_question tool.

No key needed. Speaks MCP's streamable HTTP transport directly, so there is no SDK dependency.
"""

from __future__ import annotations

import json

import httpx

from ..questions import Question
from .base import Tool, ToolResponse, timed

URL = "https://mcp.deepwiki.com/mcp"
PROTOCOL = "2025-06-18"


def _parse(resp: httpx.Response) -> dict:
    """MCP servers may answer with plain JSON or a server-sent-events stream."""
    if resp.headers.get("content-type", "").startswith("text/event-stream"):
        for line in resp.text.splitlines():
            if line.startswith("data:"):
                msg = json.loads(line[5:].strip())
                if "result" in msg or "error" in msg:
                    return msg
        raise ValueError("no JSON-RPC result in event stream")
    return resp.json()


class DeepWiki(Tool):
    name = "deepwiki"

    def __init__(self) -> None:
        self.client = httpx.Client(
            timeout=180,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "User-Agent": "driftbench",
            },
        )
        self.session: str | None = None
        self._id = 0

    def _rpc(self, method: str, params: dict | None = None, notify: bool = False) -> dict:
        body: dict = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            body["params"] = params
        if not notify:
            self._id += 1
            body["id"] = self._id
        headers = {"MCP-Protocol-Version": PROTOCOL}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        resp = self.client.post(URL, json=body, headers=headers)
        resp.raise_for_status()
        if sid := resp.headers.get("mcp-session-id"):
            self.session = sid
        if notify:
            return {}
        msg = _parse(resp)
        if "error" in msg:
            raise RuntimeError(f"MCP error: {msg['error']}")
        return msg["result"]

    def _ensure_session(self) -> None:
        if self.session is not None:
            return
        self._rpc(
            "initialize",
            {
                "protocolVersion": PROTOCOL,
                "capabilities": {},
                "clientInfo": {"name": "driftbench", "version": "0.1.0"},
            },
        )
        self._rpc("notifications/initialized", notify=True)

    def ask(self, q: Question, query: str, variant: str) -> ToolResponse:
        def go() -> ToolResponse:
            self._ensure_session()
            result = self._rpc(
                "tools/call",
                {"name": "ask_wiki_question", "arguments": {"repoName": q.repo, "question": query}},
            )
            if structured := result.get("structuredContent"):
                text = structured.get("result", "")
            else:
                text = "\n".join(c.get("text", "") for c in result.get("content", []))
            error = text if result.get("isError") else None
            return ToolResponse(text=text, meta={"repo": q.repo}, error=error)

        return timed(go)
