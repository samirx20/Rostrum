"""Grid ▾ and Snap in the arrangement's header, and Note ▾ in the Editor's (the length a drawn or double-clicked note gets:
a quarter at first, a length of its own, or the grid step) (a slot mix-in for SoundBridge): screen state, never an undo step,
held here per window (`_grid_now`) and passed to the one snapping code (timing.snap). Auto (the default) follows the
zoom: the finest step at least timing.MIN_PX wide on the narrowest time ruler on screen (each BarRuler reports its width,
setRulerWidth), again on every zoom, scroll and window resize.
"""
from __future__ import annotations

from PySide6.QtCore import Property, Signal, Slot
from rostrum_gui import snap

from . import key_lock, music_map, timing, view_kept
from .timing import Grid

WORDS = {"auto": "Auto", "bar": "Bar", "1/2": "1/2", "beat": "1/4", "1/8": "1/8", "1/16": "1/16", "1/32": "1/32",
         "1/8T": "1/8 triplet", "1/16T": "1/16 triplet"}


NOTE_CHOICES = ["grid", "bar", "1/2", "beat", "1/8", "1/16", "1/32"]
DRAW_CHOICES = [("", "Single notes"), ("key", "Chord in key"), ("major", "Major"), ("minor", "Minor"), ("power", "Power")]


class GridSlots:
    gridChanged = Signal()

    @property
    def _grid_now(self) -> Grid:
        """This window's grid (one per bridge: windows and tests never share it), carrying its markers and section
        edges, so every snap from the screen catches them first (timing.catch)."""
        g = self.__dict__.get("_grid_state")
        if g is None:
            g = self.__dict__["_grid_state"] = Grid()
            g.marks = self._land_marks
            kept = view_kept.read(self.doc.folder, self.doc.item_id).get("tools") or {}     # as the person left them
            if kept.get("grid") in Grid.CHOICES:
                g.value = kept["grid"]
            if kept.get("note") in NOTE_CHOICES:
                self._note_len = kept["note"]
            if kept.get("draw") in {c[0] for c in DRAW_CHOICES}:
                self._draw_chord = kept["draw"]
        return g

    def _keep_tools(self):
        """The Grid, Note ▾ and Draw choices go with the song's view (view_kept.py `tools`)."""
        self._kept_view().keep_tools({"grid": self._grid_now.value, "note": self.noteLength,
                                      "draw": self.__dict__.get("_draw_chord", "")})

    def _land_marks(self, skip=""):
        """What a pointer's time catches before the grid: the markers (`skip`: one being dragged), then the sections'
        starts and ends."""
        marks = [snap.Target("marker", m["name"], m["t"]) for m in self._view["markers"] if m["id"] != skip]
        for s in music_map.sections(self.doc.data):
            marks += [snap.Target("section", s["name"], s["t"]), snap.Target("section", f"{s['name']} end", s["end"])]
        return marks

    @Property(str, notify=gridChanged)
    def grid(self):
        return self._grid_now.value

    @Property(str, notify=gridChanged)
    def gridLabel(self):
        """The Grid button's words: the step chosen; for Auto, the step Auto is on at this zoom ("Auto · 1/8"), read from
        the same Grid the drawing and snapping use."""
        g = self._grid_now
        if g.value != "auto":
            return WORDS[g.value]
        name = next((v for v in ("1/32", "1/16", "1/8", "beat", "1/2") if Grid.STEPS[v] == g.auto_beats), "bar")
        return f"Auto · {WORDS[name]}"

    @Property(bool, notify=gridChanged)
    def snapOn(self):
        return self._grid_now.on

    @Property("QVariantList", notify=gridChanged)
    def gridChoices(self):
        """[{value, label, keys, group, checked}] for the kit's ActionMenu (the current one is ticked)."""
        return [{"value": v, "label": WORDS[v], "keys": "", "group": "auto" if v == "auto" else "steps",
                 "checked": v == self.grid}
                for v in Grid.CHOICES]

    @Slot(str)
    def setGrid(self, value):
        if value not in Grid.CHOICES:
            return self._fail(f'Error: grid: "{value}" is not a grid ({", ".join(Grid.CHOICES)}).')
        self._grid_now.value = value
        self._follow_zoom()
        self._keep_tools()
        self.gridChanged.emit()

    @Property(str, notify=gridChanged)
    def noteLength(self):
        """Note ▾: the length of a drawn or double-clicked note: "beat" (a quarter, at first), "1/8", "bar" … or
        "grid" (one grid step)."""
        return self.__dict__.get("_note_len", "beat")

    @Property("QVariantList", notify=gridChanged)
    def noteLengthChoices(self):
        """Note ▾'s menu: "Note length" (the current one ticked; "One grid step" follows the Grid), then "Draw": what a
        Draw click stamps (Single notes, or a chord: "Chord in key" only while the song has a key)."""
        lengths = [{"value": v, "label": "One grid step" if v == "grid" else WORDS[v], "keys": "",
                    "group": "grid" if v == "grid" else "steps", "checked": v == self.noteLength,
                    **({"heading": "Note length"} if i == 0 else {})} for i, v in enumerate(NOTE_CHOICES)]
        now = self.drawChord
        draw = [{"value": f"draw:{v or 'single'}", "label": label, "keys": "", "group": "draw", "checked": v == now,
                 **({"heading": "Draw"} if i == 0 else {})}
                for i, (v, label) in enumerate(c for c in DRAW_CHOICES if c[0] != "key" or key_lock.has_key(self.doc.data))]
        return lengths + draw

    @Property(str, notify=gridChanged)
    def drawChord(self):
        """What a Draw click stamps: "" (a single note, at first) or a chord shape ("key", "major", "minor", "power");
        screen state per window. "key" counts only while the song has a key."""
        v = self.__dict__.get("_draw_chord", "")
        return "" if v == "key" and not key_lock.has_key(self.doc.data) else v

    @Property(str, notify=gridChanged)
    def noteLabel(self):
        """Note ▾'s words: "Note 1/4", and "Note 1/4 · Chord" when a chord is chosen."""
        n = {"grid": "= grid", "beat": "1/4", "bar": "1 bar"}.get(self.noteLength, self.noteLength)
        return f"Note {n}" + (" · Chord" if self.drawChord else "")

    @Slot(str)
    def setDrawChord(self, value):
        v = "" if value == "single" else value
        if v not in {c[0] for c in DRAW_CHOICES}:
            return self._fail(f'Error: draw: "{value}" is not a Draw choice (single, key, major, minor, power).')
        self._draw_chord = v
        self._keep_tools()
        self.gridChanged.emit()

    @Slot(str)
    def setNoteLength(self, value):
        if value not in NOTE_CHOICES:
            return self._fail(f'Error: note length: "{value}" is not a length ({", ".join(NOTE_CHOICES)}).')
        self._note_len = value
        self._keep_tools()
        self.gridChanged.emit()

    def _draw_beats(self, at_beat: float = 0.0) -> float:
        """How many beats long Draw makes a note: Note ▾'s length, else the grid step."""
        v = self.noteLength
        if v == "grid":
            return self._grid_now.beats(self.doc.data, at_beat)
        g = Grid()
        g.value = v
        return g.beats(self.doc.data, at_beat)

    @Slot(bool)
    def setSnap(self, on):
        self._grid_now.on = bool(on)
        self.gridChanged.emit()

    @Slot()
    def toggleSnap(self):
        self.setSnap(not self._grid_now.on)

    @Slot(str, float)
    def setRulerWidth(self, key, width):
        """A time ruler's width on screen (`key`: which ruler; 0: it is gone or hidden): Auto keeps its steps wide
        enough on the narrowest one."""
        widths = self.__dict__.setdefault("_ruler_widths", {})
        if width > 0:
            widths[key] = float(width)
        else:
            widths.pop(key, None)
        self._follow_zoom()

    def _follow_zoom(self):
        span = self.viewSpan
        beats = span / max(self._view["song"]["spb"], 1e-6) if self._view else 16.0
        width = min(self.__dict__.get("_ruler_widths", {}).values(), default=1200.0)     # (no screen: a common width)
        if self._grid_now.follow_zoom(beats, width) and self._grid_now.value == "auto":
            self.gridChanged.emit()


    # ---- the ruler: a click or scrub puts the playhead on what it catches ---------------------------------------
    @Slot(float, bool, bool, float)
    def setTimeSnapped(self, t, free, seconds_line, scale):
        """The playhead at `t` seconds as the ruler's click or scrub gives it: `free` (Ctrl) or Snap off = exactly
        there; else snapped (ruler_snap). `seconds_line`: on the seconds line; `scale`: the ruler's px per second."""
        at, caught = self.ruler_snap(t, free, seconds_line, scale)
        self._set_snap(caught)
        self.setTime(at)

    @Slot(float, str, result=str)
    def snapWords(self, t, name):
        """The snap line's chip for a drag's `snapLine` ({t, name}: a marker's or section edge's name, "" for the grid):
        "Marker: Flash", "Section: Verse", "Bar 15", "Beat 15.3" (timing.snap_words)."""
        kinds = {m.name: m.kind for m in self._land_marks()}
        return timing.snap_words(t, self.doc.data, name, kinds)

    @Slot()
    def endTimeSnap(self):
        """The ruler's press ended: no snap line."""
        self._set_snap({})

    @Slot(float)
    def setPictureFps(self, fps):
        """The picture's frame rate, as its player reads it (PictureCorner): the seconds line snaps to its frames."""
        self._picture_fps = float(fps or 0)

    def ruler_snap(self, t, free, seconds_line=False, scale=0.0, skip=""):
        """(where a time on the ruler lands, what it caught: {t, name}; {} when free). Markers and section edges
        catch first (the kit's 6 px, strongest first; `skip`: a marker being dragged), then the window's grid ("bar 9",
        "9.3"), or on the seconds line with a picture its nearest whole frame ("frame 120")."""
        root, grid = self.doc.data, self._grid_now
        if free or not grid.on:
            return max(0.0, round(t, 4)), {}
        caught = timing.catch(t, grid, 1.0 / scale if scale > 0 else 0.0, skip)
        if caught is not None:
            return caught.value, {"t": caught.value, "name": caught.name}
        fps = self.__dict__.get("_picture_fps", 0.0)
        if seconds_line and fps > 0 and self.picture:
            at, n = timing.frame(t, self.pictureStart, fps)
            return at, {"t": at, "name": f"frame {n}"}
        at = timing.snap(t, root, False, grid)
        return at, {"t": at, "name": timing.line_name(at, root)}
