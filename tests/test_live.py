"""Live checks against the real services. Skipped unless DRIFTBENCH_LIVE=1.

    DRIFTBENCH_LIVE=1 uv run pytest tests/test_live.py -v

The `exa` API check also needs EXA_API_KEY and costs about one search. These tests don't assert
which API a tool returns, only that the adapter still talks to the service correctly.
"""

import os
from pathlib import Path

import pytest

from driftbench.questions import load_questions
from driftbench.tools import Context7, DeepWiki, Exa, ExaMcp

pytestmark = pytest.mark.skipif(os.environ.get("DRIFTBENCH_LIVE") != "1", reason="set DRIFTBENCH_LIVE=1")

Q = next(
    q
    for q in load_questions(Path(__file__).parent.parent / "data/questions/2026-11.json")
    if q.id == "fastapi-root-path"
)


@pytest.mark.parametrize("tool_cls", [Context7, DeepWiki, ExaMcp, Exa], ids=lambda t: t.name)
def test_tool_answers(tool_cls):
    tool = tool_cls()
    ok, why = tool.available()
    if not ok:
        pytest.skip(why)
    resp = tool.ask(Q, Q.question, "plain")
    assert resp.error is None, resp.error
    assert len(resp.text) > 200
    assert "root_path" in resp.text or "root-path" in resp.text
