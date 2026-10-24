"""The screen's problems list: what inspect_diagnose finds (rostrum2d/diagnose_engine.everything, the same function),
worked out off the GUI thread with an engine of its own, newest document wins, half a second after the last change.
The kit's Problems chip in the top bar (ProblemsChip.qml) shows the count only while there are any; its list shows each
in words with what to do, and a click jumps to it (`jump`: selects the item it is about, and goes to its moment).
"""
from __future__ import annotations

import copy

from PySide6.QtCore import Property, QTimer, Signal, Slot
from rostrum_core import RostrumError
from rostrum_gui.frames import PictureWorker

from . import project_picks

WORDS = {"refused": "Can't be drawn", "missing-font": "Missing font", "missing-file": "Missing file", "outside-project": "File outside the project",
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

    @Slot("QVariant")
    def jump(self, row):
        """A row was clicked: select what it is about (nothing for a problem of the whole composition), and go to its
        moment when it has one."""
        row = dict(row)
        if isinstance(row.get("time"), (int, float)):
            self.bridge.setTime(float(row["time"]))
        try:
            self.bridge.doc.item(row.get("item") or "")
        except RostrumError:
            return
        self.bridge.select(row["item"])

    @Slot("QVariant", str)
    def act(self, row, value):
        """A row's own picker (a Missing font's "Use another font"): one change for every text using that font (font.replace)."""
        row, b = dict(row), self.bridge
        if row.get("family"):
            b.guard(lambda: b.done(b.doc.apply([{"op": "font.replace", "args": {"from": row["family"], "to": value}}], b.who,
                                              label="Use another font"), ""))

    def show_rows(self, rows):
        """A scripted list (the layout check's long problems), until the next look."""
        self._take(list(rows))

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
        rows = [{**p, "label": WORDS.get(p["kind"], p["kind"]), "danger": p["kind"] == "refused"} for p in found]
        self.found.emit(rows)

    def describe(self, job, error):
        return f"Error: problems list: {error}"

    def _take(self, rows):
        self._done = True
        rows = [{**r, "options": project_picks.fonts()} if r.get("family") else r for r in rows]     # (the faces: the GUI thread's)
        if rows != self._rows:
            self._rows = rows
            self.changed.emit()
