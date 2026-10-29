"""A drag is one step (OPERATIONS.md § 6). While a person drags or scrubs, each move runs the same operations
(same checks) and updates the document live; on release the whole drag is saved as one change. Escape
(`cancel`) or an error puts everything back and records nothing; its "reset" event lists the edits that took the
document back (None: can't tell), so listeners redo only what the drag had touched.

    with doc.gesture("Move logo", Who.person()) as g:
        g.preview({"op": "layer.move", "target": ["logo"], "args": {"x": x}})
"""
from __future__ import annotations

from . import edits as E
from . import pending, run
from .diff import diff, touched
from .document import Event
from .errors import RostrumError, codes


class Gesture:
    def __init__(self, doc, label, who):
        self.doc, self.label, self.who = doc, label, who
        self.change, self.cancelled, self._calls = None, False, []
        self._kept = []              # calls of steps that made or removed items: the drag's record keeps them all
        self._stepped = False        # a step was shown: listeners saw a state that the end must take back or keep
        self._near = set()           # the ids the shown state differs on from the start: compares look only there
        self._made = None            # a fresh step's edits from the start (the shown state is exactly start + these)
        self._ended = False          # closed (a window closing cancels it: its owner's later end does nothing)
        self.interrupt = None        # how it ends when another edit comes (Document.make_way); None: that edit is refused

    def __enter__(self):
        self.doc.make_way("gesture")            # an open box that knows how ends first; else a plain refusal
        self.start, self._start_idx = self.doc.data, self.doc._index()   # never changed in place: no copy needed
        self.doc._gesture = self
        return self

    def preview(self, calls, fresh=False):
        """Run the calls on top of the drag so far. A bad step raises and leaves the last good state showing.
        `fresh`: run them on the state from before the drag instead (an action re-run live with other amounts, the
        kit's amounts popover: Humanise twice must not loosen twice); `calls` may then be a function, called while the
        document reads as it was before the drag (calls worked out from the selection see the original items)."""
        if self._ended:
            raise RostrumError(codes.CONFLICT, "gesture", f'"{self.label}"', "is closed already (cancelled when the "
                               "window closed)", hint="Start it again.")
        if fresh:
            return self._fresh(calls)
        calls = self.doc.routed(calls, self.who)
        work, edits, calls, idx = run.plan_indexed(self.doc.kind, self.doc.data, calls, idx=self.doc._index())
        self._near |= touched(edits, self.doc.kind.lists)
        self._made = None
        self.doc.data = work
        self.doc._indexed(work, idx)
        self._calls = self._kept + calls     # the last step says where the drag ended, after the steps that made
        if any(isinstance(e, (E.Insert, E.Remove, E.Many)) for e in edits):     # items (an Alt+drag copy is a duplicate, then
            self._kept = self._calls                                     # moves): later moves don't erase the copy
        self._stepped = True
        self.doc._emit(Event("preview", edits=edits))     # what this step changed: listeners redo only that

    def _fresh(self, calls):
        self.show_planned(self.plan(self.fresh_calls(calls)))

    # A fresh preview in three parts, so a big one (Repeat x4 on a whole song: ~1.7 s of planning) can be planned on
    # another thread while the window goes on: `fresh_calls` and `show_planned` on the document's thread, `plan` anywhere.
    def fresh_calls(self, calls) -> list:
        """The calls of a fresh step, worked out while the document reads as it was before the drag (on its thread)."""
        if self._ended:
            raise RostrumError(codes.CONFLICT, "gesture", f'"{self.label}"', "is closed already (cancelled when the "
                               "window closed)", hint="Start it again.")
        shown, shown_idx = self.doc.data, self.doc._index()
        self.doc.data = self.start
        self.doc._indexed(self.start, self._start_idx)
        try:                                # a person's calls through the window's routes (a chosen animation layer)
            return self.doc.routed(calls() if callable(calls) else calls, self.who)
        finally:
            self.doc.data = shown
            self.doc._indexed(shown, shown_idx)

    def plan(self, calls) -> tuple:
        """The calls planned on the state from before the drag: pure (the start and its index are never changed), so
        any thread may run it. Raises what the calls would raise."""
        return run.plan_indexed(self.doc.kind, self.start, calls, idx=self._start_idx)

    def show_planned(self, planned):
        """A fresh step's plan (`plan`) shown: the document is the start plus it, listeners told what differs from
        what they show (on the document's thread)."""
        if self._ended:
            raise RostrumError(codes.CONFLICT, "gesture", f'"{self.label}"', "is closed already", hint="Start it again.")
        work, made, calls, idx = planned
        shown, shown_idx = self.doc.data, self.doc._index()
        near = touched(made, self.doc.kind.lists)
        edits = made if shown is self.start else diff(                  # from what listeners show now (the first
            shown, work, self.doc.kind.lists, shown_idx, idx, self._near | near)   # step: start + made, a Many stays one)
        self._near, self._made = near, made
        self.doc.data = work
        self.doc._indexed(work, idx)
        self._calls, self._kept = calls, []     # the state shown is the start plus these calls alone
        self._stepped = True
        self.doc._emit(Event("preview", edits=edits))

    def cancel(self):
        self.cancelled = True

    def __exit__(self, exc_type, exc, tb):
        if self._ended:
            return False
        self._ended = True
        self.doc._gesture = None
        end, end_idx = self.doc.data, self.doc._index()
        self.doc.data = self.start
        self.doc._indexed(self.start, self._start_idx)
        if not self._stepped:        # a press and a release with no step between (a click): nothing was shown, so
            return False             # nothing to take back; a reset made every listener redo its work (~7 ms a pick)
        if exc_type or self.cancelled:          # taken back: listeners hear what that undid on what they show, so
            self._reset(end, end_idx)           # they redo only that (Esc in a popover redrew every row: 34-64 ms)
            return False
        edits = self._made if self._made is not None else diff(
            self.start, end, self.doc.kind.lists, self._start_idx, end_idx, self._near)   # (a Shift stays one edit)
        if edits:
            again = pending.intent("apply", self.who, self.label, self._calls) if self._made is not None else None
            self.change = self.doc.commit(end, edits, self.who, self.label, self._calls, idx=end_idx,
                                          intent=again)    # (a fresh step: start + its calls is exactly the end)
        else:
            self.doc._emit(Event("reset", edits=[]))
        return False

    def _reset(self, end, end_idx):
        if self._made is not None:              # start + made is what shows: its exact reverse, nothing to compare
            self.doc._emit(Event("reset", edits=[E.reverse(e) for e in reversed(self._made)]))
            return
        try:
            back = diff(end, self.start, self.doc.kind.lists, end_idx, self._start_idx, self._near)
        except Exception:  # noqa: BLE001  a step that broke the tree can't be compared: everyone redoes all
            back = None
        self.doc._emit(Event("reset", edits=back))
