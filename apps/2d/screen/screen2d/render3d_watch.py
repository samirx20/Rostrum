"""Says when a 3D render layer's picture should change by itself: its 3D item got a new finished render, or its 3D
document changed after the render (out of date). The canvas then draws again and the Problems list looks again.
Looks every 2 s, and only while the composition has a 3D render layer (rostrum2d/render3d.py: what is shown).

The look reads the 3D item's files (~250 ms a layer), so it runs off the GUI thread on the kit's worker (one look at a
time, the newest wins), where it can't hitch playback; only its answer comes back to the GUI thread.
"""
from __future__ import annotations

import copy
from types import SimpleNamespace

from PySide6.QtCore import QTimer, Signal
from rostrum_gui.frames import PictureWorker


class Render3DWatch(PictureWorker):
    changed = Signal()
    looked = Signal(object)          # the layers' (id, status message) tuple

    def __init__(self, bridge, parent=None):
        super().__init__("render3d-watch", parent)
        self.b, self._last = bridge, None
        self.looked.connect(self._take)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._post)
        self._timer.start(2000)
        self.start()

    def _post(self):
        from rostrum2d.exprbake import items_of
        layers = [copy.deepcopy(i) for i in items_of(self.b.comp()).values() if i["type"] == "render3d"]
        if layers:
            self.post_latest((layers, self.b.doc.folder))
        else:
            self._take(None)

    def open_engine(self):
        return SimpleNamespace(close=lambda: None)     # no engine (the look reads files); the worker closes it

    def handle(self, _eng, job):
        from rostrum2d import render3d
        layers, folder = job
        self.looked.emit(tuple((i["id"], render3d.status(i, folder).get("message")) for i in layers))

    def describe(self, job, error):
        return f"Error: watching 3D render layers: {error}"

    def _take(self, now):
        if now != self._last and self._last is not None:
            self.changed.emit()
        self._last = now

    def close(self):
        self._timer.stop()
        super().close()
