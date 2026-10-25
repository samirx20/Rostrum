"""A document: the tree, its one history, and the only door in (`apply`). The GUI, scripts and agents all
change it through here (OPERATIONS.md §§ 5–6)."""
from __future__ import annotations

import contextlib
import copy
import functools
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from . import edits as E
from . import joint, run
from .diff import _at, diff
from .errors import RostrumError, codes
from .history import Change, History
from .tree import index
from .who import Who

NUDGE_S = 1.0     # repeated small changes to the same fields by the same person merge within this time
_last_t = [0.0]


def ticking() -> float:
    """The clock every document stamps its changes with: wall time, but never the same or earlier twice in a process, so
    two changes made in one tick (a document and the project's markers) still have an order for one undo (desk.py)."""
    _last_t[0] = max(time.time(), _last_t[0] + 1e-6)
    return _last_t[0]


def _through_door(fn):
    """A change-making method runs inside the document's door: with live.keep, lock + catch up + save (live.py)."""
    @functools.wraps(fn)
    def through(self, *a, **kw):
        with self._door():
            return fn(self, *a, **kw)
    return through


@dataclass
class Event:
    kind: str          # "change" | "preview" | "reset"
    change: Change | None = None
    edits: list | None = None      # a preview's: what this step changed on top of the last one (a change's are its own)


class Document:
    def __init__(self, kind, data: dict | None = None, folder=None, item=None, clock=ticking, base=None):
        self.kind, self.folder, self.item_id, self.clock = kind, folder, item, clock
        self.data = data if data is not None else kind.blank()
        self._idx = (self.data, self._top(), index(self.data, kind.lists))   # a duplicate id fails here; _index
        self._base = copy.deepcopy(self.data) if base is None else base   # history line 0 (opening: read when asked)
        self.history = History(kind.lists)
        self.script_bases: dict[str, dict] = {}         # § 7: what each script produced last time
        self.file_version = kind.version                # the file format it was read as (an older one is migrated on open)
        self.saved_by: str | None = None                # the app version that last saved it (storage.py)
        self.file_at: int | None = None                 # opened: the step its document file showed (None: unknown)
        self._subs, self._gesture = [], None
        self.live = None                                # live.Live when another program shares the file
        self._written = None                            # storage.Written: where the history file ends, as we left it
        self.notes: list[str] = []                      # plain sentences from opening (a step cut off by a crash)

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

    @property
    def base(self) -> dict:
        """The document when its history began (a big one opened from a file is parsed only when asked)."""
        if callable(self._base):
            self._base = self._base()
        return self._base

    @base.setter
    def base(self, value):
        self._base = value

    # reading
    def _index(self) -> dict:
        """id -> Loc for the current data, kept until the data is replaced (every change makes a new tree; a tree is
        never written in place, edits.fork). One `is` per read (screens ask 100+ times per change). The one exception
        is a set-up filling a new document's data before its first change (tests do: `doc.data["tracks"].append`):
        until the history has a step, its top lists are compared too. Positions may be stale (parent_of looks)."""
        if self._idx[0] is not self.data or (not self.history.changes and self._idx[1] != self._top()):
            self._idx = (self.data, self._top(), index(self.data, self.kind.lists))
        return self._idx[2]

    def locs(self) -> dict:
        """id -> Loc for the current data (items and parents are current; positions may be stale, see parent_of)."""
        return self._index()

    def _indexed(self, data, idx):
        self._idx = (data, self._top(data), idx)

    def _top(self, data=None):
        data = self.data if data is None else data
        return tuple((id(data.get(k)), len(data.get(k) or ())) for k in self.kind.lists.get(data.get("type"), []))

    def item(self, id_) -> dict:
        idx = self._index()
        if id_ not in idx:
            raise RostrumError.not_found("document", "item", id_, idx)
        return idx[id_].item

    def has(self, id_) -> bool:
        return id_ in self._index()

    def items(self):
        return (loc.item for loc in list(self._index().values()))

    def parent_of(self, id_):
        idx = self._index()
        loc = idx.get(id_)
        if loc is None:
            raise RostrumError.not_found("document", "item", id_, idx)
        return loc.parent, loc.key, (_at(idx, id_) if loc.parent is not None else loc.index)

    @property
    def seq(self) -> int:
        return self.history.seq

    def who_changed(self, id_, field_=None) -> Change | None:
        return self.history.who_changed(id_, field_)

    # the door
    def _door(self):
        return self.live.door() if self.live is not None else contextlib.nullcontext([])

    def locked_by(self, id_) -> Who | None:
        """Who set item `id_`'s lock last (the lock rule and its plain refusal); None when nobody did through an op."""
        c = self.history.who_changed(id_, "locked")
        return c.who if c is not None else None

    @_through_door
    def apply(self, calls, who: Who, label=None, session=None, based_on=None, join=True) -> Change | None:
        """Run a list of operations as one change, all or nothing. Nothing changed = nothing recorded (None).
        `join=False`: never merge into the person's previous change (an arrow-key press is one step each)."""
        if self._gesture is not None:
            raise RostrumError(codes.CONFLICT, "apply", "the document", "is being dragged by a person right now",
                               hint="Try again in a moment.")
        if self.kind.tidy:
            calls = self.kind.tidy(run.normalize(calls), self.folder)
        work, edits, calls, idx = run.plan_indexed(self.kind, self.data, calls, self.locked_by, who, self._index())
        if based_on is not None:
            self._check_based_on(edits, based_on)
        label = label or ", ".join(dict.fromkeys(self.kind.registry.get(c["op"]).label for c in calls))
        if not edits:
            return None
        if join and self._nudge(who, label, edits, calls, work, idx):
            return self.history.changes[-1]
        return self.commit(work, edits, who, label, calls, session, idx=idx)

    def commit(self, work, edits, who, label, calls=(), session=None, undoes=(), redoes=(), idx=None) -> Change:
        """Record an already-checked new tree as one change (used by apply, undo, merge, gestures). Live (live.py): if
        the door took in another program's steps first, `work` is an older picture, so the edits go on top of now.
        `idx`: work's index, when known."""
        with self._door() as caught:
            if caught:
                work, idx = E.fork(self.data, self.kind.lists, self._index())
                edits = [E.apply(work, self.kind.lists, e, label, idx) for e in edits]
            return self._record(work, edits, who, label, calls, session, undoes, redoes, idx)

    def _record(self, work, edits, who, label, calls, session, undoes, redoes, idx=None) -> Change:
        c = Change(self.seq + 1, self.seq, who, label, _now(), list(edits), list(calls), session,
                   "", list(undoes), list(redoes), self.clock(), joint.current() or joint.new_id())
        c.hash_of(work)                     # worked out when first read (saving, comparing), not on every change
        self.data = work
        if idx is not None:
            self._indexed(work, idx)
        self.history.add(c)
        joint.note(self, c.step)
        with joint.within(c.step):          # what a listener changes now (a marker following a layer) is this step
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

    def _nudge(self, who, label, edits, calls, work, idx) -> bool:
        last = self.history.changes[-1] if self.history.changes else None
        if not (last and who.kind == "person" and last.who == who and last.original and last.label == label
                and self.clock() - last.t < NUDGE_S and all(isinstance(e, E.Set) for e in last.edits + edits)):
            return False
        if {(e.id, *e.path) for e in edits} != {(e.id, *e.path) for e in last.edits}:
            return False
        first = {(e.id, *e.path): e.before for e in last.edits}
        last.edits = [E.Set(e.id, e.path, e.value, first[(e.id, *e.path)]) for e in edits]
        last.calls, last.t = last.calls + calls, self.clock()
        last.hash_of(work)
        self.data = work
        self._indexed(work, idx)
        with joint.within(last.step):
            self._emit(Event("change", last))
        return True

    # undo / redo: new changes, per author
    @_through_door
    def undo(self, who: Who) -> Change | None:
        c = self.history.last_undoable(who)
        return self.undo_changes([c], who) if c else None

    @_through_door
    def undo_session(self, session, who: Who) -> Change | None:
        cs = [c for c in self.history.changes if c.original and c.session == session and self.history.done[c.seq]]
        return self.undo_changes(cs, who, f"Undid session {session}") if cs else None

    @_through_door
    def redo_session(self, session, who: Who) -> Change | None:
        """Bring back a whole taken-back run (History's "Bring back"): one step, refused like any redo."""
        cs = [c for c in self.history.changes if c.original and c.session == session and not self.history.done[c.seq]]
        if not cs:
            return None
        return self.redo_changes(cs, who, f"Brought back: {cs[-1].label}")

    @_through_door
    def redo_changes(self, targets, who, label=None) -> Change:
        """Bring back undone originals `targets` as one new change (refused like any redo)."""
        self.history.blockers(targets, max(self.history.at[c.seq] for c in targets))
        edits = [e for c in sorted(targets, key=lambda c: c.seq) for e in c.edits]
        return self._replay(edits, who, label or f"Redid: {targets[-1].label}", redoes=[c.seq for c in targets])

    @_through_door
    def undo_changes(self, targets, who, label=None) -> Change:
        self.history.blockers(targets, max(self.history.at[c.seq] for c in targets))
        rev = [E.reverse(e) for c in sorted(targets, key=lambda c: -c.seq) for e in reversed(c.edits)]
        return self._replay(rev, who, label or f"Undid: {targets[-1].label}", undoes=[c.seq for c in targets])

    @_through_door
    def redo(self, who: Who) -> Change | None:
        c = self.history.last_redoable(who)
        if not c:
            return None
        self.history.blockers([c], self.history.at[c.seq])
        return self._replay(c.edits, who, f"Redid: {c.label}", redoes=[c.seq])

    def _replay(self, edits, who, label, **kw) -> Change:
        work, idx = E.fork(self.data, self.kind.lists, self._index())
        done = [E.apply(work, self.kind.lists, e, label, idx) for e in edits]
        return self.commit(work, done, who, label, idx=idx, **kw)

    # versions
    @_through_door
    def mark_version(self, name):
        self.history.versions[name] = self.seq

    def versions(self) -> dict:
        return dict(self.history.versions)

    def at_step(self, seq) -> dict:
        data = copy.deepcopy(self.base)
        idx = index(data, self.kind.lists)              # once: each edit keeps it up to date
        for c in self.history.changes[:seq]:
            for e in c.edits:
                E.apply(data, self.kind.lists, e, f"step {c.seq}", idx)
        return data

    @_through_door
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

    @_through_door
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
        """Write the document to its project folder. A live document (live.keep) has every change in its history file
        already; this writes its document file too, through the one door (lock, catch up), so a save never writes over
        another program's steps (live.Live.fold)."""
        if self.live is not None:
            self.live.fold()
            return
        from .storage import save
        save(self)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
