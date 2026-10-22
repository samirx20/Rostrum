"""A document: the tree, its one history, and the only door in (`apply`). The GUI, scripts and agents all
change it through here (OPERATIONS.md §§ 5–6)."""
from __future__ import annotations

import copy
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from . import edits as E
from . import run
from .diff import diff
from .errors import RostrumError, codes
from .history import Change, History
from .storage import doc_hash
from .tree import index
from .who import Who

NUDGE_S = 1.0     # repeated small changes to the same fields by the same person merge within this time
_last_t = [0.0]


def ticking() -> float:
    """The clock every document stamps its changes with: wall time, but never the same or earlier twice in a process, so
    two changes made in one tick (a document and the project's markers) still have an order for one undo (desk.py)."""
    _last_t[0] = max(time.time(), _last_t[0] + 1e-6)
    return _last_t[0]


@dataclass
class Event:
    kind: str          # "change" | "preview" | "reset"
    change: Change | None = None


class Document:
    def __init__(self, kind, data: dict | None = None, folder=None, item=None, clock=ticking):
        self.kind, self.folder, self.item_id, self.clock = kind, folder, item, clock
        self.data = data if data is not None else kind.blank()
        index(self.data, kind.lists)                    # a duplicate id fails here, loudly
        self.base = copy.deepcopy(self.data)            # history line 0
        self.history = History(kind.lists)
        self.script_bases: dict[str, dict] = {}         # § 7: what each script produced last time
        self._subs, self._gesture = [], None

    @classmethod
    def new(cls, kind, folder=None, item=None, start=(), **kw) -> "Document":
        """A new document. `start`: operations that make its starting contents (a new project's blank composition):
        they are history line 0, not a change, so a new file has nothing to undo and shows no changes."""
        data = run.plan(kind, kind.blank(), list(start))[0] if start else None
        return cls(kind, data, folder, item, **kw)

    @classmethod
    def open(cls, folder, item, kind) -> "Document":
        """Open a saved document; a file changed outside Rostrum is recorded first as a change by `outside`."""
        from .storage import open_doc
        return open_doc(cls, folder, item, kind)

    # reading
    def item(self, id_) -> dict:
        idx = index(self.data, self.kind.lists)
        if id_ not in idx:
            raise RostrumError.not_found("document", "item", id_, idx)
        return idx[id_].item

    def has(self, id_) -> bool:
        return id_ in index(self.data, self.kind.lists)

    def items(self):
        return (loc.item for loc in index(self.data, self.kind.lists).values())

    def parent_of(self, id_):
        loc = index(self.data, self.kind.lists).get(id_)
        if loc is None:
            raise RostrumError.not_found("document", "item", id_, index(self.data, self.kind.lists))
        return loc.parent, loc.key, loc.index

    @property
    def seq(self) -> int:
        return self.history.seq

    def who_changed(self, id_, field_=None) -> Change | None:
        return self.history.who_changed(id_, field_)

    # the door
    def apply(self, calls, who: Who, label=None, session=None, based_on=None) -> Change | None:
        """Run a list of operations as one change, all or nothing. Nothing changed = nothing recorded (None)."""
        if self._gesture is not None:
            raise RostrumError(codes.CONFLICT, "apply", "the document", "is being dragged by a person right now",
                               hint="Try again in a moment.")
        work, edits, calls = run.plan(self.kind, self.data, calls)
        if based_on is not None:
            self._check_based_on(edits, based_on)
        label = label or ", ".join(dict.fromkeys(self.kind.registry.get(c["op"]).label for c in calls))
        if not edits:
            return None
        if self._nudge(who, label, edits, calls, work):
            return self.history.changes[-1]
        return self.commit(work, edits, who, label, calls, session)

    def commit(self, work, edits, who, label, calls=(), session=None, undoes=(), redoes=()) -> Change:
        """Record an already-checked new tree as one change (used by apply, undo, merge, gestures)."""
        c = Change(self.seq + 1, self.seq, who, label, _now(), list(edits), list(calls), session,
                   doc_hash(work), list(undoes), list(redoes), self.clock())
        self.data = work
        self.history.add(c)
        self._emit(Event("change", c))
        return c

    def _check_based_on(self, edits, based_on):
        mine = set().union(*(E.keys(e, self.kind.lists) for e in edits))
        for c in self.history.since(based_on):
            hit = E.overlap(self.history.keys(c), mine)
            if hit:
                raise RostrumError(codes.CONFLICT, "apply", E.key_text(sorted(hit)[0]),
                                   f"was changed by {c.who} (\"{c.label}\", step {c.seq}) after step {based_on}",
                                   hint="Read the document again and retry.")

    def _nudge(self, who, label, edits, calls, work) -> bool:
        last = self.history.changes[-1] if self.history.changes else None
        if not (last and who.kind == "person" and last.who == who and last.original and last.label == label
                and self.clock() - last.t < NUDGE_S and all(isinstance(e, E.Set) for e in last.edits + edits)):
            return False
        if {(e.id, *e.path) for e in edits} != {(e.id, *e.path) for e in last.edits}:
            return False
        first = {(e.id, *e.path): e.before for e in last.edits}
        last.edits = [E.Set(e.id, e.path, e.value, first[(e.id, *e.path)]) for e in edits]
        last.calls, last.t, last.hash_after = last.calls + calls, self.clock(), doc_hash(work)
        self.data = work
        self._emit(Event("change", last))
        return True

    # undo / redo: new changes, per author
    def undo(self, who: Who) -> Change | None:
        c = self.history.last_undoable(who)
        return self.undo_changes([c], who) if c else None

    def undo_session(self, session, who: Who) -> Change | None:
        cs = [c for c in self.history.changes if c.original and c.session == session and self.history.done[c.seq]]
        return self.undo_changes(cs, who, f"Undid session {session}") if cs else None

    def undo_changes(self, targets, who, label=None) -> Change:
        self.history.blockers(targets, max(self.history.at[c.seq] for c in targets))
        rev = [E.reverse(e) for c in sorted(targets, key=lambda c: -c.seq) for e in reversed(c.edits)]
        return self._replay(rev, who, label or f"Undid: {targets[-1].label}", undoes=[c.seq for c in targets])

    def redo(self, who: Who) -> Change | None:
        c = self.history.last_redoable(who)
        if not c:
            return None
        self.history.blockers([c], self.history.at[c.seq])
        return self._replay(c.edits, who, f"Redid: {c.label}", redoes=[c.seq])

    def _replay(self, edits, who, label, **kw) -> Change:
        work = copy.deepcopy(self.data)
        done = [E.apply(work, self.kind.lists, e, label) for e in edits]
        return self.commit(work, done, who, label, **kw)

    # versions
    def mark_version(self, name):
        self.history.versions[name] = self.seq

    def versions(self) -> dict:
        return dict(self.history.versions)

    def at_step(self, seq) -> dict:
        data = copy.deepcopy(self.base)
        for c in self.history.changes[:seq]:
            for e in c.edits:
                E.apply(data, self.kind.lists, e, f"step {c.seq}")
        return data

    def restore_version(self, name, who: Who) -> Change | None:
        if name not in self.history.versions:
            raise RostrumError.not_found("restore_version", "version", name, self.history.versions)
        target = self.at_step(self.history.versions[name])
        edits = diff(self.data, target, self.kind.lists)
        return self._replay(edits, who, f"Restore version \"{name}\"") if edits else None

    # gestures and listeners
    def gesture(self, label, who: Who):
        from .gesture import Gesture
        return Gesture(self, label, who)

    def run_script(self, name, output: dict, who: Who | None = None, force=False, session=None):
        from .merge import merge_script
        return merge_script(self, name, output, who or Who.script(name), force, session)

    def subscribe(self, fn):
        self._subs.append(fn)
        return lambda: self._subs.remove(fn)

    def _emit(self, ev: Event):
        for fn in list(self._subs):
            fn(ev)

    def save(self):
        from .storage import save
        save(self)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
