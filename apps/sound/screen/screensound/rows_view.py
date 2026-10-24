"""What the arrangement and the Editor's roll show, made from the song (a mix-in for SoundBridge, see gui-kit parts.py):
the rows (timeline.py), the markers, the song's length and grid, the roll of the current track.

A change that touched only tracks, and every step of a drag, makes again only the rows of the tracks it changed
(stepped.py: the document is never changed in place, so an untouched track is the very same object); anything else
makes everything again (`_rebuild`). The row model (`trackRows`) then signals only the rows that changed.
"""
from __future__ import annotations

from . import lanes, stepped, timeline, voice_card, voice_takes


class RowsView:
    def _show_roll(self):
        """The Editor shows another track: only the roll is made again, the arrangement's rows stay (rebuilding every
        row on a click cost ~250 ms on a 16-track song, S59)."""
        self._span = ("", 0, 0)                       # another track: its keys are framed afresh
        self._view["roll"] = self._roll(self._view["rows"])
        self.rollChanged.emit()

    def _lanes_now(self) -> dict:
        root = self.doc.data
        return {k: v for k, v in self._open.items() if self.doc.has(k) and v in lanes.applicable(self.doc.item(k), root)}

    def _rebuild(self):
        root = self.doc.data
        self._open = self._lanes_now()
        tracks = timeline.track_rows(root, self._open)
        rows = timeline.arrange(root, tracks, self._open, self._folded)
        self._marks_on(rows)
        self._made, self._shown = {t["id"]: t for t in tracks}, root
        marks = timeline.markers(root)
        self._view = {"rows": rows, "markers": marks, "song": timeline.song(root, tracks, marks), "roll": self._roll(rows)}
        self._tv.setLength(self._length())        # the view is the person's: nothing new on screen zooms or scrolls it
        self.songChanged.emit()
        self.timelineChanged.emit()
        self.markersChanged.emit()
        self._lanes.update([{"id": r["id"], "track": r} for r in rows], instant=True)   # after: `tracks` is new for the rows made
        self.rollChanged.emit()
        self.viewChanged.emit()

    def _drag_step(self, change=False):
        """A drag's step, or a change that touched only tracks (a drag's drop, an edit on a note, undo of one): only
        the rows of the tracks it changed are made again and sent (the row model signals just those), the roll only
        when its track is one, the song only when its length moved. A step leaves the list `tracks` as it was; a
        change sends it (timelineChanged). Anything else (a marker, the tempo, tracks added …): everything (_rebuild)."""
        root = self.doc.data
        changed = stepped.changed_tracks(self._shown, root)
        if changed is None or (change and self._lanes_now() != self._open):
            return self._rebuild()
        made = {k: v for k, v in self._made.items() if k not in changed}
        tracks = timeline.track_rows(root, self._open, made)
        rows = timeline.arrange(root, tracks, self._open, self._folded)
        self._marks_on([t for t in tracks if t["id"] in changed])
        self._made, self._shown = {t["id"]: t for t in tracks}, root
        self._view["rows"] = rows
        song = timeline.song(root, tracks, self._view["markers"])
        if song != self._view["song"]:
            self._view["song"] = song
            self._tv.setLength(self._length())
            self.songChanged.emit()
        if change:
            self.timelineChanged.emit()
        self._lanes.update([{"id": r["id"], "track": r} for r in rows], instant=True)
        if self._track in changed:
            self._view["roll"] = self._roll(rows)
            self.rollChanged.emit()

    def _roll(self, rows) -> dict:
        """The Editor's piano roll of the current track (`_track`), in its row's colour."""
        root = self.doc.data
        hue = next((r["hue"] for r in rows if r["id"] == self._track), timeline.HUES[0])
        track = self.doc.item(self._track) if self._track and self.doc.has(self._track) else None
        span = self._span
        roll = timeline.roll(track, root, hue, self._play_lane, keep=span[1:] if span[0] == self._track else None)
        if roll["kind"] == "notes":
            self._span = (self._track, roll["lo"], roll["hi"])      # the keys shown only grow while the track stays open
        self._marks_on([roll])
        return roll

    def _marks_on(self, rows):
        side = getattr(self, "side", None)               # lines being spoken say so on their blocks
        if side:
            voice_card.mark_speaking(rows, side.voice.making())
            voice_card.mark_waiting(rows, side.voice.waiting())
            voice_takes.mark_takes(rows, self.doc.data)

