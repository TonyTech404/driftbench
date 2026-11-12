"""Find candidate API changes (renames, deprecations, replacements) in release notes.

This is deliberately simple: it only matches sentences that name both the old and the new
API in backticks. Every candidate still needs a human (or model) review before it becomes
a question, because release notes also rename internal things nobody calls.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

CODE = r"`(?P<{name}>[^`\n]{{2,80}})`"
OLD = CODE.format(name="old")
NEW = CODE.format(name="new")

# Each pattern must capture `old` and `new`. Order matters only for readability.
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("rename", re.compile(rf"{OLD}[^.\n`]{{0,40}}?\b(?:renamed|moved)\s+to\s+{NEW}", re.I)),
    ("rename", re.compile(rf"\brename[sd]?\s+{OLD}\s+(?:to|as|into)\s+{NEW}", re.I)),
    (
        "deprecation",
        re.compile(
            rf"\bdeprecat\w*\s+(?:the\s+)?{OLD}[^\n`]{{0,60}}?"
            rf"(?:in\s+favou?r\s+of|use|replaced\s+by|superseded\s+by)\s+(?:the\s+)?{NEW}",
            re.I,
        ),
    ),
    (
        "deprecation",
        re.compile(
            rf"{OLD}[^\n`]{{0,30}}?\b(?:is|are|has\s+been|have\s+been|now)\s+deprecated[^\n`]{{0,60}}?"
            rf"(?:in\s+favou?r\s+of|use|replaced\s+by|superseded\s+by)\s+(?:the\s+)?{NEW}",
            re.I,
        ),
    ),
    ("replacement", re.compile(rf"\breplace[sd]?\s+{OLD}\s+with\s+{NEW}", re.I)),
    ("replacement", re.compile(rf"\buse\s+{NEW}\s+instead\s+of\s+{OLD}", re.I)),
]

# Things in backticks that are not APIs: versions, commit hashes, file globs, flags-only noise.
_NOT_API = re.compile(r"^(v?\d+(\.\d+)*|[0-9a-f]{7,40}|\*+|-+)$")


@dataclass(frozen=True)
class Candidate:
    repo: str
    tag: str
    published_at: str
    release_url: str
    kind: str
    old_api: str
    new_api: str
    excerpt: str

    def to_dict(self) -> dict:
        return asdict(self)


def _clean(token: str) -> str:
    return token.strip().strip("`").strip()


def extract_from_text(text: str) -> list[tuple[str, str, str, str]]:
    """Return (kind, old, new, excerpt) for every match, one excerpt per source line."""
    found: list[tuple[str, str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for line in text.splitlines():
        line = line.strip()
        if "`" not in line:
            continue
        for kind, pat in PATTERNS:
            for m in pat.finditer(line):
                old, new = _clean(m.group("old")), _clean(m.group("new"))
                if old == new or _NOT_API.match(old) or _NOT_API.match(new):
                    continue
                if (old, new) in seen:
                    continue
                seen.add((old, new))
                found.append((kind, old, new, line[:400]))
    return found


def extract_from_release(release: dict) -> list[Candidate]:
    return [
        Candidate(
            repo=release["repo"],
            tag=release["tag"],
            published_at=release["published_at"],
            release_url=release["url"],
            kind=kind,
            old_api=old,
            new_api=new,
            excerpt=excerpt,
        )
        for kind, old, new, excerpt in extract_from_text(release["body"])
    ]
