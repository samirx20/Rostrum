"""Two checks on a new change before it is recorded: not on top of someone else's later step, and whether it merges
into the person's last one (see document.py)."""
from __future__ import annotations

from . import edits as E
from . import joint
from .errors import RostrumError, codes
from .doc_door import Event

NUDGE_S = 1.0     # repeated small changes to the same fields by the same person merge within this time (never one
                  # that puts a field back where the merged step began: that is an undo-able step of its own)


class ChangeMixin:
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
        if any(e.value == first[(e.id, *e.path)] for e in edits):   # back where it began (a switch turned off again, a
            return False                                            # group added then taken away): its own step to undo
        last.edits = [E.Set(e.id, e.path, e.value, first[(e.id, *e.path)]) for e in edits]
        last.calls, last.t = last.calls + calls, self.clock()
        last.hash_of(work)
        self.data = work
        self._indexed(work, idx)
        with joint.within(last.step):
            self._emit(Event("change", last))
        return True
