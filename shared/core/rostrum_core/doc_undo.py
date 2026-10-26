"""A document's undo, redo, versions and restore: each a new change, per author (see document.py)."""
from __future__ import annotations

import copy

from . import edits as E
from .diff import diff
from .doc_door import _through_door
from .errors import RostrumError, codes
from .history import Change
from .tree import index
from .who import Who


class UndoMixin:
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
        self.history.blockers(targets)
        edits = [e for c in sorted(targets, key=lambda c: c.seq) for e in c.edits]
        return self._replay(edits, who, label or f"Redid: {targets[-1].label}", redoes=[c.seq for c in targets])

    @_through_door
    def undo_changes(self, targets, who, label=None) -> Change:
        self.history.blockers(targets)
        rev = [E.reverse(e) for c in sorted(targets, key=lambda c: -c.seq) for e in reversed(c.edits)]
        return self._replay(rev, who, label or f"Undid: {targets[-1].label}", undoes=[c.seq for c in targets])

    @_through_door
    def redo(self, who: Who) -> Change | None:
        c = self.history.last_redoable(who)
        if not c:
            return None
        self.history.blockers([c])
        return self._replay(c.edits, who, f"Redid: {c.label}", redoes=[c.seq])

    def _replay(self, edits, who, label, **kw) -> Change:
        if self._gesture is not None:           # undo / redo under a live drag or popover would step the history under
            raise RostrumError(codes.CONFLICT, "undo", "the document",            # what it shows (its end then mixes both)
                               f'has "{self._gesture.label}" open right now', hint="Finish it first: Enter keeps it, Esc puts it back.")
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
