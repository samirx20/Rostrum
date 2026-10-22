"""Grid ▾ and Snap in the arrangement's header (a slot mix-in for SoundBridge): screen state, never an undo step,
read by the one snapping code (timing.GRID). Auto follows the zoom (the finest step at least 16 px wide).
"""
from __future__ import annotations

from PySide6.QtCore import Property, Signal, Slot

from .timing import GRID, Grid

WORDS = {"auto": "Auto", "bar": "Bar", "beat": "Beat", "1/8": "1/8", "1/16": "1/16", "1/32": "1/32",
         "1/8T": "1/8 triplets", "1/16T": "1/16 triplets"}


class GridSlots:
    gridChanged = Signal()

    @Property(str, notify=gridChanged)
    def grid(self):
        return GRID.value

    @Property(bool, notify=gridChanged)
    def snapOn(self):
        return GRID.on

    @Property("QVariantList", constant=True)
    def gridChoices(self):
        """[{value, label, keys, group}] for the kit's ActionMenu."""
        return [{"value": v, "label": WORDS[v], "keys": "", "group": "auto" if v == "auto" else "steps"}
                for v in Grid.CHOICES]

    @Slot(str)
    def setGrid(self, value):
        if value not in Grid.CHOICES:
            return self._fail(f'Error: grid: "{value}" is not a grid ({", ".join(Grid.CHOICES)}).')
        GRID.value = value
        self._follow_zoom()
        self.gridChanged.emit()

    @Slot(bool)
    def setSnap(self, on):
        GRID.on = bool(on)
        self.gridChanged.emit()

    def _follow_zoom(self):
        span = self.viewSpan
        beats = span / max(self._view["song"]["spb"], 1e-6) if self._view else 16.0
        GRID.follow_zoom(beats)
