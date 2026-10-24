"""A document kind: what one app tells rostrum_core about its documents. That small table, plus the app's
operations, is all the shared code needs (OPERATIONS.md § 9)."""
from __future__ import annotations

import copy
import inspect
from dataclasses import dataclass, field
from typing import Callable

from .errors import RostrumError, codes
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
    # One small data-only step per format change: migrations[n](data, lists) -> (data, label) takes a document saved as
    # format n to format n+1 (it may change `data` in place; a file is migrated on a copy). A step that needs the
    # project around the document (2D: the shared markers its cameras were timed on) takes a third argument, `folder`
    # (None without a project), as `upgrade` does. Run oldest first on open,
    # before the document is checked, so a file written by any earlier build opens. Every format below `version` must
    # have its step: raising `version` without one is refused here, so a format change can't ship without it.
    migrations: dict[int, Callable[[dict, dict], tuple[dict, str]]] = field(default_factory=dict)
    # The app's check, run after every call: check(data), or check(data, items=None) to be handed the items a call
    # changed (None: look at everything, as on open) so a big document isn't walked whole per change.
    check: Callable[..., list[str]] = _no_problems
    # Facts about an item, for valid_when {"fact": …}: the app writes facts(item, doc), where doc is a View
    # (doc.parent(item), doc.item(id)), so a child can be valid by its parent (a note by its track's instrument).
    # A one-argument facts(item) still works.
    facts: Callable = _no_facts
    # The app's warnings: warn(data) -> plain sentences about what the file may hold but Rostrum no longer makes (a
    # retired design). Unlike `check`, they never stop a file opening or a call; they are never silent either: the
    # agent's replies carry them (mcp/server.py), inspect lists them, screens show them on the Problems chip.
    warn: Callable[[dict], list[str]] = _no_problems
    new: Callable[[], dict] | None = None               # a fresh document's root
    # The app's upgrade: upgrade(data, lists[, folder]) -> (new data, label) for what an older file holds that Rostrum
    # now holds another way (2D: a gradient effect becomes the fill; Sound: absolute takes become project-relative,
    # which needs the project `folder`, None without one), or None. Run once on open (storage.open_doc), after `migrations` and before the check, and
    # recorded as one change, so the history before it replays as written and undo takes it back.
    upgrade: Callable | None = None
    # The app's tidy: tidy(calls, folder) -> calls, run on every call list before it is checked (Sound: a full path typed
    # inside the song's folder is stored as a place in it). Only the way a value is written changes, never its meaning.
    tidy: Callable | None = None

    def __post_init__(self):
        missing = [n for n in range(1, self.version) if n not in self.migrations]
        if missing:
            raise ValueError(f"DocKind {self.name!r}: format {self.version} needs an upgrade step (migrations) for "
                             f"format {', '.join(map(str, missing))}")
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
        self.migrations = {n: (step if len(inspect.signature(step).parameters) >= 3
                               else (lambda data, lists, folder=None, _s=step: _s(data, lists)))
                           for n, step in self.migrations.items()}
        app_up = self.upgrade
        if app_up is not None and len(inspect.signature(app_up).parameters) < 3:
            self.upgrade = lambda data, lists, folder=None: app_up(data, lists)

    def migrate(self, data: dict, from_version: int, folder=None) -> tuple[dict, list[str]]:
        """`data` (a document saved as format `from_version`) brought to this format, one step after another, on a
        copy: (new data, the steps' labels). A file of the current format comes back as it is, with no labels.
        `folder`: the project folder, for a step that reads the project (None without one)."""
        labels = []
        if from_version < self.version:
            data = copy.deepcopy(data)
            for n in range(from_version, self.version):
                data, label = self.migrations[n](data, self.lists, folder)
                labels.append(label)
        return data, labels

    def bad_values(self, items):
        """Each stored field value its kind's own field op refuses (range, kind of value, choices): the same rule
        operation arguments obey, so no field of any kind can hold what its control could never set (a frame rate
        of 0). Yields RostrumErrors."""
        for item in items:
            op = self.registry.field_op(item.get("type"))
            for name, value in (fields(item, self.lists).items() if op else ()):
                p = op.param(name)
                if p is None or value in getattr(p, "kept", ()):   # a kept choice: an old file's, still read
                    continue
                where = f'{item.get("type")} "{item.get("id")}"'
                try:
                    stored = p.check(value, where)
                except RostrumError as e:
                    yield e
                    continue
                if stored != value:     # checks take forms people write ("#fff"); a file holds only the stored one
                    yield RostrumError(codes.BAD_ARGUMENT, where, f"{name}={value!r}", "is not written as stored", [repr(stored)])

    def problems(self, data: dict, items=None) -> list[str]:
        """The whole-document check: every field value (or only `items`', the ones a call changed) against its
        field's own data, then the app's own check. Run after every call and on every open."""
        try:
            out = [f"{e.where}: {e.subject} {e.problem}" + (f" ({', '.join(e.accepted)})" if e.accepted else "")
                   for e in self.bad_values(walk(data, self.lists) if items is None else items)]
            return out + list(self.check(data, items))
        except SHAPE_ERRORS as e:
            return [f"{type(e).__name__}: {e}"]

    def warnings(self, data: dict) -> list[str]:
        """What the document holds that still opens but is no longer made (`warn`), in words."""
        try:
            return list(self.warn(data))
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
