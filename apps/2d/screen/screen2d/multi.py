"""The selected layers as the canvas and the layers list use them: the kit's ONE selection (`bridge.selection`,
`selectMany`; the primary first) read as layers, their boxes for the outlines, and the ways to change it by hand:
Shift+click on the canvas, Ctrl+click / Shift+click in the layers list, the rubber band, and which piece a click picks
(picking.py). A QObject part, read in QML as `backend.multi`."""
from __future__ import annotations

from rostrum_gui import news

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_gui.selection_rules import box, click

from . import bounds, picking
from .group_slots import union


class Multi(QObject):
    changed = Signal()

    def __init__(self, bridge):
        super().__init__(bridge)
        self.b = bridge
        told = news.relay(self)                             # only news: the overlays redo their handles on it
        for s in (bridge.selectedItemsChanged, bridge.outlineChanged, bridge.shownChanged):
            s.connect(told)

    @Property("QVariantList", notify=changed)
    def boxes(self):
        """The box of every selected layer (the primary first): the outlines the canvas draws, as the picture on screen
        shows them (shown.py; a layer newer than the picture has none yet)."""
        by = {x["id"]: x for x in self.b.shown_boxes()}
        return [by[i] for i in self.layers() if i in by]

    @Property("QVariantMap", notify=changed)
    def groupBox(self):
        """The one box round all the selected layers (their handles: group_slots.py); {} for fewer than two."""
        boxes = self.boxes
        return union(boxes) if len(boxes) > 1 else {}

    @Property("QVariantMap", notify=changed)
    def ride(self):
        """The path the primary selected layer (or the camera) rides, with the words the canvas shows for it
        (its `id`, `label`). {} when the selection rides nothing."""
        ids = self.layers()
        rider = self.b.doc.item(ids[0]) if ids else {}
        path = rider.get("ridePath", "")
        if not path or not self.b.doc.has(path):
            return {}
        what = "Camera" if rider.get("type") == "camera" else rider.get("name") or ids[0]
        return {"id": path, "label": f"{what} rides {self.b.doc.item(path).get('name') or path}"}

    @Property(int, notify=changed)
    def count(self):
        return len(self.layers())

    @Property("QVariantList", notify=changed)
    def ids(self):
        """The selected layers (an effect, mask or key selected counts as its layer): the rows the list lights."""
        return self.layers()

    def layers(self) -> list[str]:
        out = []
        for i in self.b.selection:
            layer = bounds.layer_of(self.b.doc, i) if self.b.doc.has(i) else ""
            if layer and layer not in out:
                out.append(layer)
        return out

    def extras(self) -> list[str]:
        return self.layers()[1:]

    def _set(self, ids: list[str]):
        """Select these layers together: the first is the primary (none: the composition)."""
        self.b.selectMany(ids) if ids else self.b.select(self.b.comp_id)

    @Slot(str, result=bool)
    def has(self, layer_id):
        return layer_id in self.layers()

    @Slot(str)
    def toggle(self, layer_id):
        """Shift+click on the canvas, Ctrl+click in the list: add the layer to the selection, or take it out."""
        self._set(click(self.layers(), None, layer_id, {"ctrl"}, "list")[0])      # the kit's rule (INTERACTION 1.3)

    @Slot(str)
    def selectRange(self, layer_id):
        """Shift+click in the layers list: every layer row from the primary to this one, as the list shows them."""
        rows = [r["id"] for r in self.b.layers if r["row"] == "layer"]
        here = self.layers()[0] if self.layers() else layer_id
        run = click(self.layers(), here, layer_id, {"shift"}, "list", rows)[0]      # the kit's rule (INTERACTION 1.3)
        self._set([here] + [i for i in run if i != here] if here in run else run)     # the primary stays first

    @Slot(float, float, str, result=str)
    def target(self, x, y, mode):
        """What a click at (x, y) composition px would select, without selecting it ("" = nothing painted there).
        mode: "click" (the outermost group, or the piece among its siblings once inside it), "deep" (Ctrl: the piece
        itself), "in" (double-click: one level further in than the selection)."""
        chain = bounds.pick_chain(self.b.placed(), self.b._t, x, y)
        sel = self.layers()[0] if self.layers() else ""
        return picking.choose(chain, sel, picking.groups_of(self.b.doc, sel) if sel else [], mode)

    @Slot(float, float, str, result=str)
    def pick(self, x, y, mode):
        """A click at (x, y): select what `target` says (nothing painted there: the composition)."""
        hit = self.target(x, y, mode)
        self._set([hit] if hit else [])
        return hit

    @Slot(float, float, float, float, str, result=int)
    def boxSelect(self, x0, y0, x1, y1, mods=""):
        """The rubber band (composition px), by the kit's rule (selection_rules.box, INTERACTION 1.3): every layer it
        touches, as its outermost group (never a locked one); `mods` "shift" adds them to the selection, "ctrl" picks
        the deepest pieces instead (not groups). Returns how many are selected."""
        lo_x, hi_x, lo_y, hi_y = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
        found = [x for x in bounds.boxes(self.b.placed(), self.b._t) if not x["locked"]
                 and (e := bounds.extent(x)) and e[0] <= hi_x and e[2] >= lo_x and e[1] <= hi_y and e[3] >= lo_y]
        touched = [((x["up"] or (x["id"],))[0], x["id"]) for x in reversed(found) if x["type"] != "group"]   # topmost first
        ids = box(self.layers(), touched, set(mods.split()), "canvas")
        self._set(ids)
        return len(ids)
