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

A layout only a few rows away from a kept page's (the same kind with a few settings left out because the screen shows
them elsewhere: the Sound Mixer open, onpage.py) takes that page over: its rows are picked in place (model_pick.py: the
rows left out are parked, the ones back come from the parked) instead of a new page made whole (~100-120 ms for a
track's panel the first time the Mixer opened with a track selected).
"""
from __future__ import annotations

from PySide6.QtCore import Property, QAbstractListModel, QByteArray, QModelIndex, QObject, Qt, Signal, Slot

from .model import RowsModel

PAGES = 12
NEAR = 8            # at most this many rows left out of the other: the same kind, a few settings shown elsewhere


def _near(a: tuple, b: tuple) -> bool:
    """One layout is the other with a few rows left out (two kinds, each with rows of its own, never are)."""
    sa, sb = set(a), set(b)
    return (sa <= sb or sb <= sa) and 0 < len(sa ^ sb) <= NEAR


class RowPages(QAbstractListModel):
    shownChanged = Signal()

    def __init__(self, roles: tuple[str, ...], parent=None):
        super().__init__(parent)
        self._row_roles = roles
        self._pages: list[tuple[tuple, RowsModel]] = []     # (layout, its rows), in the order QML made them
        self._at = -1                                        # the shown page's index (-1: none yet)
        self._used: list[tuple] = []                         # layouts, the last shown last
        self.reader = None                                   # called before `rows` is read (the bridge's _panel_now)

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
        """The rows as of the document and selection now (a panel still waiting for the frame after is made first)."""
        if self.reader is not None:
            self.reader()
        return self.shown_rows

    @property
    def shown_rows(self) -> list[dict]:
        """The rows the panel shows now: for a QML binding (told by rowsChanged when the waiting panel lands; making it
        inside a binding put the whole panel back into the click)."""
        p = self._page()
        return p.rows if p is not None else []

    @property
    def instant(self) -> bool:
        p = self._page()
        return p.instant if p is not None else False

    def reset(self, rows: list[dict]):
        self._show(rows, lambda p, new, near: p.reset(rows))

    def update(self, rows: list[dict], instant: bool = False):
        """The shown page's update; rows of another layout show on that layout's page (made the first time, at
        their final state), updated in place at once (`instant`: a page coming back shows as it is now, no easing)."""
        self._show(rows, lambda p, new, near: p.reset(rows) if new else p.update(rows, instant or near or p is not self._page()))

    def park(self, rows: list[dict], part: list[dict]):
        """Made ahead (bridge_select.make_panels_ahead): the page of `rows`' layout, hidden (made empty the first
        time), with `part` of its rows parked in it, their controls made; the pick that later shows it moves them
        into place (model_pick.py) and only their values change."""
        at, new, _ = self._page_of(rows, near_ok=False)
        if new:
            self._pages[at][1].reset([])
        self._pages[at][1].park(part, ready=True)

    def _page_of(self, rows: list[dict], near_ok: bool = True) -> tuple[int, bool, bool]:
        """The index of the page of `rows`' layout (made, hidden, if there is none), whether it was made now and whether
        it is a near layout's page taken over (module note); it becomes the page used last (the last to go)."""
        key = tuple(r.get("id") for r in rows)
        at = next((i for i, (k, _) in enumerate(self._pages) if k == key), -1)
        near = False
        if at < 0 and near_ok:                       # the shown page first, then the others (never for a page made ahead)
            order = ([self._at] if self._at >= 0 else []) + [i for i in range(len(self._pages)) if i != self._at]
            at = next((i for i in order if _near(self._pages[i][0], key)), -1)
            if at >= 0:
                near, old = True, self._pages[at][0]
                self._pages[at] = (key, self._pages[at][1])
                self._used[self._used.index(old)] = key
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
        return at, new, near

    def _show(self, rows: list[dict], fill):
        at, new, near = self._page_of(rows)
        fill(self._pages[at][1], new, near)                    # filled while still hidden, then shown
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
