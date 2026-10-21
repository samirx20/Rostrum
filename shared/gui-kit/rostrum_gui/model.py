"""A list model of plain dict rows for QML. `reset` swaps the whole list (a new selection: no animation);
`update` changes rows in place with dataChanged, so delegates live on and animate their own reveal."""
from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, Qt


class RowsModel(QAbstractListModel):
    def __init__(self, roles: tuple[str, ...], parent=None):
        super().__init__(parent)
        self._names = roles
        self._roles = {Qt.UserRole + 1 + i: QByteArray(n.encode()) for i, n in enumerate(roles)}
        self._ids = {n: Qt.UserRole + 1 + i for i, n in enumerate(roles)}
        self.rows: list[dict] = []

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

    def update(self, rows: list[dict]):
        """Same layout, new values: only the changed roles of the changed rows are signalled.
        A different row count or row ids means a different layout, so it falls back to reset."""
        if [r.get("id") for r in rows] != [r.get("id") for r in self.rows]:
            self.reset(rows)
            return
        for i, (old, new) in enumerate(zip(self.rows, rows)):
            changed = [self._ids[n] for n in self._names if old.get(n) != new.get(n)]
            if changed:
                self.rows[i] = new
                self.dataChanged.emit(self.index(i), self.index(i), changed)
