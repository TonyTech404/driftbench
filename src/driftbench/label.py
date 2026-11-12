"""Label a tool's response by which API it shows: the current one, the outdated one, both or neither.

Three views of one response:
- code:  the fenced code blocks, which is what an agent copies. This is the headline metric.
         Prose such as "`app.mount()` is deprecated, use `mount()`" is a good answer, so
         mentioning the old API outside code must not count against a tool.
- first: the first code block that shows either API, which is the one an agent most likely uses.
- text:  the whole response, for reference.
If a response has no fenced code, the code and first views fall back to inline code spans.

Code that tells the reader to stop using the old API doesn't count as recommending it, so the
code and first views drop: removed lines in diff blocks (`- old()`), lines marked `[!code --]`
(VitePress diffs), and lines that call the API deprecated, removed or replaced.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .questions import Question

CURRENT = "current"  # only the new API
MIXED = "mixed"  # both: the reader has to guess which one is right
STALE = "stale"  # only the outdated API
NEITHER = "neither"  # neither API appears
ERROR = "error"  # the tool failed

LABELS = (CURRENT, MIXED, STALE, NEITHER, ERROR)

_FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})([^\n]*)\n(.*?)^[ \t]*\1[ \t]*$", re.M | re.S)
_INLINE = re.compile(r"`([^`\n]+)`")
_REMOVAL_NOTE = re.compile(
    r"deprecat|\bremoved\b|\bno longer\b|\bobsolete\b|\binstead\b|in favou?r of|replaced (?:by|with)|"
    r"\[!code --\]",
    re.I,
)


@dataclass(frozen=True)
class Label:
    label: str
    old_hits: tuple[str, ...]
    new_hits: tuple[str, ...]


@dataclass(frozen=True)
class Labels:
    code: Label
    first: Label
    text: Label


def label_text(q: Question, text: str) -> Label:
    old_hits = tuple(m.group(0) for p in q._old if (m := p.search(text)))
    new_hits = tuple(m.group(0) for p in q._new if (m := p.search(text)))
    if old_hits and new_hits:
        label = MIXED
    elif new_hits:
        label = CURRENT
    elif old_hits:
        label = STALE
    else:
        label = NEITHER
    return Label(label, old_hits, new_hits)


def code_blocks(text: str) -> list[str]:
    blocks = [m.group(3) for m in _FENCE.finditer(text)]
    return blocks or _INLINE.findall(text)


def recommended_code(text: str) -> list[str]:
    """Code blocks minus the lines that show what to stop using."""
    fenced = list(_FENCE.finditer(text))
    raw = [(m.group(2).strip().lower(), m.group(3)) for m in fenced] or [
        ("", s) for s in _INLINE.findall(text)
    ]
    blocks = []
    for info, body in raw:
        is_diff = info.startswith("diff")
        kept = []
        for line in body.splitlines():
            if is_diff and line.startswith("-"):
                continue
            if _REMOVAL_NOTE.search(line):
                continue
            kept.append(line[1:] if is_diff and line.startswith("+") else line)
        blocks.append("\n".join(kept))
    return blocks


def label_response(q: Question, text: str) -> Labels:
    blocks = recommended_code(text)
    first = next(
        (lab for b in blocks if (lab := label_text(q, b)).label != NEITHER),
        Label(NEITHER, (), ()),
    )
    return Labels(code=label_text(q, "\n".join(blocks)), first=first, text=label_text(q, text))
