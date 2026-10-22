"""A document kind: what one app tells rostrum_core about its documents. That small table, plus the app's
operations, is all the shared code needs (OPERATIONS.md § 9)."""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Callable

from .errors import RostrumError
from .registry import Registry
from .tree import View, fields, walk

SHAPE_ERRORS = (KeyError, TypeError, ValueError, AttributeError, IndexError)   # an app check reading a wrong shape


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
    # The app's check, run after every call: check(data), or check(data, items=None) to be handed the items a call
    # changed (None: look at everything, as on open) so a big document isn't walked whole per change.
    check: Callable[..., list[str]] = _no_problems
    # Facts about an item, for valid_when {"fact": …}: the app writes facts(item, doc), where doc is a View
    # (doc.parent(item), doc.item(id)), so a child can be valid by its parent (a note by its track's instrument).
    # A one-argument facts(item) still works.
    facts: Callable = _no_facts
    new: Callable[[], dict] | None = None               # a fresh document's root

    def __post_init__(self):
        app_check = self.check
        if len(inspect.signature(app_check).parameters) < 2:
            self.check = lambda data, items=None: app_check(data)
        app_facts = self.facts
        takes_doc = len(inspect.signature(app_facts).parameters) >= 2

        def facts(item: dict, doc=None) -> dict:
            """doc: a Document, a document's data dict, a View, or None (no parent facts)."""
            if not takes_doc:
                return app_facts(item)
            return app_facts(item, self.view(doc) if doc is not None else None)
        self.facts = facts

    def bad_values(self, items):
        """Each stored field value its kind's own field op refuses (range, kind of value, choices): the same rule
        operation arguments obey, so no field of any kind can hold what its control could never set (a frame rate
        of 0). Yields RostrumErrors."""
        for item in items:
            op = self.registry.field_op(item.get("type"))
            for name, value in (fields(item, self.lists).items() if op else ()):
                p = op.param(name)
                if p is None:
                    continue
                try:
                    p.check(value, f'{item.get("type")} "{item.get("id")}"')
                except RostrumError as e:
                    yield e

    def problems(self, data: dict, items=None) -> list[str]:
        """The whole-document check: every field value (or only `items`', the ones a call changed) against its
        field's own data, then the app's own check. Run after every call and on every open."""
        try:
            out = [f"{e.where}: {e.subject} {e.problem}" + (f" ({', '.join(e.accepted)})" if e.accepted else "")
                   for e in self.bad_values(walk(data, self.lists) if items is None else items)]
            return out + list(self.check(data, items))
        except SHAPE_ERRORS as e:
            return [f"{type(e).__name__}: {e}"]

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
