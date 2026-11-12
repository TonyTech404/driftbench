"""Offline tests for agent mode. A fake `claude` replays the stream-json events the real CLI emits."""

import json
from pathlib import Path

from driftbench.agent import PROMPT, SETUPS, ask_agent, build_command, parse_stream, run_agents

QUESTIONS = Path(__file__).parent.parent / "data/questions/2026-11.json"


def stream(answer: str, tool_calls=(), is_error=False, subtype="success") -> str:
    events = [
        {"type": "system", "subtype": "init", "model": "claude-sonnet-5", "apiKeySource": "none"},
        *(
            {
                "type": "assistant",
                "message": {"content": [{"type": "tool_use", "name": n, "input": {"q": 1}}]},
            }
            for n in tool_calls
        ),
        {"type": "assistant", "message": {"content": [{"type": "text", "text": answer}]}},
        {
            "type": "result",
            "subtype": subtype,
            "is_error": is_error,
            "result": answer,
            "num_turns": 1 + len(tool_calls),
            "total_cost_usd": 0.05,
        },
    ]
    return "\n".join(json.dumps(e) for e in events) + "\n"


class FakeClaude:
    """Records each command and answers with a scripted stream."""

    def __init__(self, reply):
        self.reply = reply
        self.calls: list[tuple[list[str], Path, dict | None]] = []

    def __call__(self, cmd, cwd):
        config = None
        if "--mcp-config" in cmd:
            config = json.loads(Path(cmd[cmd.index("--mcp-config") + 1]).read_text())
        self.calls.append((cmd, cwd, config))
        return 0, self.reply(cmd), ""


def test_command_isolates_the_agent():
    cmd = build_command("q", "sonnet", Path("/tmp/c.json"))
    assert cmd[:3] == ["claude", "-p", "q"]
    assert cmd[cmd.index("--tools") + 1] == ""  # no built-in tools: no web search, no files
    assert cmd[cmd.index("--setting-sources") + 1] == ""  # ignore user and project settings
    assert "--strict-mcp-config" in cmd
    assert "--no-session-persistence" in cmd
    assert cmd[cmd.index("--allowedTools") + 1] == "mcp__docs"
    assert cmd[cmd.index("--model") + 1] == "sonnet"


def test_baseline_has_no_mcp_server_at_all():
    cmd = build_command("q", "sonnet", None)
    assert "--mcp-config" not in cmd
    assert "--strict-mcp-config" in cmd  # so the user's own MCP servers can't leak in


def test_parse_stream_reads_answer_tool_calls_and_auth():
    res = parse_stream(stream("use `mount(h)`", tool_calls=["mcp__docs__ask"]).splitlines())
    assert res.text == "use `mount(h)`"
    assert [c["name"] for c in res.tool_calls] == ["mcp__docs__ask"]
    assert (res.model, res.api_key_source, res.num_turns, res.cost_usd) == (
        "claude-sonnet-5",
        "none",
        2,
        0.05,
    )
    assert res.error is None


def test_parse_stream_errors():
    assert parse_stream(["not json", ""]).error == "no result event in output"
    res = parse_stream(stream("Claude usage limit reached. Resets at 5pm.", is_error=True).splitlines())
    assert res.error.startswith("Claude usage limit")
    assert res.hit_limit
    other = parse_stream(stream("", subtype="error_max_turns").splitlines())
    assert other.error == "error_max_turns"
    assert not other.hit_limit


def test_every_setup_gets_the_same_prompt_and_only_its_own_server(tmp_path):
    fake = FakeClaude(lambda cmd: stream("x"))
    for setup in SETUPS:
        ask_agent("How do I X?", setup, "sonnet", tmp_path, runner=fake)
    prompts = {cmd[2] for cmd, _, _ in fake.calls}
    assert prompts == {PROMPT.format(question="How do I X?")}
    configs = {setup: cfg for setup, (_, _, cfg) in zip(SETUPS, fake.calls, strict=True)}
    assert configs["none"] is None
    for setup in ("context7", "deepwiki", "exa"):
        assert configs[setup] == {"mcpServers": {"docs": SETUPS[setup]}}


def test_nonzero_exit_without_result_is_an_error(tmp_path):
    def broken(cmd, cwd):
        return 1, "", "boom"

    res = ask_agent("q", "none", "sonnet", tmp_path, runner=broken)
    assert res.error == "no result event in output"


def test_missing_claude_binary_is_an_error(tmp_path):
    def missing(cmd, cwd):
        raise FileNotFoundError("claude")

    res = ask_agent("q", "none", "sonnet", tmp_path, runner=missing)
    assert res.error.startswith("FileNotFoundError")


def test_run_labels_code_records_tool_use_and_resumes(tmp_path):
    out = tmp_path / "agent.jsonl"
    answers = {
        "deepwiki": "```ts\nimport { mount } from 'hono/mount'\napp.all('/x/*', mount(h))\n```",
        "none": "```ts\napp.mount('/x', h)\n```",
    }

    def reply(cmd):
        config = cmd[cmd.index("--mcp-config") + 1] if "--mcp-config" in cmd else ""
        setup = "deepwiki" if "deepwiki" in config else "none"
        calls = ["mcp__docs__ask_wiki_question"] if setup == "deepwiki" else []
        return stream(answers[setup], tool_calls=calls)

    fake = FakeClaude(reply)
    code = run_agents(QUESTIONS, out, ["none", "deepwiki"], only={"hono-mount"}, pause_s=0, runner=fake)
    assert code == 0
    rows = {r["tool"]: r for r in map(json.loads, out.read_text().splitlines())}
    assert rows["agent-none"]["label"] == "stale"
    assert rows["agent-deepwiki"]["label"] == "current"
    assert rows["agent-deepwiki"]["meta"]["tool_calls"] == ["mcp__docs__ask_wiki_question"]
    assert rows["agent-none"]["meta"]["auth"] == "none"
    assert (tmp_path / "raw" / "hono-mount.agent-deepwiki.plain.1.txt").exists()

    run_agents(QUESTIONS, out, ["none", "deepwiki"], only={"hono-mount"}, pause_s=0, runner=fake)
    assert len(fake.calls) == 2  # second run had nothing left to do


def test_run_stops_at_usage_limit_without_recording_it(tmp_path):
    out = tmp_path / "agent.jsonl"
    fake = FakeClaude(lambda cmd: stream("Claude usage limit reached", is_error=True))
    code = run_agents(QUESTIONS, out, ["none"], only={"hono-mount", "polars-cut"}, pause_s=0, runner=fake)
    assert code == 3
    assert len(fake.calls) == 1
    assert out.read_text() == ""
