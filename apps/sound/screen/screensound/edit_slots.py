"""Edits from the arrangement and piano roll: mute / solo, add a note, delete, and the drags (one doc.gesture =
one undo step). Every one an operation (moves.py builds the calls).

A drag (DESIGN.md §5): every selected note / hit / clip / line moves together, held by the one pressed; Ctrl = no
snapping, Shift = only in time (no pitch change), Alt = drag a copy (the copies stay where the items were). While
it snaps, `snapLine` says where and to what (a marker's name, "" for the grid) for the screen's thin line.
"""
from __future__ import annotations

from PySide6.QtCore import Property, Signal, Slot
from rostrum_gui.edits import Drag

from . import handles, moves, timing
from .actions import LIST


class EditSlots:
    snapChanged = Signal()

    @Property("QVariantMap", notify=snapChanged)
    def snapLine(self):
        """{t, name} of what the drag snapped to; {} when nothing (free, or no drag)."""
        return getattr(self, "_snap", {})

    def _set_snap(self, caught):
        if caught != getattr(self, "_snap", {}):
            self._snap = caught
            self.snapChanged.emit()

    @Slot(str, str)
    def toggleTrack(self, track_id, field):
        def go():
            call, label = moves.toggle_call(self.doc, track_id, field)
            self._apply([call], label)
        self._guard(go)

    @Slot(float, int)
    def addNote(self, t, key):
        if not self._track:
            return

        def go():
            before = {n["id"] for n in self.doc.item(self._track).get("notes", [])}
            self._apply([moves.add_note_call(self.doc, self._track, t, key)], "Add note")
            new = [n["id"] for n in self.doc.item(self._track)["notes"] if n["id"] not in before]
            if new:
                self.select(new[0])
        self._guard(go)

    @Slot()
    def removeSelected(self):
        if self._apt:
            return self._remove_point()
        valid = {e["id"] for e in LIST.available(self._facts())}
        if self.timeRange and "cut_range" in valid:             # Delete on a time range over a clip: cut it out
            return self._hub.run("cut_range")
        if len(self.selectedIds) > 1:
            return self._hub.run("delete")
        if self._sel and self.doc.has(self._sel):
            self._guard(lambda: self._apply([moves.remove_call(self.doc, self._sel)], "Delete"))

    @Slot(str, result=bool)
    def beginDrag(self, item_id):
        """Press on a note, hit, clip or marker: select it (kept when it is already one of several selected) and
        start one gesture for everything selected."""
        self.endDrag()
        if item_id not in self.selectedIds:
            self.select(item_id)

        def go():
            many = self.doc.item(item_id)["type"] in moves.MANY
            self._grab = moves.grab_many(self.doc, self.selectedIds, item_id) if many else moves.grab(self.doc, item_id)
            self._copy = False
            n = len(self._grab["items"]) if many else 1
            kind = self._grab["primary"]["type"] if many else self._grab["type"]
            self._drag = Drag(self.doc, self.who, moves.LABELS[kind] + (f" + {n - 1} more" if n > 1 else ""))
        return self._guard(go)

    @Slot(float, int, bool)
    def dragBy(self, dt, dsemi, free):
        """Total move from the press: dt seconds, dsemi semitones (notes); snapped unless free (Ctrl)."""
        self.dragTo(dt, dsemi, free, False, False, 0.0)

    @Slot(float, int, bool, bool, bool, float)
    def dragTo(self, dt, dsemi, free, only_time, copy, tol):
        """A drag's move with its keys: free (Ctrl, no snapping), only_time (Shift), copy (Alt, read once, at the
        first move); `tol` = how near (seconds) a marker or the playhead must be to catch it."""
        if self._drag is None:
            return
        g = self._grab

        def go():
            if "primary" not in g:
                return self._drag.preview(moves.drag_calls(self.doc, g, dt, dsemi, free))
            calls, caught = moves.many_calls(self.doc, g, dt, dsemi, free, only_time, self._snap_targets(), tol)
            if not only_time:
                calls += moves.track_calls(self.doc, g, getattr(self, "_to_track", ""))
            if copy and not self._copy:
                calls, self._copy = moves.copy_calls(g) + calls, True
            self._drag.preview(calls)
            self._set_snap(caught if caught.get("name") or not free else {})
        self._guard(go)

    @Slot(str)
    def dragTrack(self, track_id):
        """The row under the pointer while dragging clips: they go to that track (when it can hold them)."""
        self._to_track = track_id

    def _snap_targets(self):
        return [{"t": m["t"], "name": m["name"]} for m in self._view["markers"]] + [{"t": self._t, "name": "playhead"}]

    @Slot()
    def endDrag(self):
        d, g, self._drag, self._grab, self._to_track = self._drag, self._grab, None, None, ""
        self._set_snap({})
        if d is not None and g and "handle" in g:      # the step says what it did ("Fade in 0.40 s")
            d._ctx.label = handles.label(self.doc, g["grabs"], g["handle"])
        if d is not None:
            self._guard(lambda: self._done(d.end(), ""))

    @Slot()
    def cancelDrag(self):
        d, self._drag, self._grab = self._drag, None, None
        self._set_snap({})
        if d is not None:
            self._guard(lambda: d.end(cancel=True))

    @Slot(str, float, bool, result=bool)
    def moveSharedMarker(self, marker_id, dt, free):
        """Release of a drag on one of the project's markers: one `marker.move` through the shared marker list
        (rostrum_gui.markers.MarkerWatch), so it moves for every app and undoes as one step; snapped to a quarter
        beat unless free. The sound follows on the watch's change like any other marker move."""
        row = next((m for m in self._marks.rows() if m["id"] == marker_id), None)
        if row is None or abs(dt) < 1e-6:
            return False
        return self._marks.move(marker_id, timing.snap(row["at"] + dt, self.doc.data, free))
