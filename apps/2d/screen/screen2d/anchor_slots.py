"""The anchor point on the canvas: drag the ring to move the point a layer turns and scales around, while the layer
stays exactly where it shows (Position follows: After Effects' "pan behind"). One drag = one undo step, made of the
same value.set calls an agent makes (route.value_call). The ring shows only while the settings panel's Anchor group is
open (`anchorOpen`), on a single layer that has a box; the maths of what moves is transform.turn. A slot mix-in for
Bridge2D (see rostrum_gui/parts.py); it uses handle_slots' grab.
"""
from __future__ import annotations

from PySide6.QtCore import Property, Signal, Slot

from . import bounds, route, transform as T

SNAP_PX = 5.0              # a screen distance: the anchor catches the edges and the middle (0, 50, 100 %) this close
CATCH = (0.0, 0.5, 1.0)


class AnchorSlots:
    anchorOpenChanged = Signal()           # told by Bridge2D whenever the settings rows change

    @Property(bool, notify=anchorOpenChanged)
    def anchorOpen(self):
        """The Anchor group is open in the settings panel: the canvas shows the anchor to drag."""
        return any(r.get("fold") == "Anchor" and r.get("open") for r in self.model.rows)

    @Slot(result=bool)
    def beginAnchor(self):
        return self._handle_begin("Move anchor of", 0, 0, lambda g, item: ("anchorX", "anchorY") + (() if g.placed else ("x", "y")))

    def _caught(self, a: float, size: float) -> float:
        near = SNAP_PX / max(self.view_zoom(), 1e-6) / max(size, 1e-6)
        return next((c for c in CATCH if abs(a - c) <= near), a)

    @Slot(float, float, bool)
    def anchorBy(self, dx, dy, free=False):
        """Total drag from where it began, composition px. `free` (Ctrl): no catching of the edges and the middle."""
        g = self._grab
        if self._drag is None or not hasattr(g, "kit"):
            return
        item, p, b = self.doc.item(g.layer), g.p, g.box
        dx, dy = bounds.parent_delta(b, dx, dy)
        ldx, ldy = T.turn(dx, dy, -b["lrot"])                    # the drag along the layer's own sides
        ax, ay = p["anchorX"] + ldx / b["lw"], p["anchorY"] + ldy / b["lh"]
        if not free:
            ax, ay = self._caught(ax, b["lw"]), self._caught(ay, b["lh"])
        dx, dy = T.turn((ax - p["anchorX"]) * b["lw"], (ay - p["anchorY"]) * b["lh"], b["lrot"])
        sets = {"anchorX": round(ax, 4), "anchorY": round(ay, 4)}
        if not g.placed:
            sets.update({"x": round(p["x"] + dx, 2), "y": round(p["y"] + dy, 2)})
        self._guard(lambda: self._drag.preview([route.value_call(item, k, v, self.own_t(item["id"])) for k, v in sets.items()]))
