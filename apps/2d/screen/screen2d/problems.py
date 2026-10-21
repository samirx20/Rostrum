"""The screen's problems list: what inspect_diagnose finds (rostrum2d/diagnose_engine.everything, the same function),
worked out off the GUI thread with an engine of its own, newest document wins, half a second after the last change.
The top bar shows a Problems button with the count only while there are any; its panel lists each in words and a click
selects the item it is about.
"""
from __future__ import annotations

import copy

from PySide6.QtCore import Property, QTimer, Signal, Slot
from rostrum_core import RostrumError
from rostrum_gui.frames import PictureWorker

WORDS = {"refused": "Can't be drawn", "missing-font": "Missing font", "missing-file": "Missing file",
         "broken-link": "Broken link", "missing-marker": "Missing marker", "expression": "Expression",
         "invisible": "Never seen", "off-canvas": "Off the frame", "unused-keys": "Keys that do nothing",
         "missing-render": "No 3D render", "stale-render": "3D render out of date"}


class Problems(PictureWorker):
    changed = Signal()
    found = Signal(list)

    def __init__(self, bridge):
        super().__init__("problems2d", bridge)
        self.bridge, self._rows, self._done = bridge, [], False
        self._wait = QTimer(self, singleShot=True, interval=500)
        self._wait.timeout.connect(self._post)
        self.found.connect(self._take)
        self.start()

    @Property("QVariantList", notify=changed)
    def rows(self):
        return self._rows

    @Property(int, notify=changed)
    def count(self):
        return len(self._rows)

    @Slot(str)
    def show(self, item_id):
        """A row was clicked: select what it is about (nothing for a problem of the whole composition)."""
        try:
            self.bridge.doc.item(item_id)
        except RostrumError:
            return
        self.bridge.select(item_id)

    def touch(self):
        """The document or the markers changed: look again once things are still."""
        self._wait.start()

    def wait(self, timeout_s: float) -> bool:
        """For scripted steps: run the event loop until the newest list is in (False when it took too long)."""
        import time
        from PySide6.QtCore import QCoreApplication
        end = time.time() + timeout_s
        self._done = False
        while time.time() < end:
            QCoreApplication.processEvents()
            if self._done and not self._wait.isActive():
                return True
            time.sleep(0.02)
        return False

    def _post(self):
        b = self.bridge
        self.post_latest((copy.deepcopy(b.doc.data), b.comp_id, b.doc.folder, b.marks.times if b.doc.folder else None))

    def open_engine(self):
        from rostrum2d.engine import Engine
        return Engine()

    def handle(self, eng, job):
        from rostrum2d import textsize
        from rostrum2d.diagnose_engine import everything
        data, comp_id, folder, markers = job
        with textsize.use(eng):         # this thread measures texts with its own engine
            found = everything(data, comp_id, folder, markers, eng)
        rows = [{**p, "label": WORDS.get(p["kind"], p["kind"])} for p in found]
        self.found.emit(rows)

    def describe(self, job, error):
        return f"Error: problems list: {error}"

    def _take(self, rows):
        self._done = True
        if rows != self._rows:
            self._rows = rows
            self.changed.emit()
