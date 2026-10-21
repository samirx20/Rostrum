"""A document kind: what one app tells rostrum_core about its documents. That small table, plus the app's
operations, is all the shared code needs (OPERATIONS.md § 9)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .registry import Registry


def _no_problems(data) -> list[str]:
    return []


def _no_facts(item) -> dict:
    return {}


@dataclass
class DocKind:
    name: str                                   # "toy", "2d", "sound" … (the file's format is "rostrum-<name>")
    ext: str                                    # ".toy", ".mtn" …
    registry: Registry
    lists: dict = field(default_factory=lambda: {"doc": ["items"]})   # item type -> keys holding child items
    version: int = 1
    check: Callable[[dict], list[str]] = _no_problems   # whole-document check, run after every call
    facts: Callable[[dict], dict] = _no_facts            # facts about an item, for valid_when {"fact": …}
    new: Callable[[], dict] | None = None               # a fresh document's root

    def blank(self) -> dict:
        if self.new:
            return self.new()
        return {"id": "root", "type": "doc", **{k: [] for k in self.lists.get("doc", [])}}

    @property
    def format(self) -> str:
        return f"rostrum-{self.name}"
