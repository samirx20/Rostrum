"""Edits from the arrangement and piano roll: mute / solo, add a note, delete, and the drags (one doc.gesture =
one undo step). Every one an operation (moves.py builds the calls)."""
from __future__ import annotations

from PySide6.QtCore import Slot
from rostrum_gui.edits import Drag

from . import moves, timing


class EditSlots:
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
        if self._sel and self.doc.has(self._sel):
            self._guard(lambda: self._apply([moves.remove_call(self.doc, self._sel)], "Delete"))

    @Slot(str, result=bool)
    def beginDrag(self, item_id):
        """Press on a note, hit, clip or marker: select it and start one gesture."""
        self.endDrag()
        self.select(item_id)

        def go():
            self._grab = moves.grab(self.doc, item_id)
            self._drag = Drag(self.doc, self.who, moves.LABELS[self._grab["type"]])
        return self._guard(go)

    @Slot(float, int, bool)
    def dragBy(self, dt, dsemi, free):
        """Total move from the press: dt seconds, dsemi semitones (notes), snapped to 1/4 beat unless free."""
        if self._drag is not None:
            self._guard(lambda: self._drag.preview(moves.drag_calls(self.doc, self._grab, dt, dsemi, free)))

    @Slot()
    def endDrag(self):
        d, self._drag, self._grab = self._drag, None, None
        if d is not None:
            self._guard(lambda: self._done(d.end(), ""))

    @Slot()
    def cancelDrag(self):
        d, self._drag, self._grab = self._drag, None, None
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
