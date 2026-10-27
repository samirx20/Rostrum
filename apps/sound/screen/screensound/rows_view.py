"""What the arrangement and the Editor's roll show, made from the song (a mix-in for SoundBridge, see gui-kit parts.py):
the rows (timeline.py), the markers, the song's length and grid, the roll of the current track (roll_view.py).

A change that touched only tracks, and every step of a drag, makes again only the rows of the tracks it changed
(stepped.py: the document is never changed in place, so an untouched track is the very same object); anything else
makes everything again (`_rebuild`). The row model (`trackRows`) then signals only the rows that changed.

What a row or the roll holds is sent in two parts (`shape`): its layout (name, kind, hue, lane, key range …) and its
blocks (a whole list as JSON text, block_patch.py). A note or a hit added, moved or undone changes only the blocks: only that row's or the roll's blocks are
sent and painted again; the arrangement's layout (`tracks`), the headers and the Editor's header are told nothing.
Each read of a QML map or list property copies all of it, so a song's every block re-read by every layout binding
on each click cost 50-150 ms on a 31-s song (M4, sound-r4).

A drag's step that re-times the whole song (the tempo dragged, a tempo change, a section or a marker moved: the song's
clock moved, so every block is made again) shows the song's own parts at once (the ruler's grid and tempos, the
sections, the markers: `_clock_step`), and the rows when the pointer rests (REST_MS without a step) and at the drop,
never on each move: making and sending every block cost ~400 ms a move on a 3-minute 8-track song, so the tempo
being dragged stuck.
The blocks placed in beats go to the screen in beats (block_patch.seen) and are re-timed there from the tempo map
the rows were made under (`blocksTempo`, Blocks.js `timed`, Tempo.js): a change of the tempo makes the rows here
again (every reader of `rows_now` needs their seconds) but sends only the rows whose text changed (clips in seconds),
and the screen re-times and paints the rest itself (sending every row again cost ~150-250 ms).
"""
from __future__ import annotations

from PySide6.QtCore import QTimer

from . import lanes, stepped, timeline, voice_card, voice_takes
from .block_memo import BlockMemo
from .roll_view import RollView, shape


MIX_FIELDS = frozenset({"volume", "pan", "reverb", "output"})
REST_MS = 120           # a drag's re-timing steps are drawn once the pointer stays this long (and at the drop)


class RowsView(RollView):
    @property
    def _memo(self) -> BlockMemo:
        """Each note's and hit's block, made once while it stays the same item (block_memo.py)."""
        if "_memo_" not in self.__dict__:
            self.__dict__["_memo_"] = BlockMemo()
        return self.__dict__["_memo_"]

    @property
    def _rest(self) -> QTimer:
        """Draws a drag's re-timing step once the pointer rests (`_drag_step`)."""
        if "_rest_" not in self.__dict__:
            t = QTimer(self)
            t.setSingleShot(True)
            t.setInterval(REST_MS)
            t.timeout.connect(lambda: self._guard(self._at_rest))
            self.__dict__["_rest_"] = t
        return self.__dict__["_rest_"]

    def _at_rest(self):
        if self.doc.data is not self._shown:      # (the drop or a cancel may have drawn it already)
            self._rebuild()

    def _send_rows(self, rows):
        """The row model's rows (the layout and the blocks as two roles, so a block change signals only `blocks`);
        a block change goes as a patch instead (block_patch.py; rows that came, went or moved: whole)."""
        held, patches, resets, backs = self._held.send(rows)
        self._lanes.update([{"id": r["id"], "track": shape(r), "blocks": held[r["id"]]} for r in rows], instant=True)
        for k in resets:
            self.blocksReset.emit(k)
        for k in backs:
            self.blocksBack.emit(k)
        for k, p in patches:
            self.blocksPatched.emit(k, p)
        self._rows_sent()                           # the selected blocks' rows (select_slots: Picks.js)

    def rows_now(self) -> list[dict]:
        """The arrangement's rows with their blocks, as made (QML's `tracks` is their layout only)."""
        return self._view["rows"]

    def _lanes_now(self) -> dict:
        root = self.doc.data
        return {k: v for k, v in self._open.items() if self.doc.has(k) and v in lanes.applicable(self.doc.item(k), root)}

    def _rebuild(self):
        """Everything made again, and each part of the screen told only when its part changed. The blocks are kept
        while the song's clock stayed (block_memo.py: a track added, removed or moved keeps the others'); after a
        change to the document, a row whose track is the same object in the same place with the same lane open is
        taken as it was (as a drag's step does). A rebuild with the document as it was (a lane opened, a take made,
        a line spoken) makes every row again: what they show changed outside the song."""
        root, was, old = self.doc.data, self._open, self._view
        if "_rest_" in self.__dict__:
            self._rest.stop()
        self._open = self._lanes_now()
        ids = {t["id"] for t in root.get("tracks", [])}
        kept = self._memo.follow(timeline.clock(root), ids)
        made = (stepped.kept_rows(self._shown, root, self._made, was, self._open)
                if kept and old and self._shown is not root else {})
        tracks = timeline.track_rows(root, self._open, made, self._memo)
        rows = timeline.arrange(root, tracks, self._open, self._folded)
        self._marks_on([t for t in tracks if t["id"] not in made])
        self._made, self._shown, self._clocked = {t["id"]: t for t in tracks}, root, False
        marks = timeline.markers(root)
        song = timeline.song(root, tracks, marks, self._memo, self._picture_end())
        laid = [shape(r) for r in rows]
        self._view = {"rows": rows, "shape": laid, "markers": marks, "song": song,
                      "roll": old.get("roll", {}), "rollShape": old.get("rollShape")}
        self._tv.setLength(self._length())        # the view is the person's: nothing new on screen zooms or scrolls it
        if song != old.get("song"):
            self.songChanged.emit()
            self.viewChanged.emit()
        if laid != old.get("shape"):
            self.timelineChanged.emit()
        if not kept:
            self.pictureChanged.emit()
        if marks != old.get("markers"):
            self.markersChanged.emit()
        self._place_by(song)
        self._send_rows(rows)                       # after: `tracks` is new for the rows made
        self._send_roll(self._roll(rows))           # its blocks, then its layout, each only when it changed

    def _drag_step(self, change=False):
        """A drag's step, or a change that touched only tracks (a drag's drop, an edit on a note, undo of one): only
        the rows of the tracks it changed are made again and sent (the row model signals just those), the roll only
        when its track is one, the song only when its length moved. The layout `tracks` is sent only when a row's
        layout moved (timelineChanged: its settings, or a note dragged past its key span). Anything else (a marker, the tempo, tracks
        added …): everything (_rebuild); a drag's step that re-times every block, once the pointer rests (REST_MS)."""
        root = self.doc.data
        if self._mix_only(root):
            self._shown = root
            return
        relaid = change and self._lanes_now() != self._open
        # the ruler still shows a drag's step of the clock (_clock_step; _rebuild clears it): a cancelled clock drag
        # (Esc) brings back the very song the rows show, but the ruler, sections and flags must come back too
        if root is self._shown and self.__dict__.get("_clocked"):
            return self._rebuild()
        if root is self._shown and not relaid:    # a drag's drop: its last step already shows this very song
            return
        changed = stepped.changed_tracks(self._shown, root)
        if changed is None or relaid:
            if self._stepping and not relaid and not self._memo.keeps(timeline.clock(root)):
                return self._clock_step()         # every block re-timed: the rows when the pointer rests (above)
            return self._rebuild()
        made = {k: v for k, v in self._made.items() if k not in changed}
        tracks = timeline.track_rows(root, self._open, made, self._memo)
        rows = timeline.arrange(root, tracks, self._open, self._folded)
        self._marks_on([t for t in tracks if t["id"] in changed])
        self._made, self._shown = {t["id"]: t for t in tracks}, root
        before = self._view["rows"]
        same = rows == before                         # a fader or a pan moves no row: the screen is told nothing
        self._view["rows"] = rows
        if timeline.song_length(root, tracks, self._view["markers"], self._memo, self._picture_end()) != self._view["song"]["length"]:
            self._view["song"] = timeline.song(root, tracks, self._view["markers"], self._memo, self._picture_end())   # the rest follows the tempo
            self._tv.setLength(self._length())
            self.songChanged.emit()
            self._place_by(self._view["song"])
        if same:            # (the rows draw nothing of it, but the Editor's playing lane may: a point added or dragged)
            if self._track in changed:
                self._played_again(root)
            return
        laid = [shape(r) for r in rows]               # the layout: only when a row's own settings or span moved
        if laid != self._view["shape"]:
            self._view["shape"] = laid
            self.timelineChanged.emit()
        self._send_rows(rows)
        if self._track in changed:
            self._send_roll(self._roll(rows))

    def _clock_step(self):
        """A drag's step that moved the song's clock: the ruler (grid, tempos), the sections and the markers follow
        now; the rows, the roll and the view's length once the pointer rests or at the drop (`_rest`): a view fitted
        to the song would zoom on every move, painting every row whole again for rows not yet re-timed."""
        root = self.doc.data
        marks = timeline.markers(root)
        song = timeline.song(root, list(self._made.values()), marks, self._memo, self._picture_end())
        if marks != self._view["markers"]:
            self._view["markers"] = marks
            self.markersChanged.emit()
        if song != self._view["song"]:
            self._view["song"] = song
            self._clocked = True
            self.songChanged.emit()
        self._rest.start()

    def _mix_only(self, root) -> bool:
        """The change (or step) set only a track's own level, pan, reverb or output, and no lane is open: no row,
        block or roll shows those, so the screen is told nothing (touched.py)."""
        t = self._kit.touched
        return (t is not None and not t.structural and bool(t.fields) and not self._open and self._shown is not None
                and all(f in MIX_FIELDS and self.doc.has(i) and self.doc.item(i)["type"] == "track" for i, f in t.fields))

    def _marks_on(self, rows):
        side = getattr(self, "side", None)               # lines being spoken say so on their blocks
        if side:
            voice_card.mark_speaking(rows, side.voice.making())
            voice_card.mark_waiting(rows, side.voice.waiting())
            voice_takes.mark_takes(rows, self.doc.data)

