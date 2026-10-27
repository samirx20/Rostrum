"""The canvas's orange shape-setting handles (ShapeHandles.qml: corner radius dots, star / polygon / triangle / arc /
spiral diamonds and dots) and a text's wrap-width sides. Each drag is one doc.gesture = one undo step, made of the
same value.set calls an agent makes (route.value_call: an animated field gets a key at the playhead, a still one
changes); a field driven by an expression is refused, as the resize handles refuse it. Which handles a kind shows:
handle_kinds.SHAPE_HANDLES; where they sit and what a drag sets: shape_handle_geom.HANDLES. A slot mix-in for Bridge2D
(see rostrum_gui/parts.py); it uses handle_slots' grab.
"""
from __future__ import annotations

import math

from PySide6.QtCore import Slot

from . import bounds, route, transform as T
from .handle_kinds import KITS, SHAPE_HANDLES
from .shape_handle_geom import HANDLES, Grab

NEAR_EDGE = 16.0       # screen px: an edge square this close to a setting handle hides (the setting wins, CANVAS §3 rule 3)
NEAR_CORNER = 9.0      # screen px: a setting handle this close to a corner square hides (the corner wins)
EDGES = {"n": (0.5, 0.0), "e": (1.0, 0.5), "s": (0.5, 1.0), "w": (0.0, 0.5)}
CORNERS = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))


def wraps(g) -> bool:
    """A grab's sides set the wrap width (a text's kit), not a stretch."""
    return KITS.get(g.kit, {}).get("sides") == "wrap"


def _flips(b: dict) -> tuple[bool, bool]:
    """The box shows the shape mirrored across / up and down (a negative Stretch, or a mirrored group)."""
    return bool(b.get("fx")) != (b.get("pm") == "x"), bool(b.get("fy")) != (b.get("pm") == "y")


def shown(b: dict, p: dict, x: float, y: float) -> tuple[float, float]:
    """An own-px point as fractions across and down the box as it shows."""
    fx, fy = _flips(b)
    u, v = x / max(p["w"], 1e-6), y / max(p["h"], 1e-6)
    return (1 - u if fx else u), (1 - v if fy else v)


def own(b: dict, p: dict, u: float, v: float) -> tuple[float, float]:
    fx, fy = _flips(b)
    return (1 - u if fx else u) * p["w"], (1 - v if fy else v) * p["h"]


def placed(b: dict, p: dict, zoom: float, active: str = "") -> list[dict]:
    """The setting handles a shape shows in its box at this zoom: [{name, look, u, v}] (fractions of the box as shown).
    Hidden by size, and where a corner square would cover them; the one being dragged always shows."""
    bw, bh = b["w"] * zoom, b["h"] * zoom
    s = (bw / max(p["w"], 1e-6), bh / max(p["h"], 1e-6))
    out = []
    for name in SHAPE_HANDLES.get(p.get("shape"), ()):
        hd = HANDLES[name]
        u, v = shown(b, p, *hd.place(p, s))
        near = any(math.hypot((u - cu) * bw, (v - cv) * bh) < NEAR_CORNER for cu, cv in CORNERS)
        if name == active or (min(bw, bh) >= hd.hide_under and not near):
            out.append({"name": name, "look": hd.look, "u": round(u, 5), "v": round(v, 5)})
    return out


def covered(b: dict, zoom: float, handles: list[dict]) -> list[str]:
    """The edge squares a setting handle sits on: hidden, so the handle can be reached."""
    bw, bh = b["w"] * zoom, b["h"] * zoom
    return [k for k, (eu, ev) in EDGES.items() if any(math.hypot((o["u"] - eu) * bw, (o["v"] - ev) * bh) < NEAR_EDGE for o in handles)]


class ShapeHandleSlots:
    @Slot("QVariantMap", float, result="QVariantMap")
    def shapeHandles(self, box, fit):
        """What ShapeHandles.qml draws over a picked shape's box: {handles, covers, chip, active}."""
        layer = box.get("id")
        if not layer or layer != self.selectedLayer or box.get("type") != "shape" or not self.doc.has(layer):
            return {}
        p = route.shown_values(self.doc.item(layer), self.own_t(layer))
        g = self._grab if isinstance(self._grab, Grab) else None
        hs = placed(box, p, fit, g.name if g else "")
        return {"handles": hs, "covers": covered(box, fit, hs), "chip": g.state.get("chip", "") if g else "", "active": g.name if g else ""}

    @Slot(str, float, float, result=bool)
    def beginShapeHandle(self, name, u, v):
        """Press on setting handle `name` at (u, v), fractions of the box as shown (where the pointer is)."""
        hd = HANDLES.get(name)
        if hd is None:
            self._fail(f"Error: no shape handle {name!r} (handles: {', '.join(HANDLES)}).")
            return False
        b = self._handle_grab(hd.word.lower(), lambda g, item: hd.fields)
        if b is None:
            return False
        p = b.p
        if b.box.get("type") != "shape" or name not in SHAPE_HANDLES.get(p.get("shape"), ()):
            self._fail(f"Error: {self.label_of(self.doc.item(b.layer))} has no {name} handle.")
            return False
        zoom = self.view_zoom()
        s = (b.box["w"] * zoom / max(p["w"], 1e-6), b.box["h"] * zoom / max(p["h"], 1e-6))
        g = Grab(name, b.layer, p, *own(b.box, p, u, v), s)
        g.state["box"] = b.box
        return self._begin(f"{hd.word} {self.label_of(self.doc.item(b.layer))}", g)

    @Slot(float, float, bool, bool)
    def shapeHandleTo(self, u, v, shift=False, alt=False):
        """The pointer at (u, v), fractions of the box as shown. Shift: 15° steps on an angle; Alt on a radius dot:
        this corner only."""
        g = self._grab
        if self._drag is None or not isinstance(g, Grab):
            return
        hd, t = HANDLES[g.name], self.own_t(g.layer)
        sets = hd.drag(g, *own(g.state["box"], g.p, u, v), shift, alt)
        g.state["chip"] = hd.chip({**g.p, **sets})
        # fresh: on the values from before the drag, so Alt let go mid-drag puts the other corners back
        # (edit_call: value.set on a field keys may drive, the shape's own .set on a still one: Each corner, the kind)
        self._guard(lambda: self._drag.preview([route.edit_call(self.doc, g.layer, k, val, t) for k, val in sets.items()], fresh=True))

    def _wrap_by(self, g, item, dx, dy, alt):
        """A text's side dragged: its wrap width (boxWidth; auto texts start from the width they show), the letters keep
        their size and the lines re-flow; the other side stays put (Alt: the middle does)."""
        p, b = g.p, g.box
        dx, dy = bounds.parent_delta(b, dx, dy)
        hx, hy, ax, ay = bounds.parent_side(b, g.hx, g.hy)
        r = T.resize({"x": p["x"], "y": p["y"], "w": b["lw"], "h": b["lh"], "ax": ax, "ay": ay, "rot": b["lrot"]},
                     hx, hy, dx, dy, False, alt)
        sets = {"boxWidth": round(max(1.0, r["w"] / (abs(p["scale"] * p["scaleX"]) or 1.0)), 1)}
        if not g.placed and not r["cx"]:
            sets.update({"x": round(r["x"], 2), "y": round(r["y"], 2)})
        self._guard(lambda: self._drag.preview([route.value_call(item, k, v, self.own_t(item["id"])) for k, v in sets.items()], fresh=True))
