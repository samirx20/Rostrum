"""A drag is one step (OPERATIONS.md § 6). While a person drags or scrubs, each move runs the same operations
(same checks) and updates the document live; on release the whole drag is saved as one change. Escape
(`cancel`) or an error puts everything back and records nothing.

    with doc.gesture("Move logo", Who.person()) as g:
        g.preview({"op": "layer.move", "target": ["logo"], "args": {"x": x}})
"""
from __future__ import annotations

import copy

from . import run
from .diff import diff
from .document import Event
from .errors import RostrumError, codes


class Gesture:
    def __init__(self, doc, label, who):
        self.doc, self.label, self.who = doc, label, who
        self.change, self.cancelled, self._calls = None, False, []

    def __enter__(self):
        if self.doc._gesture is not None:
            raise RostrumError(codes.CONFLICT, "gesture", f'"{self.label}"',
                               f"can't start: \"{self.doc._gesture.label}\" is still being dragged")
        self.start = copy.deepcopy(self.doc.data)
        self.doc._gesture = self
        return self

    def preview(self, calls):
        """Run the calls on top of the drag so far. A bad step raises and leaves the last good state showing."""
        work, _, calls = run.plan(self.doc.kind, self.doc.data, calls)
        self.doc.data = work
        self._calls = calls          # the last step says where the drag ended
        self.doc._emit(Event("preview"))

    def cancel(self):
        self.cancelled = True

    def __exit__(self, exc_type, exc, tb):
        self.doc._gesture = None
        end, self.doc.data = self.doc.data, self.start
        if exc_type or self.cancelled:
            self.doc._emit(Event("reset"))
            return False
        edits = diff(self.start, end, self.doc.kind.lists)
        if edits:
            self.change = self.doc.commit(end, edits, self.who, self.label, self._calls)
        else:
            self.doc._emit(Event("reset"))
        return False
