"""What the top bar says about the person's one history: how many changes are *in effect*, and what Undo / Redo would do.

The documents keep an append-only history (an undo is itself a recorded step), so counting its entries made "N changes"
go UP after Undo. Here a change counts while it is done: Undo takes the count down, Redo brings it back. The same rule
as desk.py picks what Undo and Redo would act on, across the document and the markers (one history).
"""
from __future__ import annotations


def live_count(history) -> int:
    return sum(1 for c in history.changes if c.original and history.done[c.seq])


class UndoState:
    """Mix-in for Bridge2D, which publishes history_count, undo_label and redo_label as properties (a mix-in that is not
    a QObject cannot carry them)."""

    def _histories(self):
        docs = [self.doc] + [p.history_doc() for p in self._partners]
        return [d.history for d in docs if d is not None]

    def _next(self, pick):
        """(history, change) of the newest step Undo (or Redo) would act on, or None: desk.py's rule."""
        hs = self._histories()
        found = [(h.acted(c), h, c) for h in hs for c in [pick(h, self.who)] if c is not None]
        if not found:
            return None
        at, h, c = max(found, key=lambda f: f[0])
        if pick is not desk_last_undoable:
            newest_own = max((x.t for g in hs for x in g.changes if x.original and x.who == self.who), default=0.0)
            if at < newest_own:
                return None
        return h, c

    def _marker_saved(self):
        """A marker edit of this person's goes straight to the project's marker file, so the title never gets the
        "unsaved" dot for it (the dot is for the document). Say so instead, so no one thinks it still needs Save."""
        c = self.marks.last_change()
        if c is not None and c.who == self.who and c.seq != getattr(self, "_marker_seen", c.seq):
            self._set_status(f"{c.label}  ·  markers save as you go")
        self._marker_seen = c.seq if c is not None else 0

    def history_count(self):
        return sum(live_count(h) for h in self._histories())

    def undo_label(self):
        """What Undo would take back ("" when there is nothing to undo: the button is absent)."""
        hit = self._next(desk_last_undoable)
        return hit[1].label if hit else ""

    def redo_label(self):
        hit = self._next(desk_last_redoable)
        return hit[1].label if hit else ""


def desk_last_undoable(h, who):
    return h.last_undoable(who)


def desk_last_redoable(h, who):
    return h.last_redoable(who)
