"""A list model of plain dict rows for QML. `reset` swaps the whole list (a new layout: no animation);
`update` changes rows in place with dataChanged, so delegates live on and animate their own reveal.
`update(rows, instant=True)` (a new selection) changes them in place too, with `instant` true for that one update,
so each row takes its new state at once (InspectorRow's reveal reads it) and nothing eases.
`rows` is every row of the layout (the bridge reads it); what the view (QML) sees is `_shown`: only the rows that apply
now (valid), plus, between selections, a row that stopped applying (it stays to ease out and come back). A kind's layout
holds every param and ~90 of ~100 rows are absent, so a selection switch made ~90 delegates to show nothing (~50 ms).
A row that starts to apply is inserted as absent and then set valid, so it eases in like a row that was always there.
A new selection of settings rows (rows with `valid`) never frees a delegate (model_pick.py): each row takes the delegate that last showed the same setting
(shown or parked; only its value changes), else a new one; delegates left over are parked after the shown rows,
absent, for a later selection."""
from __future__ import annotations

from difflib import SequenceMatcher

from PySide6.QtCore import Property, QAbstractListModel, QByteArray, QModelIndex, Qt, Signal

from .model_pick import repick


class RowsModel(QAbstractListModel):
    instantChanged = Signal()

    def __init__(self, roles: tuple[str, ...], parent=None):
        super().__init__(parent)
        self._names = roles
        self._roles = {Qt.UserRole + 1 + i: QByteArray(n.encode()) for i, n in enumerate(roles)}
        self._ids = {n: Qt.UserRole + 1 + i for i, n in enumerate(roles)}
        self.rows: list[dict] = []          # every row of the layout
        self._shown: list[dict] = []        # the rows the view has (see the module note)
        self._parked: list[dict] = []       # after them: rows kept for the next selection's use (absent, not shown)
        self._instant = False

    @Property(bool, notify=instantChanged)
    def instant(self):
        """True only while an `update(..., instant=True)` is being sent: rows change without easing."""
        return self._instant

    def roleNames(self):
        return self._roles

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._shown) + len(self._parked)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or role not in self._roles:
            return None
        i = index.row()
        row = self._shown[i] if i < len(self._shown) else self._parked[i - len(self._shown)]
        return row.get(self._names[role - Qt.UserRole - 1])

    def reset(self, rows: list[dict]):
        self.beginResetModel()
        self.rows = list(rows)
        self._shown, self._parked = [r for r in rows if r.get("valid", True)], []
        self.endResetModel()

    def update(self, rows: list[dict], instant: bool = False):
        """Same layout, new values: only the changed roles of the changed rows are signalled.
        Another layout (other row ids) is a reset, or with `instant` only the shown rows that differ are removed and
        inserted. Same layout, other rows applying: those are inserted or (between selections) dropped."""
        if not instant and [r.get("id") for r in rows] != [r.get("id") for r in self.rows]:
            self.reset(rows)
            return
        have = {r.get("id") for r in self._shown}
        want = [r for r in rows if r.get("valid", True) or (not instant and r.get("id") in have)]
        self.rows = list(rows)
        if instant:
            self._instant = True
            self.instantChanged.emit()
        try:
            self._patch(want, instant)
        finally:
            if instant:
                self._instant = False
                self.instantChanged.emit()

    def park(self, rows: list[dict]):
        """Delegates made ahead for rows a later selection will show: added after the shown rows, absent, unless one
        that showed the same setting is here already (model_pick.py takes them, as it takes any parked row)."""
        have = {(r.get("id"), self._look(r)) for r in self._shown + self._parked}
        new = []
        for r in rows:
            key = (r.get("id"), self._look(r))
            if key not in have:
                have.add(key)
                new.append({**r, "valid": False})
        if new:
            n = self.rowCount()
            self.beginInsertRows(QModelIndex(), n, n + len(new) - 1)
            self._parked.extend(new)
            self.endInsertRows()

    def _send(self, rows: list[dict], at: int = 0):
        for i, new in enumerate(rows, at):
            old = self._shown[i]
            if old == new:                  # most rows of an edit are as they were: one compare, not one per role
                continue
            changed = [self._ids[n] for n in self._names if old.get(n) != new.get(n)]
            if changed:
                self._shown[i] = new
                self.dataChanged.emit(self.index(i), self.index(i), changed)

    @staticmethod
    def _look(row: dict):
        """What a row's delegate is made of (its kind of control): a settings row takes the delegate that showed the same
        setting only when it is made of the same control (model_pick.py); other rows are matched by it, in order."""
        return row.get("row"), row.get("type"), row.get("control"), row.get("half")

    def _patch(self, rows: list[dict], instant: bool):
        """The shown rows both lists share keep their delegates; the rest are removed and inserted (from the end, so
        the indices before each step still hold). Between selections an inserted row is made absent first and then
        set to its state, so it eases in. A new selection of rows that say whether they apply (`valid`: the settings
        rows) keeps every delegate (model_pick.py); other rows (a list of lanes) are matched by their look in order."""
        if [r.get("id") for r in rows] == [r.get("id") for r in self._shown]:
            return self._send(rows)
        if instant and "valid" in self._ids:
            return repick(self, rows)
        key = self._look if instant else (lambda r: r.get("id"))
        ops = SequenceMatcher(None, [key(r) for r in self._shown], [key(r) for r in rows], autojunk=False)
        for tag, i1, i2, j1, j2 in reversed(ops.get_opcodes()):
            if tag == "equal":
                self._send(rows[j1:j2], i1)
                continue
            if i2 > i1:
                self.beginRemoveRows(QModelIndex(), i1, i2 - 1)
                del self._shown[i1:i2]
                self.endRemoveRows()
            if j2 > j1:
                new = rows[j1:j2]
                self.beginInsertRows(QModelIndex(), i1, i1 + j2 - j1 - 1)
                self._shown[i1:i1] = new if instant else [{**r, "valid": False} for r in new]
                self.endInsertRows()
                if not instant:
                    self._send(new, i1)
