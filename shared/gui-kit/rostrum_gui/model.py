"""A list model of plain dict rows for QML. `reset` swaps the whole list (a new layout: no animation);
`update` changes rows in place with dataChanged, so delegates live on and animate their own reveal.
`update(rows, instant=True)` (a new selection) changes them in place too, with `instant` true for that one update,
so each row takes its new state at once (InspectorRow's reveal reads it) and nothing eases. Rows whose id stays keep
their delegate; only the rows another kind adds or drops are made or freed (a kind switch rebuilt them all)."""
from __future__ import annotations

from difflib import SequenceMatcher

from PySide6.QtCore import Property, QAbstractListModel, QByteArray, QModelIndex, Qt, Signal


class RowsModel(QAbstractListModel):
    instantChanged = Signal()

    def __init__(self, roles: tuple[str, ...], parent=None):
        super().__init__(parent)
        self._names = roles
        self._roles = {Qt.UserRole + 1 + i: QByteArray(n.encode()) for i, n in enumerate(roles)}
        self._ids = {n: Qt.UserRole + 1 + i for i, n in enumerate(roles)}
        self.rows: list[dict] = []
        self._instant = False

    @Property(bool, notify=instantChanged)
    def instant(self):
        """True only while an `update(..., instant=True)` is being sent: rows change without easing."""
        return self._instant

    def roleNames(self):
        return self._roles

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or role not in self._roles:
            return None
        return self.rows[index.row()].get(self._names[role - Qt.UserRole - 1])

    def reset(self, rows: list[dict]):
        self.beginResetModel()
        self.rows = list(rows)
        self.endResetModel()

    def update(self, rows: list[dict], instant: bool = False):
        """Same layout, new values: only the changed roles of the changed rows are signalled.
        A different row count or row ids means a different layout: reset, or with `instant` only the rows that
        differ are removed and inserted."""
        same = [r.get("id") for r in rows] == [r.get("id") for r in self.rows]
        if not same and not instant:
            self.reset(rows)
            return
        if instant:
            self._instant = True
            self.instantChanged.emit()
        try:
            self._send(rows) if same else self._patch(rows)
        finally:
            if instant:
                self._instant = False
                self.instantChanged.emit()

    def _send(self, rows: list[dict], at: int = 0):
        for i, new in enumerate(rows, at):
            old = self.rows[i]
            if old == new:                  # most rows of an edit are as they were: one compare, not one per role
                continue
            changed = [self._ids[n] for n in self._names if old.get(n) != new.get(n)]
            if changed:
                self.rows[i] = new
                self.dataChanged.emit(self.index(i), self.index(i), changed)

    def _patch(self, rows: list[dict]):
        """Another layout: the rows both share keep their delegates; the rest are removed and inserted (from the
        end, so the indices before each step still hold)."""
        ops = SequenceMatcher(None, [r.get("id") for r in self.rows], [r.get("id") for r in rows], autojunk=False)
        for tag, i1, i2, j1, j2 in reversed(ops.get_opcodes()):
            if tag == "equal":
                self._send(rows[j1:j2], i1)
                continue
            if i2 > i1:
                self.beginRemoveRows(QModelIndex(), i1, i2 - 1)
                del self.rows[i1:i2]
                self.endRemoveRows()
            if j2 > j1:
                self.beginInsertRows(QModelIndex(), i1, i1 + j2 - j1 - 1)
                self.rows[i1:i1] = rows[j1:j2]
                self.endInsertRows()
