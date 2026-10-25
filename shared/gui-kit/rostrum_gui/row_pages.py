"""The settings panel's rows as one list per layout (a kind's settings: a text's, the scene's, a drawing's), each
kept with its rows made, only the shown one visible. A pick of another kind flips which list shows and sends that
list only the values that differ from when it last showed; nothing is moved, made or relabelled.

One list for every kind (model.py + model_pick.py) gave a pick across kinds its rows by moving the delegates that had
shown those settings into place and flipping each row's `valid` on and off (~15 rows out, ~15 in, each re-running its
bindings): ~10-12 ms of the screen thread a pick, while a pick within a kind cost ~2 ms.

Python sees one RowsModel's API (`rows`, `update`, `reset`, `instant`): the shown page's. A layout is the row ids of
`rows` (every row the kind's layout holds, shown or not), so an edit within a kind stays on its page and animates there
as before (model.py), and a selection whose rows have other ids gets (or makes) the page of those ids. QML sees a list
model of pages (role `page`: a RowsModel) and `shown`, the index of the visible one (Inspector.qml). At most PAGES are
kept; the page shown longest ago goes first.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QAbstractListModel, QByteArray, QModelIndex, QObject, Qt, Signal, Slot

from .model import RowsModel

PAGES = 12


class RowPages(QAbstractListModel):
    shownChanged = Signal()

    def __init__(self, roles: tuple[str, ...], parent=None):
        super().__init__(parent)
        self._row_roles = roles
        self._pages: list[tuple[tuple, RowsModel]] = []     # (layout, its rows), in the order QML made them
        self._at = -1                                        # the shown page's index (-1: none yet)
        self._used: list[tuple] = []                         # layouts, the last shown last

    # ---- QML ---------------------------------------------------------------------------------------------------
    def roleNames(self):
        return {Qt.UserRole + 1: QByteArray(b"page")}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._pages)

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid() and role == Qt.UserRole + 1 and index.row() < len(self._pages):
            return self._pages[index.row()][1]
        return None

    paged = Property(bool, lambda self: True, constant=True)     # (Inspector.qml tells this from a plain RowsModel)

    @Property(int, notify=shownChanged)
    def shown(self):
        return self._at

    @Property(QObject, notify=shownChanged)
    def current(self):
        """The shown page's rows (a RowsModel)."""
        return self._page()

    @Slot(int, result=QObject)
    def page(self, i):
        return self._pages[i][1] if 0 <= i < len(self._pages) else None

    # ---- Python: the shown page's RowsModel -------------------------------------------------------------------
    def _page(self) -> RowsModel | None:
        return self._pages[self._at][1] if self._at >= 0 else None

    @property
    def rows(self) -> list[dict]:
        p = self._page()
        return p.rows if p is not None else []

    @property
    def instant(self) -> bool:
        p = self._page()
        return p.instant if p is not None else False

    def reset(self, rows: list[dict]):
        self._show(rows, lambda p, new: p.reset(rows))

    def update(self, rows: list[dict], instant: bool = False):
        """The shown page's update; rows of another layout show on that layout's page (made the first time, at
        their final state), updated in place at once (`instant`: a page coming back shows as it is now, no easing)."""
        self._show(rows, lambda p, new: p.reset(rows) if new else p.update(rows, instant or p is not self._page()))

    def park(self, rows: list[dict]):
        """Rows a later pick will show, made ahead (bridge_select.make_panels_ahead): that layout's page, filled and
        hidden; the shown page stays. It counts as shown longest ago, so it is the first to go for room."""
        key = tuple(r.get("id") for r in rows)
        if any(k == key for k, _ in self._pages):
            return
        self._drop_old()
        self.beginInsertRows(QModelIndex(), len(self._pages), len(self._pages))
        self._pages.append((key, RowsModel(self._row_roles, self)))
        self.endInsertRows()
        self._used.insert(0, key)
        self._pages[-1][1].reset(rows)

    def _show(self, rows: list[dict], fill):
        key = tuple(r.get("id") for r in rows)
        at = next((i for i, (k, _) in enumerate(self._pages) if k == key), -1)
        new = at < 0
        if new:
            self._drop_old()
            self.beginInsertRows(QModelIndex(), len(self._pages), len(self._pages))
            self._pages.append((key, RowsModel(self._row_roles, self)))
            self.endInsertRows()
            at = len(self._pages) - 1
        else:
            self._used.remove(key)
        self._used.append(key)
        fill(self._pages[at][1], new)                    # filled while still hidden, then shown
        if at != self._at:
            self._at = at
            self.shownChanged.emit()

    def _drop_old(self):
        """Room for one more page: the one shown longest ago goes (never the shown one)."""
        if len(self._pages) < PAGES:
            return
        shown = self._pages[self._at][0] if self._at >= 0 else None
        old = next(k for k in self._used if k != shown)
        i = next(i for i, (k, _) in enumerate(self._pages) if k == old)
        self._used.remove(old)
        self.beginRemoveRows(QModelIndex(), i, i)
        _, gone = self._pages.pop(i)
        self.endRemoveRows()
        gone.deleteLater()
        if self._at > i:
            self._at -= 1
            self.shownChanged.emit()
