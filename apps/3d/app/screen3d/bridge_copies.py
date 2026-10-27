"""Copies on Bridge3D (brief 24; a slot mix-in): the right-click that can scatter what was selected over the item under
the pointer, the grey line under Count, and what a copies action leaves selected. The live drag of Count / Spacing is
copies_live.Scrubs (below, in the bases), the pick of one copy copies_qt.py, its gizmo copies_gizmo.py.
"""
from __future__ import annotations

from PySide6.QtCore import Slot

from .copies_actions import MAKE, NEAR, SCATTER
from .copies_live import Scrubs


class CopiesMixin(Scrubs):
    _scatter_from: tuple = ()           # what was selected before the right-click on a surface (screen state)
    _menu_before: tuple = ()            # the selection when the right-click was pressed

    def _make_copies(self):
        self.selectedItemsChanged.connect(self._end_scatter_from)

    def _end_scatter_from(self, *_):
        self._scatter_from = ()

    @Slot()
    def rightClickStarts(self):
        """A right-click on the viewport: the pick that follows selects what is under it, so what was selected before is
        taken now (menuSelect reads it)."""
        self._menu_before = tuple(self.selection)

    @Slot(str)
    def menuSelect(self, id_):
        """The right-click's pick answered with `id_` ("" = empty space): an item outside the selection is selected alone
        (as 2D's layers), one inside it keeps the selection; what was selected before the click stays known for this one
        menu, so Scatter '<it>' on '<surface>' can be offered (copies_actions.py). The menu's choice, or the next
        selection change, ends it."""
        before, self._menu_before = list(self._menu_before or self.selection), ()
        if id_ == "":
            if self.selection:
                self.select("")
            return
        if id_ not in self.selection:
            self.select(id_)
        if before and id_ not in before:
            self._scatter_from = tuple(before)
            self._hub.refresh()

    def copies_note(self, item_id: str) -> str:
        vp = getattr(self, "viewport", None)
        return vp.copies.note(item_id) if vp is not None else ""

    def copies_selects(self, calls) -> str:
        """What a copies action leaves selected: a new copies item (its Count row focused by the caller), a change near's
        new small sphere (the thing to move) or its effector. "" for calls that are not copies'."""
        ops = {c["op"]: c for c in calls}
        for op in (MAKE, SCATTER):
            if op in ops:
                return ops[op]["args"]["id"]
        if NEAR in ops:
            ball = next((c["args"]["id"] for c in calls if c["op"] == "mesh.add"), "")
            return ball or ops[NEAR]["args"]["id"]
        return ""
