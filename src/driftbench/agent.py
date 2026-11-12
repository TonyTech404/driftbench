"""Agent mode: give a real coding agent one documentation tool and label the code it writes.

The agent is Claude Code in headless mode (`claude -p`). Each run gets exactly one MCP server, or
none for the baseline. Built-in tools are switched off (no web search, no file access), user and
project settings are ignored, and the session runs in an empty directory, so the only outside
information is what the tool under test returns.

`claude` authenticates however it is logged in: a Claude subscription, or ANTHROPIC_API_KEY.
The run records which one was used. Cost figures are Claude Code's API-price estimates.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from .questions import Question, load_questions
from .run import digest, done_keys, label_fields, raw_path, write_raw

# MCP servers an agent can be given. All of them work without a key at low volume.
SETUPS: dict[str, dict | None] = {
    "none": None,
    "context7": {"type": "http", "url": "https://mcp.context7.com/mcp"},
    "deepwiki": {"type": "http", "url": "https://mcp.deepwiki.com/mcp"},
    "exa": {"type": "http", "url": "https://mcp.exa.ai/mcp"},
}
SERVER = "docs"  # every setup names its server the same, so prompts and tool names match

# The same prompt for every setup, so the only difference is which tool exists.
PROMPT = (
    "{question}\n\n"
    "If you have a tool for looking up documentation, use it to check the current API. "
    "Answer with a short code example."
)

LIMIT_MARKERS = ("usage limit", "rate limit", "limit reached", "credit balance", "quota")


@dataclass
class AgentResult:
    text: str
    tool_calls: list[dict] = field(default_factory=list)
    num_turns: int | None = None
    cost_usd: float | None = None
    model: str | None = None
    api_key_source: str | None = None
    ms: int = 0
    error: str | None = None

    @property
    def hit_limit(self) -> bool:
        return bool(self.error) and any(m in self.error.lower() for m in LIMIT_MARKERS)


def build_command(prompt: str, model: str, mcp_config: Path | None) -> list[str]:
    cmd = [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--model",
        model,
        "--tools",
        "",
        "--strict-mcp-config",
        "--setting-sources",
        "",
        "--no-session-persistence",
    ]
    if mcp_config is not None:
        cmd += ["--mcp-config", str(mcp_config), "--allowedTools", f"mcp__{SERVER}"]
    return cmd


def parse_stream(lines: list[str]) -> AgentResult:
    """Read Claude Code's stream-json events into one result."""
    res = AgentResult(text="")
    final = None
    for line in lines:
        line = line.strip()
        if not line.startswith("{"):
            continue
        msg = json.loads(line)
        kind = msg.get("type")
        if kind == "system" and msg.get("subtype") == "init":
            res.model = msg.get("model")
            res.api_key_source = msg.get("apiKeySource")
        elif kind == "assistant":
            for block in msg.get("message", {}).get("content", []):
                if block.get("type") == "tool_use":
                    res.tool_calls.append({"name": block.get("name"), "input": block.get("input")})
        elif kind == "result":
            final = msg
    if final is None:
        res.error = "no result event in output"
        return res
    res.text = final.get("result") or ""
    res.num_turns = final.get("num_turns")
    res.cost_usd = final.get("total_cost_usd")
    if final.get("is_error") or final.get("subtype") not in (None, "success"):
        res.error = res.text or str(final.get("subtype"))
    return res


Runner = Callable[[list[str], Path], tuple[int, str, str]]


def _subprocess_runner(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=600)
    return proc.returncode, proc.stdout, proc.stderr


def ask_agent(
    question: str, setup: str, model: str, workdir: Path, runner: Runner = _subprocess_runner
) -> AgentResult:
    server = SETUPS[setup]
    mcp_config = None
    if server is not None:
        mcp_config = workdir / f"mcp-{setup}.json"
        mcp_config.write_text(json.dumps({"mcpServers": {SERVER: server}}))
    cmd = build_command(PROMPT.format(question=question), model, mcp_config)
    start = time.perf_counter()
    try:
        code, out, err = runner(cmd, workdir)
        res = parse_stream(out.splitlines())
        if res.error is None and code != 0:
            res.error = f"claude exited with {code}: {err.strip()[:300]}"
    except (OSError, subprocess.TimeoutExpired) as e:
        res = AgentResult(text="", error=f"{type(e).__name__}: {e}")
    res.ms = round((time.perf_counter() - start) * 1000)
    return res


def run_agents(
    questions_path: Path,
    results_path: Path,
    setups: list[str],
    model: str = "sonnet",
    only: set[str] | None = None,
    variants: tuple[str, ...] = ("plain",),
    pause_s: float = 2.0,
    runner: Runner = _subprocess_runner,
) -> int:
    unknown = [s for s in setups if s not in SETUPS]
    if unknown:
        print(f"unknown setups: {', '.join(unknown)}; known: {', '.join(SETUPS)}", file=sys.stderr)
        return 2
    questions = [q for q in load_questions(questions_path) if not only or q.id in only]
    (results_path.parent / "raw").mkdir(parents=True, exist_ok=True)
    done = done_keys(results_path)

    with tempfile.TemporaryDirectory(prefix="driftbench-agent-") as tmp, results_path.open("a") as out:
        workdir = Path(tmp)
        for q in questions:
            for setup in setups:
                tool = f"agent-{setup}"
                for variant in variants:
                    if (q.id, tool, variant, 1) in done:
                        continue
                    res = ask_agent(q.text(variant), setup, model, workdir, runner)
                    if res.hit_limit:
                        print(
                            f"stopping: usage limit reached ({res.error[:120]}). Rerun to resume.",
                            file=sys.stderr,
                        )
                        return 3
                    write_raw(raw_path(results_path, q.id, tool, variant, 1), res.text)
                    row = _row(q, tool, variant, res)
                    out.write(json.dumps(row) + "\n")
                    out.flush()
                    calls = len(res.tool_calls)
                    print(
                        f"{q.id:36} {tool:15} {row['label']:8} {calls} calls {res.ms:7} ms", file=sys.stderr
                    )
                    time.sleep(pause_s)
    return 0


def _row(q: Question, tool: str, variant: str, res: AgentResult) -> dict:
    return {
        "question_id": q.id,
        "tool": tool,
        "variant": variant,
        "run": 1,
        **label_fields(q, res.text, res.error),
        "ms": res.ms,
        "chars": len(res.text),
        "sha256_16": digest(res.text),
        "meta": {
            "model": res.model,
            "auth": res.api_key_source,
            "tool_calls": [c["name"] for c in res.tool_calls],
            "num_turns": res.num_turns,
            "cost_usd_estimate": res.cost_usd,
        },
        "error": res.error,
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
