"""Ask every tool every question (plain and with a version) and record labeled results.

Results are appended to a JSONL file, one row per (question, tool, variant, run), and a rerun
skips rows that already succeeded, so an interrupted run resumes where it stopped. Raw tool
output goes to results/raw/, which is not committed, because it contains other sites' content.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from .label import ERROR, label_response
from .questions import Question, load_questions
from .tools import REGISTRY

VARIANTS = ("plain", "versioned")
PAUSE_S = 1.0  # be polite to free endpoints


def raw_path(results_path: Path, question_id: str, tool: str, variant: str, run: int) -> Path:
    return results_path.parent / "raw" / f"{question_id}.{tool}.{variant}.{run}.txt"


def write_raw(path: Path, text: str) -> None:
    """Save a tool's output byte for byte; web pages often contain \\r, which text mode would alter."""
    path.write_bytes(text.encode())


def read_raw(path: Path) -> str:
    return path.read_bytes().decode()


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def label_fields(q: Question, text: str, error: str | None) -> dict:
    labs = label_response(q, text)
    return {
        "label": ERROR if error else labs.code.label,
        "first_label": ERROR if error else labs.first.label,
        "text_label": ERROR if error else labs.text.label,
        "old_hits": list(labs.code.old_hits),
        "new_hits": list(labs.code.new_hits),
    }


def done_keys(results_path: Path) -> set[tuple[str, str, str, int]]:
    done = set()
    if results_path.exists():
        for line in results_path.read_text().splitlines():
            r = json.loads(line)
            if r["label"] != ERROR:
                done.add((r["question_id"], r["tool"], r["variant"], r["run"]))
    return done


def run(
    questions_path: Path,
    results_path: Path,
    tools: list[str] | None = None,
    only: set[str] | None = None,
    runs: int = 1,
) -> int:
    questions = [q for q in load_questions(questions_path) if not only or q.id in only]
    names = tools or list(REGISTRY)
    unknown = [n for n in names if n not in REGISTRY]
    if unknown:
        print(f"unknown tools: {', '.join(unknown)}; known: {', '.join(REGISTRY)}", file=sys.stderr)
        return 2

    active = []
    for n in names:
        tool = REGISTRY[n]()
        ok, why = tool.available()
        if ok:
            active.append(tool)
        else:
            print(f"skipping {n}: {why}", file=sys.stderr)

    (results_path.parent / "raw").mkdir(parents=True, exist_ok=True)
    done = done_keys(results_path)

    with results_path.open("a") as out:
        for q in questions:
            for tool in active:
                for variant in VARIANTS:
                    for i in range(1, runs + 1):
                        if (q.id, tool.name, variant, i) in done:
                            continue
                        resp = tool.ask(q, q.text(variant), variant)
                        write_raw(raw_path(results_path, q.id, tool.name, variant, i), resp.text)
                        row = {
                            "question_id": q.id,
                            "tool": tool.name,
                            "variant": variant,
                            "run": i,
                            **label_fields(q, resp.text, resp.error),
                            "ms": resp.ms,
                            "chars": len(resp.text),
                            "sha256_16": digest(resp.text),
                            "meta": resp.meta,
                            "error": resp.error,
                            "at": datetime.now(UTC).isoformat(timespec="seconds"),
                        }
                        out.write(json.dumps(row) + "\n")
                        out.flush()
                        print(
                            f"{q.id:36} {tool.name:9} {variant:9} {row['label']:8} {resp.ms:6} ms",
                            file=sys.stderr,
                        )
                        time.sleep(PAUSE_S)
    return 0


def relabel(questions_path: Path, results_path: Path) -> int:
    """Recompute labels from saved raw output, so labeling fixes don't need new tool calls."""
    questions = {q.id: q for q in load_questions(questions_path)}
    rows, changed, skipped = [], 0, 0
    for line in results_path.read_text().splitlines():
        r = json.loads(line)
        rows.append(r)
        q = questions.get(r["question_id"])
        if q is None or r["label"] == ERROR:
            continue
        raw = raw_path(results_path, r["question_id"], r["tool"], r["variant"], r["run"])
        if not raw.exists():
            skipped += 1
            continue
        text = read_raw(raw)
        if digest(text) != r["sha256_16"]:
            print(f"raw output changed since the run, skipping {raw.name}", file=sys.stderr)
            skipped += 1
            continue
        new = label_fields(q, text, None)
        if any(r.get(k) != v for k, v in new.items()):
            changed += 1
            print(
                f"{r['question_id']:36} {r['tool']:9} {r['variant']:9} {r['label']} -> {new['label']}",
                file=sys.stderr,
            )
            r.update(new)
    results_path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(f"{changed} rows changed, {skipped} skipped (no matching raw output)", file=sys.stderr)
    return 0
