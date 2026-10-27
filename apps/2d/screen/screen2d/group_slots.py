"""The canvas handles of SEVERAL selected layers: one box round all of them (Multi.groupBox) with the same knobs and turn
zones as a single layer. A resize scales every layer about the opposite side (Alt: the centre), a turn turns every layer
about the box's centre. One doc.gesture = one undo step, made of the same value.set calls an agent makes (route.value_call).
The maths is `union` / `resized` / `turned` below (No Qt). A slot mix-in for Bridge2D (see rostrum_gui/parts.py).

What a layer takes from a resize: shapes, images, groups change Width / Height; every other type changes Scale (a corner)
or Stretch X / Y (an edge), as one layer's handles do (handle_slots.py). Its position follows so it stays in the same
place inside the box. A layer turned a quarter still scales along the box's axes, not its own. Dragged past the
opposite side, the box mirrors (transform.resize, the one rule for every box): each layer's place mirrors across the
fixed edge, and its Stretch and turn as layer.flip's (rostrum2d/ops_flip.mirrored).
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Slot
from rostrum2d import ops_flip as flip
from rostrum2d.evaluate import resolve

from . import bounds, exprs, layout_drag, route, transform as T
from .handle_slots import OWN_SIZE


def union(boxes: list[dict]) -> dict:
    """The box round these layer boxes (composition px), unturned, anchored at its centre: {} for none."""
    if not boxes:
        return {}
    e = [bounds.extent(b) for b in boxes]
    x0, y0, x1, y1 = min(v[0] for v in e), min(v[1] for v in e), max(v[2] for v in e), max(v[3] for v in e)
    return {"id": "", "type": "group", "x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0, "rot": 0.0, "ax": 0.5, "ay": 0.5,
            "opacity": 1.0, "locked": False}


def resized(box: dict, hx: int, hy: int, dx: float, dy: float, shift=False, alt=False) -> tuple[float, float, tuple[float, float]]:
    """Dragging handle (hx, hy) of `box` by (dx, dy): the factors (fx, fy) every layer scales by (below 0: mirrored on
    that axis, past the opposite side), and the fixed point."""
    w, h = box["w"], box["h"]
    r = T.resize({"x": 0.0, "y": 0.0, "w": w, "h": h, "ax": 0.5, "ay": 0.5, "rot": 0.0}, hx, hy, dx, dy, shift, alt)
    fx = (-1 if r["cx"] else 1) * r["w"] / w
    fy = (-1 if r["cy"] else 1) * r["h"] / h
    px = box["x"] + w * (0.5 if (alt or not hx) else (0.0 if hx > 0 else 1.0))
    py = box["y"] + h * (0.5 if (alt or not hy) else (0.0 if hy > 0 else 1.0))
    return fx, fy, (px, py)


def mirrored(sets: dict, p: dict, fx: float, fy: float) -> dict:
    """`sets` (a layer's new values) when the box round it is mirrored (fx or fy below 0): the Stretch on that axis (of
    its new size) and its turn as rostrum2d/ops_flip.mirrored says (the one rule, layer.flip's)."""
    out = dict(sets)
    for k, v in flip.mirrored(p, fx < 0, fy < 0).items():
        if k != "rotation":
            out[k] = -out.get(k, p[k])
        elif v != p[k]:                                         # (no turn: nothing to write, no key)
            out[k] = v
    return out


def turned(point: tuple[float, float], centre: tuple[float, float], deg: float) -> tuple[float, float]:
    """`point` turned `deg` degrees clockwise about `centre`."""
    vx, vy = T.turn(point[0] - centre[0], point[1] - centre[1], deg)
    return centre[0] + vx, centre[1] + vy


@dataclass
class GroupGrab:
    layers: list                               # (id, values at the playhead, on-screen box) of each selected layer
    box: dict                                  # the box round them when the drag began
    hx: int = 0
    hy: int = 0
    last: float | None = None                  # turn: the pointer's last angle
    swept: float = 0.0


class GroupSlots:
    def _group_begin(self, label, hx, hy, fields_of) -> bool:
        ids = self._multi.layers()
        if len(ids) < 2:
            return False
        frames = {b["id"]: b for b in bounds.boxes(self.placed(), self._t)}
        grab = []
        for lay in ids:
            item = self.doc.item(lay)
            if lay not in frames or frames[lay]["w"] <= 0 or frames[lay]["h"] <= 0:
                self._fail(f"Error: {label.lower()}: {self.label_of(item)} has no box on screen at this time.")
                return False
            if layout_drag.begin(self.doc, self.placed(), lay, self._t) is not None:
                self._fail(f"Error: {label.lower()}: {self.label_of(item)} is placed by an auto layout; select it alone to change it.")
                return False
            for prop in fields_of(item):
                if exprs.drives(item, prop):
                    self._fail(f"Error: {label.lower()}: {self.label_of(item)}'s {prop} is driven by an expression; clear it first (the cross on its row).")
                    return False
            grab.append((lay, resolve(self.placed_item(lay), self._t), frames[lay]))   # keys on a marker placed
        self._frames = frames
        g = GroupGrab(grab, union([f for _, _, f in grab]), int(hx), int(hy))
        return self._begin(f"{label} {len(ids)} layers", g)

    @Slot(int, int, result=bool)
    def beginGroupResize(self, hx, hy):
        def fields_of(item):
            return (("w", "h") if item["type"] in OWN_SIZE else ("scale",)) + ("scaleX", "scaleY", "x", "y")
        return self._group_begin("Resize", hx, hy, fields_of)

    @Slot(float, float, bool, bool)
    def groupResizeBy(self, dx, dy, shift=False, alt=False):
        """Total drag from where it began, composition px (Shift = same proportion from a corner, Alt = from the centre)."""
        g = self._grab
        if self._drag is None or not isinstance(g, GroupGrab):
            return
        fx, fy, (px, py) = resized(g.box, g.hx, g.hy, dx, dy, shift, alt)
        calls = []
        for lay, p, b in g.layers:
            item = self.doc.item(lay)
            ax, ay = b["x"] + b["ax"] * b["w"], b["y"] + b["ay"] * b["h"]            # the anchor on screen
            mx, my = self._parent_drag(lay, px + (ax - px) * fx - ax, py + (ay - py) * fy - ay)
            sets = {"x": p["x"] + mx, "y": p["y"] + my}
            if item["type"] in OWN_SIZE:
                sets.update({"w": p["w"] * abs(fx)} if g.hx else {})
                sets.update({"h": p["h"] * abs(fy)} if g.hy else {})
            elif g.hx and g.hy:
                sets["scale"] = p["scale"] * (abs(fx) + abs(fy)) / 2
            else:
                sets.update({"scaleX": p["scaleX"] * abs(fx)} if g.hx else {"scaleY": p["scaleY"] * abs(fy)})
            calls += [route.value_call(item, k, round(v, 2), self.own_t(lay)) for k, v in mirrored(sets, p, fx, fy).items()]
        self._guard(lambda: self._drag.preview(calls, fresh=True))      # on the values from before: a mirror undone mid-drag goes back

    @Slot(result=bool)
    def beginGroupRotate(self):
        return self._group_begin("Rotate", 0, 0, lambda item: ("rotation", "x", "y"))

    @Slot(float, float, bool)
    def groupRotateTo(self, px, py, shift=False):
        """The pointer's place in composition px: every layer turns about the box's centre by the angle it swept."""
        g = self._grab
        if self._drag is None or not isinstance(g, GroupGrab):
            return
        b = g.box
        c = (b["x"] + b["w"] / 2, b["y"] + b["h"] / 2)
        a = T.angle(*c, px, py)
        g.swept += 0.0 if g.last is None else T.short(a - g.last)
        g.last = a
        deg = (round(g.swept / 15) * 15) if shift else g.swept
        calls = []
        for lay, p, lb in g.layers:
            item = self.doc.item(lay)
            at = (lb["x"] + lb["ax"] * lb["w"], lb["y"] + lb["ay"] * lb["h"])
            nx, ny = turned(at, c, deg)
            dx, dy = self._parent_drag(lay, nx - at[0], ny - at[1])
            calls += [route.value_call(item, k, round(v, 2), self.own_t(lay))
                      for k, v in (("x", p["x"] + dx), ("y", p["y"] + dy), ("rotation", p["rotation"] + deg))]
        self._guard(lambda: self._drag.preview(calls))
