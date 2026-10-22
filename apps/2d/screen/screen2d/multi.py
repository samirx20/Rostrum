"""Several layers selected at once (Shift+click, or a rubber band on empty canvas). The kit's selection stays single:
that layer is the primary (the inspector shows it); the others are listed here. The selection clears itself when
the primary changes by any other route (layers panel, a click). A QObject part, read in QML as `backend.multi`."""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from . import bounds


class Multi(QObject):
    changed = Signal()

    def __init__(self, bridge):
        super().__init__(bridge)
        self.b, self._primary, self._extra = bridge, "", []
        bridge.selectionChanged.connect(self._on_select)
        bridge.outlineChanged.connect(self.changed)
        bridge.shownChanged.connect(self.changed)

    @Property("QVariantList", notify=changed)
    def boxes(self):
        """The box of every selected layer (the primary first): the outlines the canvas draws, as the picture on screen
        shows them (shown.py; a layer newer than the picture has none yet)."""
        ids = self.layers()
        by = {x["id"]: x for x in bounds.boxes(self.b.shown_placed(), self.b.shown_t())}
        return [by[i] for i in ids if i in by]

    @Property(int, notify=changed)
    def count(self):
        return len(self.layers())

    def layers(self) -> list[str]:
        layer = self.b.selectedLayer
        return [layer] + self._extra if layer else []

    def extras(self) -> list[str]:
        return list(self._extra) if self.b.selectedLayer == self._primary else []

    def _on_select(self):
        if self.b.selectedLayer != self._primary:
            self._extra = []
        self._primary = self.b.selectedLayer

    def _set(self, ids: list[str]):
        """Select these layers together: the first is the primary."""
        self._primary, self._extra = ids[0], ids[1:]
        self.b.select(ids[0])
        self.changed.emit()

    @Slot(str, result=bool)
    def has(self, layer_id):
        return layer_id in self.layers()

    @Slot(str)
    def toggle(self, layer_id):
        """Shift+click: add the layer to the selection, or take it out."""
        ids = self.layers()
        if layer_id in ids:
            ids.remove(layer_id)
        else:
            ids.append(layer_id)
        if ids:
            self._set(ids)

    @Slot(float, float, float, float, result=int)
    def boxSelect(self, x0, y0, x1, y1):
        """The rubber band (composition px): select every layer whose box touches it; a layer inside a selected
        group is left out (the group moves it). Returns how many."""
        lo_x, hi_x, lo_y, hi_y = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
        hit = [x["id"] for x in bounds.boxes(self.b.placed(), self.b._t)
               if (e := bounds.extent(x)) and e[0] <= hi_x and e[2] >= lo_x and e[1] <= hi_y and e[3] >= lo_y]
        hit = [i for i in reversed(hit) if not set(self._above(i)) & set(hit)]        # topmost first
        if hit:
            self._set(hit)
        else:
            self.b.select(self.b.comp_id)
        return len(hit)

    def _above(self, item_id) -> list[str]:
        out, doc = [], self.b.doc
        parent = doc.parent_of(item_id)[0]
        while doc.item(parent)["type"] != "comp":
            out.append(parent)
            parent = doc.parent_of(parent)[0]
        return out
