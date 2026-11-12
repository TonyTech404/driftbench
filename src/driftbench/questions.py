"""Question format and loading."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

REQUIRED = (
    "id",
    "library",
    "repo",
    "version",
    "release_date",
    "old_api",
    "new_api",
    "old_patterns",
    "new_patterns",
    "question",
    "question_with_version",
    "source_url",
)


@dataclass(frozen=True)
class Question:
    id: str
    library: str
    repo: str
    version: str
    release_date: str
    old_api: str
    new_api: str
    old_patterns: tuple[str, ...]
    new_patterns: tuple[str, ...]
    question: str
    question_with_version: str
    source_url: str
    ecosystem: str = ""
    change: str = ""
    notes: str = ""
    _old: tuple[re.Pattern[str], ...] = field(default=(), repr=False, compare=False)
    _new: tuple[re.Pattern[str], ...] = field(default=(), repr=False, compare=False)

    @classmethod
    def from_dict(cls, d: dict) -> Question:
        missing = [k for k in REQUIRED if not d.get(k)]
        if missing:
            raise ValueError(f"question {d.get('id', '?')}: missing {', '.join(missing)}")
        old = tuple(d["old_patterns"])
        new = tuple(d["new_patterns"])
        return cls(
            id=d["id"],
            library=d["library"],
            repo=d["repo"],
            version=d["version"],
            release_date=d["release_date"],
            old_api=d["old_api"],
            new_api=d["new_api"],
            old_patterns=old,
            new_patterns=new,
            question=d["question"],
            question_with_version=d["question_with_version"],
            source_url=d["source_url"],
            ecosystem=d.get("ecosystem", ""),
            change=d.get("change", ""),
            notes=d.get("notes", ""),
            _old=tuple(re.compile(p) for p in old),
            _new=tuple(re.compile(p) for p in new),
        )

    def text(self, variant: str) -> str:
        if variant == "plain":
            return self.question
        if variant == "versioned":
            return self.question_with_version
        raise ValueError(f"unknown variant {variant!r}")


def load_questions(path: Path) -> list[Question]:
    data = json.loads(Path(path).read_text())
    questions = [Question.from_dict(d) for d in data]
    ids = [q.id for q in questions]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate question ids: {', '.join(sorted(dupes))}")
    return questions
