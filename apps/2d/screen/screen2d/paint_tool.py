"""The Brush group's five tools (painting design §2.1): Brush B, Eraser E, Fill G, Pick I, Select S. All five are
the canvas's one paint tool ("draw"); which one is on is read from the parts that do the work, so they never disagree:
the brush's mode (erase), Fill (filler.py), Pick (paint_pick.py, armed) and Select strokes (stroke_select.py, armed).
`now` is what the rail's Brush icon shows (its last-used tool) and the brush panel's top row highlights.
Screen state, never a document change. A QObject part, read in QML as `backend.paintTool`.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

TOOLS = ("brush", "eraser", "fill", "pick", "select")


class PaintTool(QObject):
    changed = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.b, self._mode = bridge, "normal"          # the brush's own mode, back when the Eraser goes off
        for part in (bridge.fill, bridge.colourPick, bridge.strokeSelect):
            part.changed.connect(self.changed)
        bridge.painter.brushChanged.connect(self.changed)
        bridge.toolChanged.connect(self.changed)

    @Property(str, notify=changed)
    def now(self):
        if self.b.strokeSelect.armed:
            return "select"
        if self.b.colourPick.armed:
            return "pick"
        if self.b.fill.on:
            return "fill"
        return "eraser" if self.b.painter.brush.values.get("mode") == "erase" else "brush"

    @Slot(str)
    def use(self, name):
        """The paint tool `name` goes on (and the canvas's tool is paint); the other four go off."""
        if name not in TOOLS:
            raise ValueError(f"no paint tool {name!r}: {', '.join(TOOLS)}")
        self.b.setTool("draw")
        mode = self.b.painter.brush.values.get("mode")
        if name == "eraser" and mode != "erase":
            self._mode = mode
            self.b.painter.setValue("mode", "erase")
        elif name != "eraser" and mode == "erase":
            self.b.painter.setValue("mode", self._mode)
        self.b.fill.setOn(name == "fill")
        self.b.colourPick.arm(name == "pick")
        self.b.strokeSelect.arm(name == "select")
        self.changed.emit()
