"""The project's shared markers on a screen (rostrum_core.markers): a list QML can draw as flags, kept fresh when
another app or an agent changes them, the one snap rule for anything dragged along time, and the ruler's marker
edits (add at the playhead, move, rename, delete). Each edit is one marker operation through
rostrum_core.markers.edit, recorded with the person's name in the project's marker history: the same operations
agents call (edit_markers). The watch joins the screen's one undo history (DocBridge.join_history): the screen's
undo takes back a marker edit like any other, and an agent's marker edit shows as who changed what.

A document outside a project folder has no shared markers: `available` is false and the screen shows no marker
controls (rule of individuality). A refused edit (a name taken, a bad time) is reported through `fail`, never
swallowed.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from rostrum_core import RostrumError, Who
from rostrum_core.markers import edit, listing, open_markers, times, version

POLL_MS = 500          # another process (an agent, Sound) may move a marker: look at the file this often (cheap)


class MarkerWatch(QObject):
    changed = Signal()

    def __init__(self, folder, parent=None, who=None, fail=None, owner=""):
        super().__init__(parent)
        self.folder, self.who, self.owner = folder, who or Who.person("sam"), owner
        self._fail = fail or (lambda line: print(line, file=sys.stderr))
        self._stamp, self.times, self._rows, self._count, self._last = None, {}, [], 0, None
        self._read()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        if folder is not None:
            self._timer.start(POLL_MS)

    def refresh(self):
        if self._read():
            self.changed.emit()

    def rows(self) -> list[dict]:
        """[{id, name, at, colour}] by time, for the ruler's flags."""
        return self._rows

    def snap(self, t: float, within: float) -> float:
        """t moved onto the nearest marker when one is within `within` seconds; else t unchanged."""
        near = min(self.times.values(), key=lambda m: abs(m - t), default=None)
        return near if near is not None and abs(near - t) <= within else t

    def close(self):
        self._timer.stop()

    # ---- one history with the screen's document (DocBridge.join_history) ------------------------------------
    def history_doc(self):
        """The marker document as it is on disk now (None outside a project)."""
        return open_markers(self.folder) if self.folder is not None else None

    def stepped(self, doc):
        """An undo or redo landed in `doc` (from history_doc): save it and show it."""
        doc.save()
        self.refresh()

    def change_count(self) -> int:
        return self._count

    def last_change(self):
        return self._last

    # ---- edits from the ruler: each one marker operation, one change ------------------------------------------
    @Property(bool, constant=True)
    def available(self):
        return self.folder is not None

    @Slot(float, result=str)
    def add(self, at):
        """A new marker at `at` seconds, named "Marker n" (the first free n); returns its id ("" if refused)."""
        taken = {n.strip().lower() for n in self.times}
        n = next(i for i in range(1, len(taken) + 2) if f"marker {i}" not in taken)
        args = {"name": f"Marker {n}", "at": round(max(at, 0.0), 6), **({"owner": self.owner} if self.owner else {})}
        before = {m["id"] for m in self._rows}
        if not self._edit([{"op": "marker.add", "args": args}], "Add marker"):
            return ""
        return next((m["id"] for m in self._rows if m["id"] not in before), "")

    @Slot(str, float, result=bool)
    def move(self, marker_id, at):
        return self._edit([{"op": "marker.move", "target": [marker_id], "args": {"at": round(max(at, 0.0), 6)}}],
                          "Move marker")

    @Slot(str, str, result=bool)
    def rename(self, marker_id, name):
        return self._edit([{"op": "marker.rename", "target": [marker_id], "args": {"name": name}}], "Rename marker")

    @Slot(str, result=bool)
    def remove(self, marker_id):
        return self._edit([{"op": "marker.remove", "target": [marker_id]}], "Delete marker")

    # ---- inside -----------------------------------------------------------------------------------------------
    def _read(self) -> bool:
        """Re-read when the marker file changed (any edit: time, name, colour); True when it did."""
        stamp = version(self.folder) if self.folder is not None else 0
        if stamp == self._stamp:
            return False
        self._stamp, self.times = stamp, times(self.folder)
        doc = open_markers(self.folder) if stamp else None
        self._rows = [{k: m[k] for k in ("id", "name", "at", "colour")} for m in listing(self.folder, doc)] if doc else []
        changes = doc.history.changes if doc else []
        self._count, self._last = len(changes), (changes[-1] if changes else None)
        return True

    def _edit(self, calls, label) -> bool:
        if self.folder is None:
            self._fail("Error: markers: this document is not in a project folder; shared markers belong to a project.")
            return False
        try:
            edit(self.folder, calls, self.who, label=label)
        except RostrumError as e:
            self._fail(e.line())
            return False
        self.refresh()
        return True
