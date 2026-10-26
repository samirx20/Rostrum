"""A list of row dicts (each with a unique "id") as a Qt list model that changes the way the rows changed: rows added,
removed or moved by id, a row whose data differs updated in place. A QML ListView over a plain list rebuilds every row
at each announcement, which dropped a key (and its mouse grab) under the pointer mid-drag and cost a whole timeline
per change; over this model a row's delegate lives as long as the row does. The delegate reads the row as `modelData`."""
from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt


class RowsModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[dict] = []

    def roleNames(self):
        return {Qt.UserRole + 1: b"modelData"}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index, role=Qt.UserRole + 1):
        return self._rows[index.row()] if index.isValid() and role == Qt.UserRole + 1 else None

    def set(self, rows: list[dict]) -> None:
        """Make the model show `rows`, with the fewest changes: removals, then in order each row's insert, move or update."""
        keep = {r["id"] for r in rows}
        for i in range(len(self._rows) - 1, -1, -1):
            if self._rows[i]["id"] not in keep:
                self.beginRemoveRows(QModelIndex(), i, i)
                del self._rows[i]
                self.endRemoveRows()
        run = [-1, -1]                       # the rows changed in place side by side: one announcement for the run (Qt and
                                             # QML take one dataChanged per run, not one per row: 48 staggered layers)

        def flush():
            if run[0] >= 0:
                self.dataChanged.emit(self.index(run[0]), self.index(run[1]))
                run[0] = run[1] = -1

        def changed(i):
            if run[0] >= 0 and i == run[1] + 1:
                run[1] = i
            else:
                flush()
                run[0] = run[1] = i
        for i, row in enumerate(rows):
            if i < len(self._rows) and self._rows[i]["id"] == row["id"]:
                if self._rows[i] != row:
                    self._rows[i] = row
                    changed(i)
                continue
            flush()
            at = next((j for j in range(i + 1, len(self._rows)) if self._rows[j]["id"] == row["id"]), -1)
            if at < 0:
                self.beginInsertRows(QModelIndex(), i, i)
                self._rows.insert(i, row)
                self.endInsertRows()
                continue
            self.beginMoveRows(QModelIndex(), at, at, QModelIndex(), i)
            self._rows.insert(i, self._rows.pop(at))
            self.endMoveRows()
            if self._rows[i] != row:
                self._rows[i] = row
                changed(i)
        flush()
