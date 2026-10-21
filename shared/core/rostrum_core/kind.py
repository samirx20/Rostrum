"""A document kind: what one app tells rostrum_core about its documents. That small table, plus the app's
operations, is all the shared code needs (OPERATIONS.md § 9)."""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Callable

from .registry import Registry
from .tree import View


def _no_problems(data) -> list[str]:
    return []


def _no_facts(item, doc) -> dict:
    return {}


@dataclass
class DocKind:
    name: str                                   # "toy", "2d", "sound" … (the file's format is "rostrum-<name>")
    ext: str                                    # ".toy", ".mtn" …
    registry: Registry
    lists: dict = field(default_factory=lambda: {"doc": ["items"]})   # item type -> keys holding child items
    version: int = 1
    check: Callable[[dict], list[str]] = _no_problems   # whole-document check, run after every call
    # Facts about an item, for valid_when {"fact": …}: the app writes facts(item, doc), where doc is a View
    # (doc.parent(item), doc.item(id)), so a child can be valid by its parent (a note by its track's instrument).
    # A one-argument facts(item) still works.
    facts: Callable = _no_facts
    new: Callable[[], dict] | None = None               # a fresh document's root

    def __post_init__(self):
        app_facts = self.facts
        takes_doc = len(inspect.signature(app_facts).parameters) >= 2

        def facts(item: dict, doc=None) -> dict:
            """doc: a Document, a document's data dict, a View, or None (no parent facts)."""
            if not takes_doc:
                return app_facts(item)
            return app_facts(item, self.view(doc) if doc is not None else None)
        self.facts = facts

    def view(self, doc) -> View:
        if isinstance(doc, View):
            return doc
        return View(doc if isinstance(doc, dict) else doc.data, self.lists)

    def blank(self) -> dict:
        if self.new:
            return self.new()
        return {"id": "root", "type": "doc", **{k: [] for k in self.lists.get("doc", [])}}

    @property
    def format(self) -> str:
        return f"rostrum-{self.name}"
