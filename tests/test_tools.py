"""Offline tests for the tool adapters, using simulated HTTP responses.

They check what each adapter sends (endpoint, auth, body) and how it reads the documented
response shapes, so CI needs no network and no API keys. tests/test_live.py calls the real
services.
"""

import json

import httpx
import pytest

from driftbench.questions import Question
from driftbench.tools import Context7, DeepWiki, Exa, ExaMcp

Q = Question.from_dict(
    {
        "id": "t",
        "library": "Hono",
        "repo": "honojs/hono",
        "version": "4.13.13",
        "release_date": "2026-10-04",
        "old_api": "app.mount",
        "new_api": "mount()",
        "old_patterns": [r"\.mount\s*\("],
        "new_patterns": [r"(?<![.\w])mount\s*\("],
        "question": "How do I mount a router in Hono?",
        "question_with_version": "How do I mount a router in Hono 4.13?",
        "source_url": "https://example.com",
    }
)


class Recorder:
    """A mock transport that records requests and answers from a handler."""

    def __init__(self, handler):
        self.requests: list[httpx.Request] = []
        self.handler = handler
        self.transport = httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.handler(request)


# --- Exa -------------------------------------------------------------------------------------

EXA_RESPONSE = {
    "requestId": "req-123",
    "results": [
        {
            "title": "Mount Middleware",
            "url": "https://hono.dev/docs/middleware/builtin/mount",
            "id": "a",
            "text": "full page text",
            "highlights": ["app.all('/x/*', mount(h))", "import { mount } from 'hono/mount'"],
        },
        {"title": "Old post", "url": "https://blog.example/hono", "id": "b", "text": "app.mount('/x', h)"},
    ],
    "costDollars": {"total": 0.007, "search": {"neural": 0.005}, "contents": {"highlights": 0.002}},
    "searchTime": 412.5,
}


def test_exa_is_skipped_without_a_key(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    assert Exa().available() == (False, "EXA_API_KEY not set")
    monkeypatch.setenv("EXA_API_KEY", "k")
    assert Exa().available() == (True, "")


def test_exa_sends_documented_request(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "secret")
    rec = Recorder(lambda req: httpx.Response(200, json=EXA_RESPONSE))
    Exa(transport=rec.transport).ask(Q, Q.question, "plain")

    [req] = rec.requests
    assert req.method == "POST"
    assert str(req.url) == "https://api.exa.ai/search"
    assert req.headers["x-api-key"] == "secret"
    assert json.loads(req.content) == {
        "query": Q.question,
        "type": "auto",
        "numResults": 10,
        "contents": {"highlights": True},
    }


def test_exa_reads_highlights_falls_back_to_text_and_keeps_cost(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "k")
    rec = Recorder(lambda req: httpx.Response(200, json=EXA_RESPONSE))
    resp = Exa(transport=rec.transport).ask(Q, Q.question, "plain")

    assert resp.error is None
    assert resp.text == (
        "Source: https://hono.dev/docs/middleware/builtin/mount\n"
        "app.all('/x/*', mount(h))\nimport { mount } from 'hono/mount'\n\n"
        "Source: https://blog.example/hono\napp.mount('/x', h)"
    )
    assert resp.meta == {
        "urls": ["https://hono.dev/docs/middleware/builtin/mount", "https://blog.example/hono"],
        "cost_dollars": 0.007,
        "request_id": "req-123",
    }


def test_exa_http_error_is_recorded_not_raised(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "bad")
    rec = Recorder(lambda req: httpx.Response(401, json={"error": "invalid api key"}))
    resp = Exa(transport=rec.transport).ask(Q, Q.question, "plain")
    assert resp.text == ""
    assert resp.error.startswith("HTTPStatusError")
    assert resp.ms >= 0


def test_exa_handles_empty_results(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "k")
    rec = Recorder(lambda req: httpx.Response(200, json={"requestId": "r", "results": []}))
    resp = Exa(transport=rec.transport).ask(Q, Q.question, "plain")
    assert resp.text == ""
    assert resp.error is None
    assert resp.meta["cost_dollars"] is None


# --- Context7 --------------------------------------------------------------------------------


def context7_handler(docs_status=200):
    def handle(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/api/v2/libs/search":
            return httpx.Response(200, json={"results": [{"id": "/honojs/hono"}, {"id": "/other/lib"}]})
        if req.url.path == "/api/v2/context":
            return httpx.Response(docs_status, text="### Mount\n```ts\nmount(h)\n```")
        return httpx.Response(500)

    return handle


def test_context7_resolves_library_then_fetches_docs(monkeypatch):
    monkeypatch.delenv("CONTEXT7_API_KEY", raising=False)
    rec = Recorder(context7_handler())
    resp = Context7(transport=rec.transport).ask(Q, Q.question, "plain")

    search, docs = rec.requests
    assert search.url.params["libraryName"] == "Hono"
    assert search.url.params["query"] == Q.question
    assert docs.url.params["libraryId"] == "/honojs/hono"  # the top search result
    assert docs.url.params["type"] == "txt"
    assert "authorization" not in docs.headers
    assert resp.text.startswith("### Mount")
    assert resp.meta == {"library_id": "/honojs/hono"}


def test_context7_sends_key_when_set(monkeypatch):
    monkeypatch.setenv("CONTEXT7_API_KEY", "ctx7")
    rec = Recorder(context7_handler())
    Context7(transport=rec.transport).ask(Q, Q.question, "plain")
    assert all(r.headers["authorization"] == "Bearer ctx7" for r in rec.requests)


def test_context7_no_docs_is_an_answer_not_an_error():
    rec = Recorder(context7_handler(docs_status=404))
    resp = Context7(transport=rec.transport).ask(Q, Q.question, "plain")
    assert resp.text == "No documentation found."
    assert resp.error is None


def test_context7_unknown_library():
    rec = Recorder(lambda req: httpx.Response(200, json={"results": []}))
    resp = Context7(transport=rec.transport).ask(Q, Q.question, "plain")
    assert len(rec.requests) == 1
    assert resp.text == ""
    assert resp.meta == {"library_id": None}


# --- DeepWiki --------------------------------------------------------------------------------


def sse(message: dict) -> httpx.Response:
    body = f"event: message\ndata: {json.dumps(message)}\n\n"
    return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})


def deepwiki_handler(tool_result: dict):
    def handle(req: httpx.Request) -> httpx.Response:
        msg = json.loads(req.content)
        if msg["method"] == "initialize":
            resp = sse({"jsonrpc": "2.0", "id": msg["id"], "result": {"protocolVersion": "2025-06-18"}})
            resp.headers["mcp-session-id"] = "sess-1"
            return resp
        if msg["method"] == "notifications/initialized":
            return httpx.Response(202)
        if msg["method"] == "tools/call":
            return sse({"jsonrpc": "2.0", "id": msg["id"], "result": tool_result})
        return httpx.Response(400)

    return handle


def test_deepwiki_initializes_once_and_reuses_the_session():
    rec = Recorder(deepwiki_handler({"structuredContent": {"result": "Use `mount(h)`."}}))
    tool = DeepWiki(transport=rec.transport)
    first = tool.ask(Q, Q.question, "plain")
    tool.ask(Q, Q.question_with_version, "versioned")

    methods = [json.loads(r.content)["method"] for r in rec.requests]
    assert methods == ["initialize", "notifications/initialized", "tools/call", "tools/call"]
    assert "id" not in json.loads(rec.requests[1].content)  # notifications carry no id
    for r in rec.requests[1:]:
        assert r.headers["mcp-session-id"] == "sess-1"
        assert r.headers["mcp-protocol-version"] == "2025-06-18"
    call = json.loads(rec.requests[2].content)
    assert call["params"] == {
        "name": "ask_wiki_question",
        "arguments": {"repoName": "honojs/hono", "question": Q.question},
    }
    assert first.text == "Use `mount(h)`."
    assert first.error is None


def test_deepwiki_reads_plain_content_blocks():
    rec = Recorder(
        deepwiki_handler({"content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]})
    )
    assert DeepWiki(transport=rec.transport).ask(Q, Q.question, "plain").text == "a\nb"


def test_deepwiki_tool_error_is_recorded():
    result = {"isError": True, "content": [{"type": "text", "text": "Repository not indexed"}]}
    rec = Recorder(deepwiki_handler(result))
    resp = DeepWiki(transport=rec.transport).ask(Q, Q.question, "plain")
    assert resp.error == "Repository not indexed"


def test_deepwiki_json_rpc_error_is_recorded():
    def handle(req):
        msg = json.loads(req.content)
        if msg["method"] == "tools/call":
            return sse({"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32602, "message": "bad"}})
        return deepwiki_handler({})(req)

    resp = DeepWiki(transport=httpx.MockTransport(handle)).ask(Q, Q.question, "plain")
    assert resp.error.startswith("RuntimeError: MCP error")


@pytest.mark.parametrize("tool_cls", [Context7, DeepWiki, ExaMcp])
def test_network_failure_is_recorded(tool_cls):
    def boom(req):
        raise httpx.ConnectError("no route to host")

    resp = tool_cls(transport=httpx.MockTransport(boom)).ask(Q, Q.question, "plain")
    assert resp.error == "ConnectError: no route to host"


# --- Exa MCP ---------------------------------------------------------------------------------


def test_exa_mcp_calls_web_search_with_defaults(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    content = {"content": [{"type": "text", "text": "Title: Mount\nURL: https://hono.dev\nmount(h)"}]}
    rec = Recorder(deepwiki_handler(content))
    resp = ExaMcp(transport=rec.transport).ask(Q, Q.question, "plain")

    call = json.loads(rec.requests[2].content)
    assert str(rec.requests[2].url) == "https://mcp.exa.ai/mcp"
    assert call["params"] == {"name": "web_search_exa", "arguments": {"query": Q.question}}
    assert "x-api-key" not in rec.requests[0].headers
    assert resp.text.endswith("mount(h)")
    assert resp.error is None


def test_exa_mcp_sends_key_as_header(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "secret")
    rec = Recorder(deepwiki_handler({"content": []}))
    ExaMcp(transport=rec.transport).ask(Q, Q.question, "plain")
    assert all(r.headers["x-api-key"] == "secret" for r in rec.requests)
    assert "secret" not in str(rec.requests[0].url)


def test_exa_mcp_rate_limit_is_recorded():
    rec = Recorder(lambda req: httpx.Response(429, text="rate limited"))
    resp = ExaMcp(transport=rec.transport).ask(Q, Q.question, "plain")
    assert resp.error.startswith("HTTPStatusError")
