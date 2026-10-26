"""A document: the tree, its one history, and the only door in (`apply`). The GUI, scripts and agents all
change it through here (OPERATIONS.md §§ 5–6). The class is one: its reading side is in doc_read, the merge of a
nudge and the based-on check in doc_nudge, undo / redo / versions in doc_undo; the clock, the door and the events in
doc_door (re-exported here)."""
from __future__ import annotations

import copy

from . import edits as E
from . import joint, run
from .doc_door import Event, _now, _through_door, ticking
from .doc_nudge import NUDGE_S, ChangeMixin
from .doc_read import ReadMixin
from .doc_undo import UndoMixin
from .errors import RostrumError, codes
from .history import Change, History
from .tree import index
from .who import Who


class Document(ReadMixin, ChangeMixin, UndoMixin):
    def __init__(self, kind, data: dict | None = None, folder=None, item=None, clock=ticking, base=None):
        self.kind, self.folder, self.item_id, self.clock = kind, folder, item, clock
        self.data = data if data is not None else kind.blank()
        self._idx = (self.data, self._top(), index(self.data, kind.lists))   # a duplicate id fails here; _index
        self._base = copy.deepcopy(self.data) if base is None else base   # history line 0 (opening: read when asked)
        self.history = History(kind.lists)
        self.script_bases: dict[str, dict] = {}         # § 7: what each script produced last time
        self.file_version = kind.version                # the file format it was read as (an older one is migrated on open)
        self.saved_by: str | None = None                # the app version that last saved it (storage.py)
        self.uses: dict = {}                            # the plugins it uses, from its file (plugin_parts.py), saved back
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

    @property
    def kept(self) -> dict:
        """The document as its history leaves it: what every save writes. While a drag or a live-preview box is open
        (gesture.py) `data` shows its unsaved picture; a save then (closing the window, Save, a timer, opening another
        song) writes the state from before it, never the preview as if it were kept."""
        return self._gesture.start if self._gesture is not None else self.data

    def drop_gesture(self):
        """Cancel an open drag or live-preview box, as Esc does: the document shows what its history leaves again and
        nothing is recorded. A window closing or switching songs calls it before its last save."""
        g = self._gesture
        if g is not None:
            g.cancel()
            g.__exit__(None, None, None)

    def make_way(self, what, end=True):
        """Another edit comes while a gesture is open. A live box that says how it ends when something else comes
        (`Gesture.interrupt`: Stagger…'s and the amounts popover's keep, as Enter does; a hover preview's take-back)
        ends first; a drag a person still holds refuses in plain words (critic r10: an open Stagger box made Ctrl+G
        say "being dragged by a person"). `end=False`: only the refusal (the caller picked its target already)."""
        g = self._gesture
        if g is not None and end and g.interrupt is not None:
            g.interrupt()
        g = self._gesture
        if g is not None:
            raise RostrumError(codes.CONFLICT, what, f'"{g.label}"', "is still open",
                               hint="Finish it first: let go of the mouse, or press Enter to keep it, Esc to put it back.")

    @_through_door
    def apply(self, calls, who: Who, label=None, session=None, based_on=None, join=True) -> Change | None:
        """Run a list of operations as one change, all or nothing. Nothing changed = nothing recorded (None).
        `join=False`: never merge into the person's previous change (an arrow-key press is one step each)."""
        self.make_way("apply")
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

    def commit(self, work, edits, who, label, calls=(), session=None, undoes=(), redoes=(), idx=None, format=None) -> Change:
        """Record an already-checked new tree as one change (used by apply, undo, merge, gestures). Live (live.py): if
        the door took in another program's steps first, `work` is an older picture, so the edits go on top of now.
        `idx`: work's index, when known. `format`: [from, to], an upgrade's file formats (formats.py)."""
        with self._door() as caught:
            if caught:
                work, idx = E.fork(self.data, self.kind.lists, self._index())
                edits = [E.apply(work, self.kind.lists, e, label, idx) for e in edits]
            return self._record(work, edits, who, label, calls, session, undoes, redoes, idx, format)

    def _record(self, work, edits, who, label, calls, session, undoes, redoes, idx=None, format=None) -> Change:
        c = Change(self.seq + 1, self.seq, who, label, _now(), list(edits), list(calls), session,
                   "", list(undoes), list(redoes), self.clock(), joint.current() or joint.new_id(), format)
        c.hash_of(work)                     # worked out when first read (saving, comparing), not on every change
        self.data = work
        if idx is not None:
            self._indexed(work, idx)
        self.history.add(c)
        joint.note(self, c.step)
        with joint.within(c.step):          # what a listener changes now (a marker following a layer) is this step
            self._emit(Event("change", c))
        return c
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
