"""What the arrangement and the Editor's roll show, made from the song (a mix-in for SoundBridge, see gui-kit parts.py):
the rows (timeline.py), the markers, the song's length and grid, the roll of the current track.

A change that touched only tracks, and every step of a drag, makes again only the rows of the tracks it changed
(stepped.py: the document is never changed in place, so an untouched track is the very same object); anything else
makes everything again (`_rebuild`). The row model (`trackRows`) then signals only the rows that changed.

What a row or the roll holds is sent in two parts (`shape`): its layout (name, kind, hue, lane, key range …) and its
blocks. A note or a hit added, moved or undone changes only the blocks: only that row's or the roll's blocks are
sent and painted again; the arrangement's layout (`tracks`), the headers and the Editor's header are told nothing.
Each read of a QML map or list property copies all of it, so a song's every block re-read by every layout binding
on each click cost 50-150 ms on a 31-s song (M4, sound-r4).
"""
from __future__ import annotations

from . import block_patch, lanes, stepped, timeline, voice_card, voice_takes
from .block_memo import BlockMemo


MIX_FIELDS = frozenset({"volume", "pan", "reverb", "output"})


def shape(part: dict) -> dict:
    """A row or the roll without its blocks: what lays the screen out (`sound`: it has any)."""
    return {**{k: v for k, v in part.items() if k != "blocks"}, "sound": bool(part.get("blocks"))}




class RowsView:
    @property
    def _memo(self) -> BlockMemo:
        """Each note's and hit's block, made once while it stays the same item (block_memo.py)."""
        if "_memo_" not in self.__dict__:
            self.__dict__["_memo_"] = BlockMemo()
        return self.__dict__["_memo_"]

    def _send_rows(self, rows, before):
        """The row model's rows (the layout and the blocks as two roles, so a block change signals only `blocks`);
        a small block change goes as a patch instead (block_patch.py). `before`: the rows the screen shows (None:
        every row whole, as after tracks came, went or moved)."""
        held, patches, resets = self._held.send(rows, before)
        self._lanes.update([{"id": r["id"], "track": shape(r), "blocks": held[r["id"]]} for r in rows], instant=True)
        for k in resets:
            self.blocksReset.emit(k)
        for k, gone, put in patches:
            self.blocksPatched.emit(k, gone, put)

    def rows_now(self) -> list[dict]:
        """The arrangement's rows with their blocks, as made (QML's `tracks` is their layout only)."""
        return self._view["rows"]

    def _show_roll(self):
        """The Editor shows another track: only the roll is made again, the arrangement's rows stay (rebuilding every
        row on a click cost ~250 ms on a 16-track song, S59)."""
        self._span = ("", 0, 0)                       # another track: its keys are framed afresh
        self._send_roll(self._roll(self._view["rows"]))

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
        self._open = self._lanes_now()
        ids = {t["id"] for t in root.get("tracks", [])}
        kept = self._memo.follow(timeline.clock(root), ids)
        made = (stepped.kept_rows(self._shown, root, self._made, was, self._open)
                if kept and old and self._shown is not root else {})
        tracks = timeline.track_rows(root, self._open, made, self._memo)
        rows = timeline.arrange(root, tracks, self._open, self._folded)
        self._marks_on([t for t in tracks if t["id"] not in made])
        self._made, self._shown = {t["id"]: t for t in tracks}, root
        marks = timeline.markers(root)
        song = timeline.song(root, tracks, marks)
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
        self._send_rows(rows, None)                 # after: `tracks` is new for the rows made
        self._send_roll(self._roll(rows))           # its blocks, then its layout, each only when it changed

    def _drag_step(self, change=False):
        """A drag's step, or a change that touched only tracks (a drag's drop, an edit on a note, undo of one): only
        the rows of the tracks it changed are made again and sent (the row model signals just those), the roll only
        when its track is one, the song only when its length moved. The layout `tracks` is sent only when a row's
        layout moved (timelineChanged: its settings, or a note dragged past its key span). Anything else (a marker, the tempo, tracks
        added …): everything (_rebuild)."""
        root = self.doc.data
        if self._mix_only(root):
            self._shown = root
            return
        changed = stepped.changed_tracks(self._shown, root)
        if changed is None or (change and self._lanes_now() != self._open):
            return self._rebuild()
        made = {k: v for k, v in self._made.items() if k not in changed}
        tracks = timeline.track_rows(root, self._open, made, self._memo)
        rows = timeline.arrange(root, tracks, self._open, self._folded)
        self._marks_on([t for t in tracks if t["id"] in changed])
        self._made, self._shown = {t["id"]: t for t in tracks}, root
        before = self._view["rows"]
        same = rows == before                         # a fader or a pan moves no row: the screen is told nothing
        self._view["rows"] = rows
        if timeline.song_length(root, tracks, self._view["markers"]) != self._view["song"]["length"]:
            self._view["song"] = timeline.song(root, tracks, self._view["markers"])   # the rest follows the tempo
            self._tv.setLength(self._length())
            self.songChanged.emit()
        if same:
            return
        laid = [shape(r) for r in rows]               # the layout: only when a row's own settings or span moved
        if laid != self._view["shape"]:
            self._view["shape"] = laid
            self.timelineChanged.emit()
        self._send_rows(rows, before)
        if self._track in changed:
            self._send_roll(self._roll(rows))

    def _send_roll(self, roll):
        """The roll as made: its layout (`roll`) and its blocks (`rollBlocks`) are each sent only when they changed."""
        before, self._view["roll"] = self._view["roll"], roll
        laid, moved = shape(roll), roll.get("blocks") != before.get("blocks")
        relaid, self._view["rollShape"] = laid != self._view["rollShape"], laid
        if moved:                   # first: what the new layout's handlers read (framing the keys on the notes)
            p = block_patch.diff(before.get("blocks"), roll.get("blocks", []))
            if p:
                self.rollPatched.emit(*p)     # a few: the screen patches the list it shows (block_patch.py)
            else:
                self.rollBlocksChanged.emit()
        if relaid:
            self.rollChanged.emit()

    def _mix_only(self, root) -> bool:
        """The change (or step) set only a track's own level, pan, reverb or output, and no lane is open: no row,
        block or roll shows those, so the screen is told nothing (touched.py)."""
        t = self._kit.touched
        return (t is not None and not t.structural and bool(t.fields) and not self._open and self._shown is not None
                and all(f in MIX_FIELDS and self.doc.has(i) and self.doc.item(i)["type"] == "track" for i, f in t.fields))

    def _roll(self, rows) -> dict:
        """The Editor's piano roll of the current track (`_track`), in its row's colour."""
        root = self.doc.data
        hue = next((r["hue"] for r in rows if r["id"] == self._track), timeline.HUES[0])
        track = self.doc.item(self._track) if self._track and self.doc.has(self._track) else None
        span = self._span
        roll = timeline.roll(track, root, hue, self._play_lane, keep=span[1:] if span[0] == self._track else None,
                             memo=self._memo)
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

