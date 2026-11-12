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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="driftbench", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("candidates", help="extract candidate API changes from GitHub release notes")
    c.add_argument("--libraries", default="data/libraries.json")
    c.add_argument("--since", required=True, help="ISO date, e.g. 2026-06-01")
    c.add_argument("--out", default="data/candidates.jsonl")
    c.set_defaults(func=cmd_candidates)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
