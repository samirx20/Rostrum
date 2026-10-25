"""Grid ▾ and Snap in the arrangement's header, and Note ▾ in the Editor's (the length a drawn or double-clicked note gets:
a quarter at first, a length of its own, or the grid step) (a slot mix-in for SoundBridge): screen state, never an undo step,
held here per window (`_grid_now`) and passed to the one snapping code (timing.snap). Auto (the default) follows the
zoom: the finest step at least timing.MIN_PX wide on the narrowest time ruler on screen (each BarRuler reports its width,
setRulerWidth), again on every zoom, scroll and window resize.
"""
from __future__ import annotations

from PySide6.QtCore import Property, Signal, Slot

from .timing import Grid

WORDS = {"auto": "Auto", "bar": "Bar", "1/2": "1/2", "beat": "1/4", "1/8": "1/8", "1/16": "1/16", "1/32": "1/32",
         "1/8T": "1/8 triplet", "1/16T": "1/16 triplet"}


NOTE_CHOICES = ["grid", "bar", "1/2", "beat", "1/8", "1/16", "1/32"]


class GridSlots:
    gridChanged = Signal()

    @property
    def _grid_now(self) -> Grid:
        """This window's grid (one per bridge: windows and tests never share it)."""
        return self.__dict__.setdefault("_grid_state", Grid())

    @Property(str, notify=gridChanged)
    def grid(self):
        return self._grid_now.value

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
        self.gridChanged.emit()

    @Property(str, notify=gridChanged)
    def noteLength(self):
        """Note ▾: the length of a drawn or double-clicked note: "beat" (a quarter, at first), "1/8", "bar" … or
        "grid" (one grid step)."""
        return self.__dict__.get("_note_len", "beat")

    @Property("QVariantList", notify=gridChanged)
    def noteLengthChoices(self):
        """Note ▾'s menu, headed "Note length", the current length ticked ("One grid step" follows the Grid)."""
        return [{"value": v, "label": "One grid step" if v == "grid" else WORDS[v], "keys": "",
                 "group": "grid" if v == "grid" else "steps", "checked": v == self.noteLength,
                 **({"heading": "Note length"} if i == 0 else {})} for i, v in enumerate(NOTE_CHOICES)]

    @Slot(str)
    def setNoteLength(self, value):
        if value not in NOTE_CHOICES:
            return self._fail(f'Error: note length: "{value}" is not a length ({", ".join(NOTE_CHOICES)}).')
        self._note_len = value
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
