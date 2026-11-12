"""driftbench command line."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


def cmd_candidates(args: argparse.Namespace) -> int:
    from .extract import extract_from_release
    from .sources import fetch_releases, make_client

    libraries = json.loads(Path(args.libraries).read_text())
    since = datetime.fromisoformat(args.since).replace(tzinfo=UTC)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with make_client() as client, out.open("w") as f:
        for lib in libraries:
            releases = fetch_releases(lib["repo"], since, client)
            n = 0
            for release in releases:
                for cand in extract_from_release(release):
                    f.write(json.dumps({"library": lib["name"], **cand.to_dict()}) + "\n")
                    n += 1
            total += n
            print(f"{lib['repo']:32} {len(releases):3} releases  {n:3} candidates", file=sys.stderr)
    print(f"wrote {total} candidates to {out}", file=sys.stderr)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    from .run import run

    return run(
        questions_path=Path(args.questions),
        results_path=Path(args.out),
        tools=args.tools.split(",") if args.tools else None,
        only=set(args.only.split(",")) if args.only else None,
        runs=args.runs,
    )


def cmd_agent(args: argparse.Namespace) -> int:
    from .agent import SETUPS, run_agents

    return run_agents(
        questions_path=Path(args.questions),
        results_path=Path(args.out),
        setups=args.setups.split(",") if args.setups else list(SETUPS),
        model=args.model,
        only=set(args.only.split(",")) if args.only else None,
        variants=tuple(args.variants.split(",")),
        pause_s=args.pause,
    )


def cmd_relabel(args: argparse.Namespace) -> int:
    from .run import relabel

    return relabel(Path(args.questions), Path(args.results))


def cmd_report(args: argparse.Namespace) -> int:
    from .report import build_report

    text = build_report(Path(args.questions), Path(args.results))
    if args.out:
        Path(args.out).write_text(text)
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(text)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="driftbench", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("candidates", help="extract candidate API changes from GitHub release notes")
    c.add_argument("--libraries", default="data/libraries.json")
    c.add_argument("--since", required=True, help="ISO date, e.g. 2026-06-01")
    c.add_argument("--out", default="data/candidates.jsonl")
    c.set_defaults(func=cmd_candidates)

    r = sub.add_parser("run", help="ask every tool every question and label the answers")
    r.add_argument("--questions", required=True)
    r.add_argument("--out", default="results/results.jsonl")
    r.add_argument("--tools", help="comma-separated tool names (default: all available)")
    r.add_argument("--only", help="comma-separated question ids")
    r.add_argument("--runs", type=int, default=1)
    r.set_defaults(func=cmd_run)

    a = sub.add_parser(
        "agent", help="give a coding agent (Claude Code) each tool and label the code it writes"
    )
    a.add_argument("--questions", required=True)
    a.add_argument("--out", default="results/agent.jsonl")
    a.add_argument("--setups", help="comma-separated: none,context7,deepwiki,exa (default: all)")
    a.add_argument("--model", default="sonnet", help="model passed to claude --model")
    a.add_argument("--only", help="comma-separated question ids")
    a.add_argument("--variants", default="plain", help="plain, versioned, or both comma-separated")
    a.add_argument("--pause", type=float, default=2.0, help="seconds between runs")
    a.set_defaults(func=cmd_agent)

    rl = sub.add_parser("relabel", help="recompute labels from saved raw output")
    rl.add_argument("--questions", required=True)
    rl.add_argument("--results", default="results/results.jsonl")
    rl.set_defaults(func=cmd_relabel)

    rep = sub.add_parser("report", help="summarize results as a Markdown report")
    rep.add_argument("--questions", required=True)
    rep.add_argument("--results", default="results/results.jsonl")
    rep.add_argument("--out")
    rep.set_defaults(func=cmd_report)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
