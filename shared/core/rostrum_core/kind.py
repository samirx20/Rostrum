"""A document kind: what one app tells rostrum_core about its documents. That small table, plus the app's
operations, is all the shared code needs (OPERATIONS.md § 9)."""
from __future__ import annotations

import copy
import inspect
from dataclasses import dataclass, field
from typing import Callable

from . import field_values
from .registry import Registry
from .tree import View, walk

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
    # upgraded(label) -> (from, to) or None: the formats an upgrade step written before steps carried their `format`
    # took the document between, read from its label (formats.py). Only for histories written before 2026-10-26.
    upgraded: Callable[[str], tuple[int, int] | None] | None = None
    # The app's check, run after every call: check(data), or check(data, items=None) to be handed the items a call
    # changed (None: look at everything, as on open) so a big document isn't walked whole per change, or
    # check(data, items=None, only=None) also told which of their fields it changed (run.set_fields: a field only a
    # Shift moved holds a number moved, so a rule about its form or its references needn't ask it again),
    # or with a keyword `idx` (check(data, items=None, idx=None)): the call's index too, to find a changed item's parent.
    check: Callable[..., list[str]] = _no_problems
    # Facts about an item, for valid_when {"fact": …}: the app writes facts(item, doc), where doc is a View
    # (doc.parent(item), doc.item(id)), so a child can be valid by its parent (a note by its track's instrument).
    # A one-argument facts(item) still works.
    facts: Callable = _no_facts
    # The app's warnings: warn(data) -> plain sentences about what the file may hold but Rostrum no longer makes (a
    # retired design). Unlike `check`, they never stop a file opening or a call; they are never silent either: the
    # agent's replies carry them (mcp/server.py), inspect lists them, screens show them on the Problems chip.
    warn: Callable[[dict], list[str]] = _no_problems
    # The app's advice: advise(data) -> plain sentences about a state that is valid but probably not what was meant (2D:
    # a set of several drawings that shows only the first). `edit_document` and `run_script` replies carry the sentences
    # a call made new, as warnings (mcp/shared_edit.py); a state that was already there is not repeated.
    advise: Callable[[dict], list[str]] = _no_problems
    # describe(item, data) -> a short phrase for an item (Sound: "n8438 at 8.44 s E2 0.5 beat"), or None for the id alone.
    # `edit_document` replies list what a change added, changed and removed, each item through it (mcp/edit_summary.py);
    # `data` is the document after the change (the tempo and keys an item's times need).
    describe: Callable[[dict, dict], str | None] | None = None
    # elsewhere(id) -> a plain hint, or None: what to say when a target id isn't in this document but names something
    # that lives outside it (Sound: a project marker, changed with edit_markers).
    elsewhere: Callable[[str], str | None] | None = None
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
        params = inspect.signature(app_check).parameters
        n = len(params)
        if "idx" in params:              # check(data, items, idx=): the call's index finds a changed item's parent
            self.check = lambda data, items=None, only=None, idx=None: app_check(data, items, idx=idx)
        elif n < 3:
            self.check = ((lambda data, items=None, only=None, idx=None: app_check(data)) if n < 2 else
                          (lambda data, items=None, only=None, idx=None: app_check(data, items)))
        else:
            self.check = lambda data, items=None, only=None, idx=None: app_check(data, items, only)
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

    def bring_up(self, data: dict, from_version: int, folder=None) -> tuple[dict, list[str]]:
        """`data` (format `from_version`) as this build holds it: the format's steps, then the app's `upgrade`.
        (new data, labels); no labels: nothing changed. Raises what a step raises."""
        data, labels = self.migrate(data, from_version, folder)
        up = self.upgrade(data, self.lists, folder) if self.upgrade else None
        if up is not None:
            data, label = up
            labels.append(label)
        return data, labels

    def bad_values(self, items, only=None):
        """Each stored field value its kind's own field op refuses (field_values.bad_values). Yields RostrumErrors."""
        return field_values.bad_values(self.registry, self.lists, items, only)

    def problems(self, data: dict, items=None, only=None, idx=None) -> list[str]:
        """The whole-document check: every field value (or only `items`', the ones a call changed; `only`: of those,
        just the fields it set, see bad_values) against its field's own data, then the app's own check. Run after
        every call and on every open. `idx`: data's index (with `items`), so an app's check finds a changed item's
        parent without walking the whole document (a drag's every move: ~1 ms per 100 layers)."""
        try:
            out = [f"{e.where}: {e.subject} {e.problem}" + (f" ({', '.join(e.accepted)})" if e.accepted else "")
                   for e in self.bad_values(walk(data, self.lists) if items is None else items, only)]
            return out + list(self.check(data, items, only if items is not None else None, idx if items is not None else None))
        except SHAPE_ERRORS as e:
            return [f"{type(e).__name__}: {e}"]

    def warnings(self, data: dict) -> list[str]:
        """What the document holds that still opens but is no longer made (`warn`), in words."""
        try:
            return list(self.warn(data))
        except SHAPE_ERRORS as e:
            return [f"{type(e).__name__}: {e}"]

    def advice(self, data: dict) -> list[str]:
        """What the document holds that is valid but probably not meant (`advise`), in words."""
        try:
            return list(self.advise(data))
        except SHAPE_ERRORS:
            return []

    def view(self, doc) -> View:
        """A View of `doc`; a Document lends the index it keeps (finding an item's parent walked the whole song on
        every selection: ~18 ms a click on a 3-minute Sound song)."""
        if isinstance(doc, View):
            return doc
        if isinstance(doc, dict):
            return View(doc, self.lists)
        return View(doc.data, self.lists, doc.locs() if hasattr(doc, "locs") else None)

    def blank(self) -> dict:
        if self.new:
            return self.new()
        return {"id": "root", "type": "doc", **{k: [] for k in self.lists.get("doc", [])}}

    @property
    def format(self) -> str:
        return f"rostrum-{self.name}"
