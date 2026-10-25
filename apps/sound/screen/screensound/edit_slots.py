"""Edits from the arrangement and piano roll: mute / solo, add a note, delete, and the drags (one doc.gesture =
one undo step). Every one an operation (moves.py builds the calls).

A drag (DESIGN.md §5): every selected note / hit / clip / line moves together, held by the one pressed; Ctrl = no
snapping, Shift = only in time (no pitch change), Alt = drag a copy (the copies stay where the items were). While
it snaps, `snapLine` says where and to what (a marker's name, "" for the grid) for the screen's thin line.
"""
from __future__ import annotations

from PySide6.QtCore import Property, Signal, Slot
from rostrum_gui import snap
from rostrum_gui.edits import Drag, Scrub

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
    def beginScrubOn(self, item_id, param):
        """A mixer strip's fader, pan or level press: the scrub works on that strip's item at once; the strip is
        picked now and the settings panel follows once the scrub ends (pressSelect, `_settle`), so the press waits
        for neither (making the panel's rows cost the press ~50 ms)."""
        self.endScrub()
        if self.selectedIds != [item_id]:
            self.pressSelect(item_id)
        self._guard(lambda: setattr(self._kit, "scrub", Scrub(self.doc, self.who, [item_id], param, self.edit_call)))

    @Slot()
    def endScrubOn(self):
        """The release of `beginScrubOn`: one change, then the settings panel shows the strip's item."""
        self.endScrub()
        self._settle()

    @Slot(str, str)
    def toggleTrack(self, track_id, field):
        def go():
            call, label = moves.toggle_call(self.doc, track_id, field)
            self._apply([call], label)
        self._guard(go)

    @Slot(float, int, float)
    def addNote(self, t, key, px=0.0):
        """Double-click on an empty key: a note there, in the grid cell under the pointer (`px`: one screen pixel in
        seconds, timing.snap), one step, selected."""
        if not self._track:
            return

        def go():
            before = {n["id"] for n in self.doc.item(self._track).get("notes", [])}
            self._apply([moves.add_note_call(self.doc, self._track, t, key, beats=self._draw_beats(timing.beat(t, self.doc.data)),
                                              grid=self._grid_now, px=px, lock=self.keepInKey)], "Add note")
            new = [n["id"] for n in self.doc.item(self._track)["notes"] if n["id"] not in before]
            if new:
                self.select(new[0])
        self._guard(go)

    @Slot(float, float, float, result=str)
    def addHit(self, t, row, px=0.0):
        """Double-click on an empty drum row (or a click with Draw): a hit on that drum in the grid cell under the
        pointer, one step, selected. Returns its id ("" when none)."""
        drums = self._view["roll"].get("drums") or []
        i = int(round(row))
        if not self._track or not 0 <= i < len(drums):
            return ""
        return self._add_one("hits", moves.add_hit_call(self.doc, self._track, t, drums[i], grid=self._grid_now, px=px),
                             "Add drum hit")

    @Slot(float, float, float, result=str)
    def drawAt(self, t, row, px=0.0):
        """The Draw tool's click on empty space in the Editor: a note Note ▾ long on that key, or a hit on that drum row,
        in the grid cell under the pointer (`px`: one screen pixel in seconds); one step, selected. Returns the new id
        (a drag on then sets the note's length)."""
        if self._view["roll"].get("kind") == "drums":
            return self.addHit(t, row, px)
        if not self._track:
            return ""
        grid = self._grid_now
        call = moves.add_note_call(self.doc, self._track, t, int(round(row)), beats=self._draw_beats(timing.beat(t, self.doc.data)),
                                   grid=grid, px=px, lock=self.keepInKey)
        return self._draw_note(call, t)

    @Slot(int)
    def playKey(self, key):
        """The Editor's keyboard: a click on a key plays it on the track's own instrument, through the engine
        (rostrum_sound.audition.render_key, cached: the second click is at once). Nothing in the song changes."""
        if not self._track or self._view["roll"].get("kind") != "notes":
            return
        self._auditioner().start({"key": int(key)}, timing.name(int(key)), self._track)

    def _add_one(self, key, call, label):
        before = {x["id"] for x in self.doc.item(self._track).get(key, [])}
        if not self._guard(lambda: self._apply([call], label)):
            return ""
        new = [x["id"] for x in self.doc.item(self._track).get(key, []) if x["id"] not in before]
        if new:                             # its outline now; the settings panel once the click is drawn (`_settle`)
            self._pick(new[:1], later=True)
            self._settle()
        return new[0] if new else ""

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
            self._guard(lambda: self._apply(moves.remove_calls(self.doc, self.doc.item(self._sel)["type"], [self._sel]), "Delete"))

    @Slot(str, result=bool)
    def beginDrag(self, item_id):
        """Press on a note, hit, clip or marker: select it (kept when it is already one of several selected) and
        start one gesture for everything selected."""
        self.endDrag()
        if item_id not in self.selectedIds:
            self._pick([item_id], later=True)         # the outline now; the settings panel when the drag ends

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
    def dragTo(self, dt, dsemi, free, only_time, copy, scale):
        """A drag's move with its keys: free (Ctrl, no snapping), only_time (Shift), copy (Alt, read once, at the
        first move); `scale` = screen px per second: a marker or the playhead within the kit's 6 px catches it (0 = none)."""
        if self._drag is None:
            return
        g = self._grab

        def go():
            if "primary" not in g and g["type"] == "marker":      # the ruler's snap: markers, section edges, grid
                to, caught = self.ruler_snap(g["t"] + dt, free, False, scale, skip=g["id"])
                self._set_snap(caught)
                return self._drag.preview(moves.drag_calls(self.doc, g, to - g["t"], 0, True, self._grid_now))
            if "primary" not in g:
                return self._drag.preview(moves.drag_calls(self.doc, g, dt, dsemi, free, self._grid_now, self.keepInKey))
            root = self.doc.data
            end = timing.sec(root["length"], root) if root.get("length") is not None else None    # a set length: kept inside it
            calls, caught = moves.many_calls(self.doc, g, dt, dsemi, free, only_time, self._snap_targets(), scale,
                                              self._grid_now, end, self.keepInKey)
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
        return [snap.Target("marker", m["name"], m["t"]) for m in self._view["markers"]]             + [snap.Target("playhead", "playhead", self._t)]

    @Slot()
    def endDrag(self):
        dest = getattr(self, "_to_track", "")
        d, g, self._drag, self._grab, self._to_track = self._drag, self._grab, None, None, ""
        self._set_snap({})
        why = moves.track_refusal(self.doc, g, dest) if d is not None and g and "primary" in g else ""
        if d is not None and g and "handle" in g and not g.get("drawn"):      # the step says what it did ("Fade in 0.40 s")
            d._ctx.label = handles.label(self.doc, g["grabs"], g["handle"])
        if d is not None:
            self._guard(lambda: self._done(d.end(), ""))
        if why:                                  # let go over a track that can't hold clips: said, never a silent stay
            self.say(why)
        self._settle()

    @Slot()
    def cancelDrag(self):
        d, self._drag, self._grab = self._drag, None, None
        self._set_snap({})
        if d is not None:
            self._guard(lambda: d.end(cancel=True))
        self._settle()

    @Slot(str, float, bool, result=bool)
    def moveSharedMarker(self, marker_id, dt, free):
        """Release of a drag on one of the project's markers: one `marker.move` through the shared marker list
        (rostrum_gui.markers.MarkerWatch), so it moves for every app and undoes as one step; snapped to a quarter
        beat unless free. The sound follows on the watch's change like any other marker move."""
        row = next((m for m in self._marks.rows() if m["id"] == marker_id), None)
        if row is None or abs(dt) < 1e-6:
            return False
        return self._marks.move(marker_id, timing.snap(row["at"] + dt, self.doc.data, free, self._grid_now))
