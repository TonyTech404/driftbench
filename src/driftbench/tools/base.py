"""What every documentation tool adapter returns."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from ..questions import Question


@dataclass
class ToolResponse:
    text: str  # exactly what an agent would read
    ms: int = 0
    meta: dict = field(default_factory=dict)  # e.g. which library id the tool resolved
    error: str | None = None


class Tool:
    name: str = ""

    def available(self) -> tuple[bool, str]:
        """(usable, reason). Tools that need a missing API key are skipped, not failed."""
        return True, ""

    def ask(self, q: Question, query: str, variant: str) -> ToolResponse:
        raise NotImplementedError


def timed(fn: Callable[[], ToolResponse]) -> ToolResponse:
    start = time.perf_counter()
    try:
        resp = fn()
    except Exception as e:  # a failing tool is a result, not a crash
        resp = ToolResponse(text="", error=f"{type(e).__name__}: {e}")
    resp.ms = round((time.perf_counter() - start) * 1000)
    return resp
