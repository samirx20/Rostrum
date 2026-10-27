"""The anchor point on the canvas: drag the ring to move the point a layer turns and scales around, while the layer
stays exactly where it shows (Position follows: After Effects' "pan behind"). One drag = one undo step, made of the
same layer.anchor call an agent makes (rostrum2d/ops_anchor.py: it moves Position so the layer keeps its place; a layer with
keys timed on a marker writes the same fields through route.value_call, so the marker key there changes). The ring shows only while the settings panel's Anchor group is
open (`anchorOpen`), on a single layer that has a box; the maths of what moves is transform.turn. A slot mix-in for
Bridge2D (see rostrum_gui/parts.py); it uses handle_slots' grab.
"""
from __future__ import annotations

from PySide6.QtCore import Property, Signal, Slot
from rostrum2d.ops_anchor import moved
from rostrum2d.sizes import own_size
from rostrum_core.keys import marked

from . import bounds, drag_chip, route, transform as T

SNAP_PX = 5.0              # a screen distance: the anchor catches the edges and the middle (0, 50, 100 %) this close
CATCH = (0.0, 0.5, 1.0)


class AnchorSlots:
    anchorOpenChanged = Signal()           # told by Bridge2D whenever the settings rows change

    @Property(bool, notify=anchorOpenChanged)
    def anchorOpen(self):
        """The Anchor group is open in the settings panel: the canvas shows the anchor to drag."""
        return any(r.get("fold") == "Anchor" and r.get("open") for r in self.model.shown_rows)

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
        sx, sy = (-1 if b["fx"] else 1), (-1 if b["fy"] else 1)    # a mirrored layer: its own sides run the other way
        ax, ay = p["anchorX"] + sx * ldx / b["lw"], p["anchorY"] + sy * ldy / b["lh"]
        if not free:
            ax, ay = self._caught(ax, b["lw"]), self._caught(ay, b["lh"])
        drag_chip.say(self, f"{ax * 100:.0f} %, {ay * 100:.0f} %")      # where in the layer: 50 %, 50 % = its middle
        self._guard(lambda: self._drag.preview(self._anchor_calls(item, g, ax, ay)))

    def _anchor_calls(self, item, g, ax, ay) -> list[dict]:
        """The agents' layer.anchor call; for a layer with keys timed on a marker, the same fields (ops_anchor.moved's
        maths) each through route.value_call, which changes the marker key under the playhead and keeps it on its
        marker: layer.anchor sees no markers, so it would add a plain key beside it (and can't read the layer's values)."""
        t = self.own_t(item["id"])
        if not any(marked.marked(k) for k in item.get("keys", [])):
            return [{"op": "layer.anchor", "target": [item["id"]],
                     "args": {"x": round(ax, 4), "y": round(ay, 4), "keep_place": True, "at": t}}]
        p = g.p
        sets = {"anchorX": ax, "anchorY": ay}
        if not g.placed:
            dx, dy = moved(p, own_size(item["type"], p), ax, ay)
            sets.update(x=p["x"] + dx, y=p["y"] + dy)
        return [route.value_call(item, prop, round(v, 4), t) for prop, v in sets.items() if abs(v - p[prop]) > 1e-9]
