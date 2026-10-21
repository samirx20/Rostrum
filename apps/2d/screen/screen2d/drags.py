"""Rostrum2D's two drags: move a layer on the canvas (or, in an auto layout, change its slot) and move a key on the
timeline. Each is one doc.gesture = one undo step. A slot mix-in for Bridge2D (see rostrum_gui/parts.py)."""
from __future__ import annotations

from PySide6.QtCore import Slot
from rostrum_core.keys import keys_of
from rostrum2d.evaluate import resolve
from rostrum_gui.edits import Drag
from rostrum_gui.parts import SlotMixin

from . import bounds, exprs, layout_drag, route


class DragSlots(SlotMixin):
    @Slot(result=bool)
    def beginMove(self):
        layer = bounds.layer_of(self.doc, self._sel) if self._sel else ""
        if not layer:
            return False
        slots = layout_drag.begin(self.doc, self.comp(), layer, self._t)      # in an auto layout: change slot
        label = f"Move {self.label_of(self.doc.item(layer))}"
        if slots:
            return self._begin(label, slots)
        if any(exprs.drives(self.doc.item(layer), a) for a in ("x", "y")):
            self._fail("Error: move: x or y is driven by an expression; clear it first (the cross on its row).")
            return False
        p = resolve(self.doc.item(layer), self._t)
        return self._begin(label, (layer, p["x"], p["y"]))

    @Slot(float, float)
    def moveBy(self, dx, dy):
        """Total offset from where the drag started, in composition px: value.set x / y at the playhead (in an
        auto layout: layer.arrange to the slot nearest the pointer)."""
        if self._drag is None or self._grab is None:
            return
        if isinstance(self._grab, dict):
            self._guard(lambda: self._drag.preview([layout_drag.call(self.doc, self._grab, dx, dy)]))
            return
        layer, x0, y0 = self._grab
        item = self.doc.item(layer)
        self._guard(lambda: self._drag.preview([route.value_call(item, "x", round(x0 + dx, 2), self._t),
                                                route.value_call(item, "y", round(y0 + dy, 2), self._t)]))

    @Slot(str, result=bool)
    def beginKeyDrag(self, key_id):
        self.select(key_id)
        return self._begin("Move key", key_id)

    @Slot(float, float)
    def keyDragTo(self, t, snap=0.0):
        """`snap`: seconds within which the key lands on a shared marker instead of the nearest frame."""
        if self._drag is None or not isinstance(self._grab, str):
            return
        c, key = self.comp(), self.doc.item(self._grab)
        on = self.marks.snap(t, snap)
        t = min(max(on if on != t else round(t * c["fps"]) / c["fps"], 0.0), c["duration"])
        owner = self.doc.item(self.doc.parent_of(key["id"])[0])
        if any(k["id"] != key["id"] and abs(k["t"] - t) < 1e-6 for k in keys_of(owner, key["prop"])):
            return                       # another key of this field is there: stay at the last free time
        self._guard(lambda: self._drag.preview([{"op": "key.set", "target": [key["id"]], "args": {"t": t}}]))

    @Slot()
    def endDrag(self):
        d, self._drag, self._grab = self._drag, None, None
        if d is not None:
            self._guard(lambda: self._done(d.end(), ""))

    def _begin(self, label, grab) -> bool:
        self.endDrag()

        def go():
            self._drag, self._grab = Drag(self.doc, self.who, label), grab
        return self._guard(go)
