"""The keys that move things in time or move the playhead (a slot mix-in for SoundBridge; INTERACTION.md §1.7, Part 2):
arrows nudge the selection (a grid step; Shift a bar; Alt fine, 1/32 beat), ↑ ↓ move notes a half step (Shift an
octave) and clips to the track above / below; Ctrl+← → move the playhead a grid step (Ctrl+Shift ten); `,` / `.`
go to the previous / next thing that happens (of the selection, or of everything); Shift+I / Shift+O set the time
range's ends at the playhead; Shift+L loops the time range; F fits the selection; M adds a marker; F2 renames a
track in place. Nudges under 1 s apart are one undo step (the core merges quick repeats of the same change).
"""
from __future__ import annotations

from PySide6.QtCore import Property, Signal, Slot

from . import action_calls as C
from . import moves, selection, timing


class KeySlots:
    loopChanged = Signal()
    renamingChanged = Signal()

    @Slot(str, int, result=bool)
    def nudge(self, how, sign):
        beats = {"grid": timing.SNAP_BEATS, "bar": float(self.doc.data.get("beatsPerBar", 4)), "fine": 1 / 32}[how]
        by = C.Facts(self.doc, self._picks.ids).by_kind()
        if not by:
            return False
        return self._act([{"op": f"{k}.move", "target": ids, "args": {"by": {"beats": sign * beats}}}
                          for k, ids in by.items()], "Nudge " + self.selectionWords)

    @Slot(int, result=bool)
    def pitchStep(self, semis):
        """↑ ↓: notes by `semis`; clips and designed sounds to the next track up (semis > 0) or down that holds
        them."""
        kinds = set(self._kinds())
        if kinds == {"note"}:
            return self._act([{"op": "note.transpose", "target": self._picks.ids, "args": {"semitones": semis}}],
                             "Transpose " + self.selectionWords)
        if kinds and kinds <= {"clip", "sound"}:
            order = [t["id"] for t in self.doc.data.get("tracks", [])]
            here = order.index(self.doc.parent_of(self._picks.ids[0])[0])
            step = -1 if semis > 0 else 1
            g = {"items": [{"id": i, "type": k} for i, k in zip(self._picks.ids, self._kinds())]}
            for j in range(here + step, -1 if step < 0 else len(order), step):
                calls = moves.track_calls(self.doc, g, order[j])
                if calls:
                    name = self.doc.item(order[j]).get("name") or order[j]
                    return self._act(calls, f"Move {self.selectionWords} to {name}")
            self.say("No track that can hold them " + ("above" if step < 0 else "below"))
        return False

    @Slot(int)
    def playheadStep(self, n):
        """Ctrl+← →: the playhead `n` grid steps (never a change)."""
        beat = timing.beat(self._t, self.doc.data) + n * timing.SNAP_BEATS
        self.setTime(max(0.0, timing.tempo.seconds_at(self.doc.data, max(0.0, beat))))

    @Slot(int)
    def jump(self, sign):
        """`,` / `.`: the playhead to the previous / next start or end of the selection (everything when nothing is
        selected) or a marker."""
        drawn = selection.blocks_by_id(self._view["rows"])
        bs = [drawn[i] for i in self._picks.ids if i in drawn] or list(drawn.values())
        times = {round(b["t"], 4) for b in bs} | {round(b["t"] + b["dur"], 4) for b in bs}
        times |= {round(m["t"], 4) for m in self._view["markers"]}
        ahead = sorted(t for t in times if (t > self._t + 1e-3 if sign > 0 else t < self._t - 1e-3))
        if ahead:
            self.setTime(ahead[0] if sign > 0 else ahead[-1])

    @Slot(str)
    def rangeEdge(self, edge):
        """Shift+I / Shift+O: the time range's start / end at the playhead (the other end kept, or the song's)."""
        a, b = self._picks.range or (0.0, self._length())
        a, b = (self._t, max(b, self._t + 0.01)) if edge == "in" else (min(a, self._t - 0.01), self._t)
        self.setRange(a, b, True)

    # ---- loop (screen state) ----------------------------------------------------------------------------------
    @Property(bool, notify=loopChanged)
    def looping(self):
        return bool(getattr(self, "_loop", False)) and bool(self._picks.range)

    @Property("QVariantList", notify=loopChanged)
    def loopRange(self):
        """[start, end] while ⟳ Loop is on over the time range; [] otherwise."""
        return list(self._picks.range) if self.looping else []

    @Slot()
    def toggleLoop(self):
        """Shift+L: loop the time range on / off (nothing to loop without one: the message line says so)."""
        if not self._picks.range:
            self.say("Loop needs a time range: drag on the ruler's top band")
            return
        self._loop = not getattr(self, "_loop", False)
        self.transport.loop = tuple(self._picks.range) if self._loop else None
        self.loopChanged.emit()

    def _range_moved(self):
        if getattr(self, "_loop", False):
            self.transport.loop = tuple(self._picks.range) if self._picks.range else None
        self.loopChanged.emit()

    @Slot()
    def fitSelection(self):
        """F: zoom so the selection (or the time range) fills the view."""
        e = self.selectionExtent()
        if e:
            self._zoom.fit_to(e["t0"], e["t1"], self._length())
            self.viewChanged.emit()

    @Slot(float, result=bool)
    def markerAt(self, t):
        """M: a marker at `t` (the playhead), "Marker n", with its name field open in place."""
        have = {m["name"] for m in self._view["markers"]}
        n = len(have) + 1
        while f"Marker {n}" in have:
            n += 1
        before = {m["id"] for m in self.doc.data.get("markers", [])}
        done = self._act([{"op": "marker.add", "args": {"name": f"Marker {n}", "at": round(t, 4)}}], "Add marker")
        new = [m["id"] for m in self.doc.data.get("markers", []) if m["id"] not in before]
        if done and new:                                # its name field opens at once (Enter keeps, Esc takes it back)
            self._pick(new)
            self.startRename(new[0])
            self._new_marker = new[0]
        return done

    @Slot(str, result=bool)
    def toggleLock(self, track_id):
        """The header's lock: `track.lock` / `track.unlock` on that track (one step)."""
        op = "track.unlock" if self.doc.item(track_id).get("locked") else "track.lock"
        name = self.doc.item(track_id).get("name") or track_id
        return self._act([{"op": op, "target": [track_id], "args": {}}], f"{'Unlock' if 'un' in op else 'Lock'} {name}")

    # ---- F2: rename a track in place ------------------------------------------------------------------------
    @Property(str, notify=renamingChanged)
    def renaming(self):
        """The id whose name field is open ("" = none)."""
        return getattr(self, "_renaming", "")

    @Slot(str, result=bool)
    def startRename(self, item_id):
        self._renaming = item_id
        self.renamingChanged.emit()
        return True

    @Slot(str, str)
    def finishRename(self, item_id, text):
        """Enter: the new name as one `<kind>.set` (a track, a marker, a section); Esc ("") keeps the old one, and a
        marker just added with M is taken back (Esc cancels the whole thing)."""
        new, self._renaming = getattr(self, "_new_marker", ""), ""
        self._new_marker = ""
        self.renamingChanged.emit()
        name = text.strip()
        if not name and new == item_id and self.doc.has(item_id):
            return self.undo()
        if name and self.doc.has(item_id) and name != (self.doc.item(item_id).get("name") or item_id):
            kind = self.doc.item(item_id)["type"]
            self._act([{"op": f"{kind}.set", "target": [item_id], "args": {"name": name}}], f"Rename to {name}")
