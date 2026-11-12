"""Turn results.jsonl into a Markdown report."""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from .label import CURRENT, ERROR, LABELS, MIXED, NEITHER, STALE
from .questions import load_questions

SYMBOL = {CURRENT: "✅", MIXED: "⚠️", STALE: "❌", NEITHER: "·", ERROR: "💥"}


def _latest(rows: list[dict]) -> list[dict]:
    """Keep the last row per (question, tool, variant, run), so a retried error is replaced."""
    keep: dict[tuple, dict] = {}
    for r in rows:
        keep[(r["question_id"], r["tool"], r["variant"], r["run"])] = r
    return list(keep.values())


def _pct(n: int, d: int) -> str:
    return f"{n}/{d} ({100 * n / d:.0f}%)" if d else "0/0"


def build_report(questions_path: Path, results_path: Path) -> str:
    questions = load_questions(questions_path)
    qids = {q.id for q in questions}
    rows = [
        r
        for r in _latest([json.loads(x) for x in Path(results_path).read_text().splitlines()])
        if r["question_id"] in qids
    ]
    tools = sorted({r["tool"] for r in rows})
    lines = [
        "# driftbench results",
        "",
        f"{len(questions)} questions about API changes released in 2026, "
        f"{len({q.library for q in questions})} libraries.",
        "",
        "Labels are based on the **code** in each response, which is what an agent copies: "
        "**current** = only the new API, **mixed** = both old and new, "
        "**stale** = only the outdated API, **neither** = neither appears. "
        "**First snippet stale** counts responses whose first relevant code block uses the "
        "outdated API.",
        "",
    ]

    # Agent rows record their tool calls, so their tables also show how often the tool was used.
    agent_mode = any("tool_calls" in (r.get("meta") or {}) for r in rows)
    variants = (("plain", "Question without a version"), ("versioned", "Question names the version"))
    for variant, title in variants:
        if not any(r["variant"] == variant for r in rows):
            continue
        columns = ["Tool", "Current", "Mixed", "Stale", "Neither", "Errors", "First snippet stale"]
        columns += ["Used its tool"] if agent_mode else []
        columns += ["Median latency"]
        lines += [
            f"## {title}",
            "",
            "| " + " | ".join(columns) + " |",
            "|" + " --- |" * len(columns),
        ]
        for t in tools:
            rs = [r for r in rows if r["tool"] == t and r["variant"] == variant]
            c = Counter(r["label"] for r in rs)
            first_stale = sum(r.get("first_label") == STALE for r in rs)
            ok = [r["ms"] for r in rs if r["label"] != ERROR]
            med = f"{statistics.median(ok) / 1000:.1f} s" if ok else "–"
            used = ""
            if agent_mode:
                if t == "agent-none":
                    used = " – |"
                else:
                    n = sum(bool((r.get("meta") or {}).get("tool_calls")) for r in rs)
                    used = f" {_pct(n, len(rs))} |"
            lines.append(
                f"| {t} | {_pct(c[CURRENT], len(rs))} | {_pct(c[MIXED], len(rs))} | "
                f"{_pct(c[STALE], len(rs))} | {_pct(c[NEITHER], len(rs))} | {c[ERROR]} | "
                f"{_pct(first_stale, len(rs))} |{used} {med} |"
            )
        lines.append("")

    legend = ", ".join(f"{SYMBOL[name]} {name}" for name in LABELS)
    lines += ["## Per question", "", f"Plain / versioned. {legend}", ""]
    header = "| Question | Library | Released | " + " | ".join(tools) + " |"
    lines += [header, "| --- | --- | --- | " + " | ".join("---" for _ in tools) + " |"]
    by_key: dict[tuple, list[str]] = defaultdict(list)
    for r in sorted(rows, key=lambda r: r["run"]):
        by_key[(r["question_id"], r["tool"], r["variant"])].append(SYMBOL[r["label"]])
    for q in questions:
        cells = []
        for t in tools:
            plain = "".join(by_key.get((q.id, t, "plain"), ["–"]))
            ver = "".join(by_key.get((q.id, t, "versioned"), ["–"]))
            cells.append(f"{plain} / {ver}")
        lines.append(
            f"| [{q.id}]({q.source_url}) | {q.library} {q.version} | {q.release_date} | "
            + " | ".join(cells)
            + " |"
        )
    lines.append("")
    return "\n".join(lines)
