"""Alt measuring as QML sees it (backend.measure, MeasureMarks.qml; CANVAS.md §2 row 23): with exactly one layer picked
and the Move tool on, holding Alt shows red lines and numbers from it to the layer under the pointer, or to the frame's
edges over nothing (or over the picked layer itself). The maths is measure.py; the boxes are the picture on screen's
(shown_boxes, as the outlines), the frame's is snap.frame_target's. Nothing in the document changes.

The canvas tells where the pointer is (`hover`, composition px; `leave`); the Alt key is read for the window by an event
filter, as paint_pick.py reads it (a lone modifier key has no key event on an item without the focus), so the lines
come on the key, not on the next move. A script says Alt with `setAlt`.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QEvent, Qt, Signal, Slot
from rostrum_gui.gui_filter import GuiFilter

from rostrum2d.frame import view as camera

from . import bounds, measure, snap


class Measure(GuiFilter):
    changed = Signal()                                      # the lines
    altChanged = Signal()

    def __init__(self, bridge):
        super().__init__(bridge)
        self.b, self._alt, self._at, self._lines = bridge, False, None, []
        for s in (bridge.selectedItemsChanged, bridge.toolChanged, bridge.shownChanged):
            s.connect(self._again)

    alt = Property(bool, lambda self: self._alt, notify=altChanged)
    lines = Property("QVariantList", lambda self: self._lines, notify=changed)    # measure.lines, world px

    @Slot(float, float)
    def hover(self, x, y):
        self._at = (x, y)
        self._again()

    @Slot()
    def leave(self):
        self._at = None
        self._again()

    @Slot(bool)
    def setAlt(self, on):
        if bool(on) != self._alt:
            self._alt = bool(on)
            self._again()
            self.altChanged.emit()

    def on_event(self, obj, event):
        t = event.type()
        if t in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease) and event.key() == Qt.Key.Key_Alt:
            self.setAlt(t == QEvent.Type.KeyPress)
        elif t == QEvent.Type.WindowDeactivate:
            self.setAlt(False)
        return False

    def _again(self, *_):
        got = self._measure() if self._alt and self._at is not None else []
        if got != self._lines:
            self._lines = got
            self.changed.emit()

    def _measure(self) -> list[dict]:
        picked = self.b.multi.layers()
        if self.b.tool != "move" or len(picked) != 1 or self.b.playing:
            return []
        mine = self.b.shown_boxes(picked)
        if not mine:
            return []
        hit = self.b.multi.target(self._at[0], self._at[1], "click")
        other = self.b.shown_boxes([hit]) if hit and hit != picked[0] else []
        if other:
            to = bounds.extent(other[0])
        else:
            c = self.b.comp()
            to = snap.frame_target(c["width"], c["height"], camera.shot(self.b.shown_placed(), self.b.shown_t()))[1]
        return measure.lines(bounds.extent(mine[0]), to)
