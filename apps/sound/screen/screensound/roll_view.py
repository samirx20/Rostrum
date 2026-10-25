"""The Editor's piano roll of the current track, as rows_view.py makes it (a mix-in of SoundBridge, under RowsView):
its layout (`roll`) and its blocks (`rollBlocks`, JSON text: block_patch.py) each sent only when they changed, a few
changed blocks as a patch (`rollPatched`), the selected ones (`rollPicked`), the playing lane (`rollPlayed`)."""
from __future__ import annotations

from . import block_patch, drum_rows, key_lock, lanes, timeline


def shape(part: dict) -> dict:
    """A row or the roll without its blocks: what lays the screen out (`sound`: it has any)."""
    return {**{k: v for k, v in part.items() if k != "blocks"}, "sound": bool(part.get("blocks"))}


class RollView:
    def _show_roll(self):
        """The Editor shows another track: only the roll is made again, the arrangement's rows stay (rebuilding every
        row on a click cost ~250 ms on a 16-track song, S59)."""
        self._span = ("", 0, 0)                       # another track: its keys are framed afresh
        self._send_roll(self._roll(self._view["rows"]))

    def _send_roll(self, roll):
        """The roll as made: its layout (`roll`) and its blocks (`rollBlocks`) are each sent only when they changed."""
        before, self._view["roll"] = self._view["roll"], roll
        laid, moved = shape(roll), roll.get("blocks") != before.get("blocks")
        laid.pop("played", None)            # the playing lane is its own property (rollPlayed): its points relay nothing
        if roll.get("played") != before.get("played"):
            self.rollPlayedChanged.emit()
        relaid, self._view["rollShape"] = laid != self._view["rollShape"], laid
        if moved:                   # first: what the new layout's handlers read (framing the keys on the notes)
            p = block_patch.diff(before.get("blocks"), roll.get("blocks", []))
            by = self.__dict__.setdefault("_roll_by", {})
            if p:
                for i in p[0]:
                    by.pop(i, None)
                by.update((b["id"], b) for b in p[1])
                self.rollPatched.emit(*p)     # a few: the screen patches the list it shows (block_patch.py)
            else:
                self.__dict__["_roll_by"] = {b["id"]: b for b in roll.get("blocks", [])}
                self.rollBlocksChanged.emit()
            self._roll_picks()
        if relaid:
            self.rollChanged.emit()

    def _played_again(self, root):
        """Only the Editor's playing lane made again (a change no row shows: a point on the track's sustain lane)."""
        roll = self._view.get("roll") or {}
        if roll.get("kind") != "notes" or not self.doc.has(self._track):
            return
        now = lanes.played(self.doc.item(self._track), root, self._play_lane)
        if now != roll.get("played"):
            self._view["roll"] = {**roll, "played": now}
            self.rollPlayedChanged.emit()

    def _roll_picks(self):
        """The roll's selected blocks again (`rollPicked`, after a pick or when the roll's blocks changed), looked up
        by id: a pick or an edit costs the selected blocks, not every block of the track. rollPickedChanged only when
        they read differently."""
        by = self.__dict__.get("_roll_by", {})
        now = [by[i] for i in self._picks.ids if i in by]
        if now != self.__dict__.get("_roll_picked", []):
            self.__dict__["_roll_picked"] = now
            self.rollPickedChanged.emit()

    def _roll(self, rows) -> dict:
        """The Editor's piano roll of the current track (`_track`), in its row's colour."""
        root = self.doc.data
        hue = next((r["hue"] for r in rows if r["id"] == self._track), timeline.HUES[0])
        track = self.doc.item(self._track) if self._track and self.doc.has(self._track) else None
        span = self._span
        roll = timeline.roll(track, root, hue, self._play_lane, keep=span[1:] if span[0] == self._track else None,
                             memo=self._memo)
        drum_rows.extend(roll, self._drum_rows().get(self._track))        # rows asked for with + Drum (drum_rows.py)
        if roll["kind"] == "notes":
            self._span = (self._track, roll["lo"], roll["hi"])      # the keys shown only grow while the track stays open
        self._marks_on([roll])
        return key_lock.fold(roll, root) if self.onlyKeyRows else roll

    def _roll_text(self) -> str:
        """The roll's blocks as the screen receives them whole (block_patch.text, made once per list)."""
        if "_roll_texts" not in self.__dict__:
            self.__dict__["_roll_texts"] = block_patch.Texts()
        return self.__dict__["_roll_texts"].of("roll", self._view["roll"].get("blocks", []))
