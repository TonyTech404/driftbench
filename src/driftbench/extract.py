"""Find candidate API changes (renames, deprecations, replacements) in release notes.

Match sentences that name both APIs in backticks and fenced import migrations.
Every candidate still needs review before it becomes a question.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

CODE = r"`(?P<{name}>[^`\n]{{2,80}})`"
OLD = CODE.format(name="old")
NEW = CODE.format(name="new")
CONTEXT = CODE.format(name="context")
PARAMETER = rf"{OLD}\s+parameter\s+(?:in|of)\s+{CONTEXT}"

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
    (
        "deprecation",
        re.compile(
            rf"{PARAMETER}\s+is\s+deprecated\.\s+"
            rf"(?:use|configure\s+[^.`]{{1,60}}\s+with)\s+{NEW}\s+instead\b",
            re.I,
        ),
    ),
    (
        "deprecation",
        re.compile(
            rf"\bdeprecate[sd]?\s+(?:the\s+)?{PARAMETER},\s+replace\s+with\s+(?:new\s+)?{NEW}",
            re.I,
        ),
    ),
]

PROPERTY = r"`[A-Za-z_]\w*`"
PROPERTIES = rf"{PROPERTY}(?:\s*/\s*{PROPERTY})*"
PROPERTY_CHANGE = re.compile(
    rf"\bnow\s+exposes\s+(?P<new>{PROPERTIES})\s+properties\s+"
    rf"\((?P<old>{PROPERTIES})\s+are\s+deprecated\)",
    re.I,
)
DIFF_BLOCK = re.compile(r"^[ \t]*```diff[ \t]*\n(?P<body>.*?)^[ \t]*```[ \t]*$", re.M | re.S)
IMPORT_PAIR = re.compile(
    r"^[ \t]*-[ \t]*(?P<old>(?P<binding>import[ \t]+[^'\"\n]{1,80}?[ \t]+from)[ \t]+"
    r"(?P<old_quote>['\"])(?P<old_module>[^'\"\n]{1,80})(?P=old_quote);?)[ \t]*\n"
    r"[ \t]*\+[ \t]*(?P<new>(?P=binding)[ \t]+"
    r"(?P<new_quote>['\"])(?P<new_module>[^'\"\n]{1,80})(?P=new_quote);?)[ \t]*$",
    re.M,
)

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


def _candidate_matches(text: str):
    for line in text.splitlines():
        line = line.strip()
        if "`" not in line:
            continue
        for kind, pat in PATTERNS:
            for match in pat.finditer(line):
                old = _clean(match["old"])
                context = match.groupdict().get("context")
                if context:
                    old = f"{old} in {_clean(context)}"
                yield kind, old, _clean(match["new"]), line
        for match in PROPERTY_CHANGE.finditer(line):
            old = re.findall(PROPERTY, match["old"])
            new = re.findall(PROPERTY, match["new"])
            if len(old) == len(new):
                for previous, current in zip(old, new, strict=True):
                    yield "deprecation", _clean(previous), _clean(current), line

    for block in DIFF_BLOCK.finditer(text.replace("\r\n", "\n")):
        for match in IMPORT_PAIR.finditer(block["body"]):
            if match["old_module"] != match["new_module"]:
                yield "replacement", match["old"], match["new"], match[0].strip()


def extract_from_text(text: str) -> list[tuple[str, str, str, str]]:
    """Return (kind, old, new, excerpt) for every distinct matching API pair."""
    found: list[tuple[str, str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for kind, old, new, excerpt in _candidate_matches(text):
        if old == new or _NOT_API.match(old) or _NOT_API.match(new) or (old, new) in seen:
            continue
        seen.add((old, new))
        found.append((kind, old, new, excerpt[:400]))
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
