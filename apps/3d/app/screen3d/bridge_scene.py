"""The scene list and the selection for Bridge3D (a slot mix-in): the rows with their keys, which item the selection
belongs to, Ctrl / Shift picking in the list."""
from __future__ import annotations

from PySide6.QtCore import Property, Slot
from rostrum_gui.selection_rules import click

from . import outline, route, scene_state
from .bridge_signals import Signals3D

S = Signals3D


class SceneMixin:
    @Property("QVariantMap", notify=S.outlineChanged)
    def sceneState(self):
        """What the panel shows with nothing selected: {shot: {id, label, rows}, sky: {id, label} or {}} (scene_state)."""
        return scene_state.scene_state(self.doc.data, self.shotInfo)

    @Property("QVariantList", notify=S.outlineChanged)
    def sceneRows(self):
        """The scene list, its keys on the same rows (outline.scene_rows)."""
        return outline.scene_rows(self.doc.data, self._folded, self.selectedOwner, self._info["fps"])

    @Property("QVariantList", notify=S.outlineChanged)
    def materials(self):
        return outline.named(self.doc.data, "materials")

    @Property(str, notify=S.outlineChanged)
    def selectedOwner(self):
        """The scene item the selection belongs to: itself, or the item of a selected key ("" for a material, shot)."""
        if not self._sel:
            return ""
        it = self.doc.item(self._sel)
        if it["type"] == "key":
            return self.doc.parent_of(self._sel)[0]
        return self._sel if it["type"] in route.F.ITEMS else ""

    @Property("QVariantList", notify=S.outlineChanged)
    def selectedRows(self):
        """The scene items selected together (the primary first): the scene list lights them all."""
        return [i for i in self.selection if i in self._item_ids()]

    def _item_ids(self) -> set:
        return {it["id"] for it in outline.scene_items(self.doc.data)}

    @Slot(str)
    def toggleInSelection(self, item_id):
        """Ctrl+click in the scene list: add the item to the selection, or take it out."""
        self.selectMany(click(self.selection, None, item_id, {"ctrl"}, "list")[0] or [])

    @Slot(str)
    def selectRange(self, item_id):
        """Shift+click in the scene list: every item row from the primary to this one, as the list shows them."""
        order = [r["id"] for r in self.sceneRows if r["row"] == "layer"]
        here = self.selected if self.selected in order else item_id
        run = click(self.selection, here, item_id, {"shift"}, "list", order)[0]
        self.selectMany([here] + [i for i in run if i != here] if here in run else run)

    @Slot(str)
    def toggleFold(self, item_id):
        self._folded ^= {item_id}
        self.outlineChanged.emit()
