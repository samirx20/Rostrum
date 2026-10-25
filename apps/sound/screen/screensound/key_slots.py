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
from rostrum_sound.doc import meter

from . import moves, scale_step, selection, timing


class KeySlots:
    loopChanged = Signal()
    renamingChanged = Signal()
    toolChanged = Signal()

    @Property(str, notify=toolChanged)
    def tool(self):
        """The Editor's tool: "select" (V: click picks, drag moves, box) or "draw" (B: a click on empty space adds a
        note or a hit; a drag sets the note's length). Screen state."""
        return getattr(self, "_tool", "select")

    @Slot(str)
    def setTool(self, name):
        if name not in ("select", "draw"):
            return self._fail(f'Error: tool: "{name}" is not a tool (select, draw).')
        self._tool = name
        self.toolChanged.emit()

    @Slot(str, int, result=bool)
    def nudge(self, how, sign):
        beats = {"grid": timing.step_beats(self.doc.data, self._grid_now), "bar": meter.bar_length_beats(self.doc.data, timing.beat(self._t, self.doc.data)), "fine": 1 / 32}[how]
        if self._apt:                                   # a lane's point selected: the arrows move it (lane_slots)
            return self._nudge_point(beats=sign * beats)
        f = C.Facts(self.doc, self._picks.ids)
        if not f.by_kind():
            return False
        calls = C.nudge(f, sign * beats)
        if not calls:
            self._refuse("Already at the start of the song: it can't move earlier")
            return False
        return self._act(calls, "Nudge " + f.words())

    @Slot(int, result=bool)
    def pitchStep(self, semis):
        """↑ ↓: the selected notes by `semis` (in a mixed selection, its notes: Facts.words); a selection of only
        clips to the next track up (semis > 0) or down that holds them; a lane's selected point up or down (Shift: five
        times as far); anything else says so."""
        if self._apt:
            return self._nudge_point(steps=(1 if semis > 0 else -1) * (5 if abs(semis) > 1 else 1))
        f = C.Facts(self.doc, self._picks.ids)
        notes = f.by_kind(("note",)).get("note")
        if notes:
            return self._act([{"op": "note.transpose", "target": notes, "args": {"semitones": semis}}],
                             "Transpose " + f.words(("note",)))
        if f.kinds != {"clip"}:
            self._refuse("↑ / ↓ move notes a half step, or clips to another track: " +
                         ("select some first" if not f.count else "no notes or clips are selected"))
            return False
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

    @Slot(int, result=bool)
    def pitchScaleStep(self, sign):
        """Ctrl+↑ ↓: notes one step up / down the song's key; says why when it can't (no notes, no key)."""
        notes = C.Facts(self.doc, self._picks.ids).by_kind(("note",)).get("note")
        if not notes:
            self._refuse("Pitch up or down a scale step works on notes: " +
                         ("select some first" if not self._picks.ids else "no notes are selected"))
            return False
        key = scale_step.song_key(self.doc.data, self._t)
        if not key:
            self._refuse("Pitch by a scale step needs the song's key: set it in the header (the key next to the tempo)")
            return False
        calls = scale_step.calls(self.doc, notes, key, sign)
        way = "up" if sign > 0 else "down"
        return bool(calls) and self._act(calls, f"Pitch {way} a scale step in {key} · {C.Facts(self.doc, notes).words()}")

    @Slot(int)
    def playheadStep(self, n):
        """Ctrl+← →: the playhead `n` grid steps (never a change)."""
        beat = timing.beat(self._t, self.doc.data) + n * timing.step_beats(self.doc.data, self._grid_now)
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

    @Slot(int)
    def markerJump(self, sign):
        """Alt+M / Alt+Shift+M: the playhead to the next / previous marker (a clear word when there is none)."""
        ahead = sorted(m["t"] for m in self._view["markers"] if (m["t"] > self._t + 1e-3 if sign > 0 else m["t"] < self._t - 1e-3))
        if not ahead:
            return self.say("No " + ("next" if sign > 0 else "earlier") + " marker")
        self.setTime(ahead[0] if sign > 0 else ahead[-1])

    @Slot()
    def toEnd(self):
        """End: the playhead to the end of the song."""
        self.setTime(self._length())

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
        """Shift+L, or the loop button: loop on / off. With no time range, turning it on makes one: the selection's
        span, else the bar at the playhead and the next three (it shows on the ruler, its edges drag)."""
        if getattr(self, "_loop", False):
            self._loop = False
        else:
            if not self._picks.range:
                a, b = self._default_loop()
                self._set_range(a, b, True, False)
                if not self._picks.range:
                    return self.say("Loop needs a time range: drag on the ruler's top band")
            self._loop = True
        self.transport.loop = tuple(self._picks.range) if self._loop else None
        self.loopChanged.emit()

    def _default_loop(self):
        e = self.selectionExtent()
        if e and e["t1"] - e["t0"] > 1e-3 and not (e.get("tracks") and e["t1"] - e["t0"] >= self._length() - 1e-3):
            return e["t0"], e["t1"]
        bars = list(self._view["song"]["bars"]) or [0.0]
        i = max((k for k, t in enumerate(bars) if t <= self._t + 1e-6), default=0)
        return bars[i], bars[i + 4] if i + 4 < len(bars) else self._length()

    # ---- click (the metronome; screen state) ------------------------------------------------------------------
    @Property(bool, notify=loopChanged)
    def clickOn(self):
        return bool(self.transport.player.state.get("metronome"))

    @Slot()
    def toggleClick(self):
        """Shift+K, or Click beside play: the engine's metronome on / off (it clicks every beat while playing)."""
        self.transport.player.set_state(metronome=not self.clickOn)
        self.loopChanged.emit()

    def _range_moved(self):
        if getattr(self, "_loop", False):
            self._loop = bool(self._picks.range)          # clearing the range ends the loop
            self.transport.loop = tuple(self._picks.range) if self._loop else None
        self.loopChanged.emit()

    @Slot()
    def fitSelection(self):
        """F: zoom so the selection (or the time range) fills the view."""
        e = self.selectionExtent()
        if e:
            self._tv.fitTo(e["t0"], e["t1"])

    @Slot()
    def markerHere(self):
        """M (the key map's `marker`): a marker at the playhead."""
        self.markerAt(self._t)

    @Slot(str)
    def dock(self, name):
        """E / X / Ctrl+L (the key map): the Editor or Mixer dock, or the Library, open / closed."""
        self.workspace.toggleLibrary() if name == "library" else self.workspace.toggleDock(name)

    @Slot(float, result=bool)
    def markerAt(self, t):
        """M: a marker at `t` (the playhead), "Marker n", with its name field open in place. One is there already:
        that one is selected and the line says so (never a second marker on the same spot)."""
        there = next((m for m in self._view["markers"] if not m.get("named") and abs(m["t"] - t) < 1e-3), None)
        if there is not None:
            self._pick([there["id"]])
            self.say(f"A marker is already here: “{there['name']}” (selected). F2 renames it")
            return False
        have = {m["name"] for m in self._view["markers"]}
        n = len(have) + 1
        while f"Marker {n}" in have:
            n += 1
        before = {m["id"] for m in self.doc.data.get("markers", [])}
        done = self._act([{"op": "marker.add", "args": {"name": f"Marker {n}", "at": round(t, 4)}}], "Add marker")
        new = [m["id"] for m in self.doc.data.get("markers", []) if m["id"] not in before]
        if done and new:                                # its name field opens at once (Enter keeps a new name, Esc the one it has)
            self._pick(new)
            self.startRename(new[0])
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
        """Enter: the new name as one `<kind>.set` (a track, a marker, a section); Esc ("") keeps the old one (a
        marker just added with M stays, with the name it was given: Esc cancels the renaming, not the marker; Ctrl+Z
        takes the marker back)."""
        self._renaming = ""
        self.renamingChanged.emit()
        name = text.strip()
        if name and self.doc.has(item_id) and name != (self.doc.item(item_id).get("name") or item_id):
            kind = self.doc.item(item_id)["type"]
            self._act([{"op": f"{kind}.set", "target": [item_id], "args": {"name": name}}], f"Rename to {name}")
