"""Says when a 3D render layer's picture should change by itself: its 3D item got a new finished render, or its 3D
document changed after the render (out of date). The canvas then draws again and the Problems list looks again.
Looks every 2 s, and only while the composition has a 3D render layer (rostrum2d/render3d.py: what is shown)."""
from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal


class Render3DWatch(QObject):
    changed = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.b, self._last = bridge, None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(2000)

    def _layers(self) -> list[dict]:
        from rostrum2d.exprbake import items_of
        return [i for i in items_of(self.b.comp()).values() if i["type"] == "render3d"]

    def _tick(self):
        from rostrum2d import render3d
        layers = self._layers()
        now = tuple((i["id"], render3d.status(i, self.b.doc.folder).get("message")) for i in layers) if layers else None
        if now != self._last and self._last is not None:
            self.changed.emit()
        self._last = now
