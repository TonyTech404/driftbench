"""A minimal MCP client for remote servers over streamable HTTP.

It covers what driftbench needs: initialize a session once, then call tools. Implementing the
few JSON-RPC messages directly avoids an SDK dependency and makes the exact traffic easy to test.
"""

from __future__ import annotations

import json

import httpx

from .. import __version__

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


class McpClient:
    def __init__(
        self,
        url: str,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 180,
        headers: dict[str, str] | None = None,
    ):
        self.url = url
        self.client = httpx.Client(
            timeout=timeout,
            transport=transport,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "User-Agent": "driftbench",
                **(headers or {}),
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
        resp = self.client.post(self.url, json=body, headers=headers)
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
                "clientInfo": {"name": "driftbench", "version": __version__},
            },
        )
        self._rpc("notifications/initialized", notify=True)

    def call_tool(self, name: str, arguments: dict) -> tuple[str, bool]:
        """Call a tool and return (text, is_error), preferring structured output when present."""
        self._ensure_session()
        result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        structured = result.get("structuredContent")
        if isinstance(structured, dict) and isinstance(structured.get("result"), str):
            text = structured["result"]
        else:
            text = "\n".join(c.get("text", "") for c in result.get("content", []) if c.get("type") == "text")
        return text, bool(result.get("isError"))
