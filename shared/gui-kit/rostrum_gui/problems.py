"""The Problems chip's list (qml ProblemsChip.qml), for an app that has no list of its own yet: rows in words, each
with what to do, and `jump(row)` (select the thing and go to its moment: the app's `jump_to(row)`).

A row: {label ("Missing file"), message (what is wrong, naming the thing), fix (what to do), item (the id to select,
or ""), time (seconds, optional), danger (red: damage, e.g. clipping; else amber)}.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot


class ProblemsList(QObject):
    changed = Signal()

    def __init__(self, jump_to=None, parent=None):
        super().__init__(parent)
        self._rows, self._jump_to, self._pinned = [], jump_to, False

    @Property("QVariantList", notify=changed)
    def rows(self):
        return self._rows

    @Property(int, notify=changed)
    def count(self):
        return len(self._rows)

    def show_rows(self, rows: list[dict]):
        """The app's newest list."""
        if rows != self._rows and not self._pinned:
            self._rows = list(rows)
            self.changed.emit()

    def pin(self, rows: list[dict]):
        """A scripted list (the layout check's long problems): kept, whatever the app finds next."""
        self._pinned = False
        self.show_rows(rows)
        self._pinned = True

    @Slot("QVariant")
    def jump(self, row):
        if self._jump_to is not None:
            self._jump_to(dict(row))
