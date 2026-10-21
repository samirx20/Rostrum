"""The pen tool (Design page) and editing a path layer's points. Every change is an operation; each is one change.

Drawing a new path: click = a corner point, press-drag = a smooth point (symmetric handles), click the first point
= close; Enter or Escape ends. The points live here (screen state) until the path ends; then one gesture adds the
path layer: `layer.add` (type path) + `path.set` (its d, box and place). A path needs two points or more.
Editing: with a path layer selected its points show, and the handles of the selected point (click one); dragging one is one gesture of `path.set_point`
(handles move together unless Alt breaks the symmetry).
Coordinates from QML are composition px; a path's points are in its own box px (ops_path.to_parent, its inverse
here). A path inside a group is not offset by the group yet (as drawing and the selection box).
"""
from __future__ import annotations

import math

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum2d import pathdata as PD
from rostrum2d.evaluate import resolve
from rostrum2d.ops_path import to_parent
from rostrum_core import ids
from rostrum_core.tree import index
from rostrum_gui.edits import Drag

CLOSE_PX = 8.0           # composition px: a click this close to the first point closes the path
SMOOTH_PX = 2.0          # a press that moves less than this is a click (a corner)


def to_local(props: dict):
    """Composition px → the layer's own box px (the inverse of ops_path.to_parent)."""
    ax, ay = props["anchorX"] * props["w"], props["anchorY"] * props["h"]
    sx, sy = props["scale"] * props["scaleX"] or 1e-9, props["scale"] * props["scaleY"] or 1e-9
    c, s = math.cos(math.radians(props["rotation"])), math.sin(math.radians(props["rotation"]))

    def fn(x, y):
        u, v = x - props["x"], y - props["y"]
        return (c * u + s * v) / sx + ax, (-s * u + c * v) / sy + ay
    return fn


def new_path_calls(comp_id: str, pid: str, points: list[dict], closed: bool) -> list[dict]:
    """layer.add + path.set for points in composition px: the box hugs the curve, the anchor at its centre."""
    d = PD.from_points([{"closed": closed, "points": points}])
    moved, (x0, y0, w, h) = PD.fit(PD.commands(d))
    look = {"filled": closed, "stroke": True}
    return [{"op": "layer.add", "target": [comp_id], "args": {"type": "path", "id": pid}},
            {"op": "path.set", "target": [pid], "args": {"d": PD.write(moved), "w": w, "h": h,
                                                         "x": x0 + w / 2, "y": y0 + h / 2, **look}}]


class Pen(QObject):
    changed = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.b, self._on, self._draft, self._press, self._drag, self._grab = bridge, False, [], None, None, None
        self._pick = ("", -1)         # (path layer, its selected point): only that point shows its handles
        bridge.outlineChanged.connect(self.changed)
        bridge.timeChanged.connect(self.changed)
        bridge.pageChanged.connect(lambda: self.setOn(False) if bridge.page != "design" and self._on else None)

    # ---- reads for QML ----------------------------------------------------------------------------------------
    @Property(bool, notify=changed)
    def on(self):
        return self._on

    @Property("QVariantList", notify=changed)
    def draft(self):
        return [_flat(p, i) for i, p in enumerate(self._draft)]

    @Property(int, notify=changed)
    def selected(self):
        """The selected path's selected point (-1: none); the point just drawn while the pen is on."""
        if self._on:
            return len(self._draft) - 1
        return self._pick[1] if self._pick[0] == self.b.selectedLayer else -1

    @Slot(int)
    def selectPoint(self, i):
        self._pick = (self.b.selectedLayer, i)
        self.changed.emit()

    def _layer(self) -> dict | None:
        lid = self.b.selectedLayer
        item = self.b.doc.item(lid) if lid else None
        return item if item and item["type"] == "path" else None

    @Property("QVariantList", notify=changed)
    def points(self):
        """The selected path's points and handles in composition px: [{i, x, y, inX, inY, outX, outY}]."""
        item = self._layer()
        if item is None:
            return []
        try:
            subs = PD.to_points(item["d"])
        except ValueError:
            return []
        fn = to_parent(resolve(item, self.b._t))
        out = []
        for p in (p for s in subs for p in s["points"]):
            x, y = fn(p["x"], p["y"])
            ix, iy = fn(p["x"] + p["in"][0], p["y"] + p["in"][1])
            ox, oy = fn(p["x"] + p["out"][0], p["y"] + p["out"][1])
            out.append({"i": len(out), "x": x, "y": y, "inX": ix, "inY": iy, "outX": ox, "outY": oy,
                        "smooth": p["in"] != [0, 0] or p["out"] != [0, 0]})
        return out

    # ---- the pen: a new path ----------------------------------------------------------------------------------
    @Slot(bool)
    def setOn(self, on):
        if not on:
            self.finish()
        self._on = on
        self.changed.emit()

    @Slot(float, float)
    def press(self, x, y):
        if self._draft and math.dist((x, y), (self._draft[0]["x"], self._draft[0]["y"])) <= CLOSE_PX and len(self._draft) > 1:
            self.finish(closed=True)
            return
        self._draft.append(PD._pt(x, y))
        self._press = (x, y)
        self.changed.emit()

    @Slot(float, float)
    def pull(self, x, y):
        """Press-drag: the out handle follows the pointer, the in handle mirrors it (a smooth point)."""
        if self._press is None or math.dist((x, y), self._press) < SMOOTH_PX:
            return
        p = self._draft[-1]
        p["out"] = [x - p["x"], y - p["y"]]
        p["in"] = [-p["out"][0], -p["out"][1]]
        self.changed.emit()

    @Slot()
    def release(self):
        self._press = None

    @Slot(result=bool)
    def finish(self, closed=False) -> bool:
        """End the path: one change adds it (two points or more), then it is selected; fewer points: nothing."""
        pts, self._draft, self._press = self._draft, [], None
        self.changed.emit()
        if len(pts) < 2:
            return False
        pid = ids.counted(index(self.b.doc.data, self.b.doc.kind.lists), "path")
        ok = self.b.guard(lambda: self.b.done(self.b.doc.apply(
            new_path_calls(self.b.comp_id, pid, pts, closed), self.b.who, label="Draw path"), ""))
        if ok:
            self.b.select(pid)
        return ok

    # ---- editing the selected path's points: one drag = one gesture -------------------------------------------
    @Slot(int, str, result=bool)
    def beginPointDrag(self, i, part):
        """part: "point", "in" or "out"."""
        item = self._layer()
        if item is None:
            return False
        subs = PD.to_points(item["d"])
        s, k = PD.locate(subs, i)
        props = resolve(item, self.b._t)

        def go():
            self._drag = Drag(self.b.doc, self.b.who, "Move point" if part == "point" else "Move handle")
            self._grab = (item["id"], i, part, dict(subs[s]["points"][k]), to_local(props), to_parent(props))
        return self.b.guard(go)

    @Slot(float, float, bool)
    def dragBy(self, dx, dy, alt=False):
        """Total offset from where the drag started, composition px. Alt: move one handle alone."""
        if self._drag is None:
            return
        lid, i, part, p, local, parent = self._grab
        if part == "point":
            x, y = parent(p["x"], p["y"])
            nx, ny = local(x + dx, y + dy)
            args = {"x": round(nx, 3), "y": round(ny, 3)}
        else:
            hx, hy = parent(p["x"] + p[part][0], p["y"] + p[part][1])
            nx, ny = local(hx + dx, hy + dy)
            args = {f"{part}X": round(nx - p["x"], 3), f"{part}Y": round(ny - p["y"], 3), "mirror": not alt}
        self.b.guard(lambda: self._drag.preview([{"op": "path.set_point", "target": [lid], "args": {"i": i, **args}}]))

    @Slot()
    def endPointDrag(self):
        d, self._drag, self._grab = self._drag, None, None
        if d is not None:
            self.b.guard(lambda: self.b.done(d.end(), ""))


def _flat(p, i):
    return {"i": i, "x": p["x"], "y": p["y"], "inX": p["x"] + p["in"][0], "inY": p["y"] + p["in"][1],
            "outX": p["x"] + p["out"][0], "outY": p["y"] + p["out"][1], "smooth": p["out"] != [0, 0]}


# ---- screen steps (steps.py) -------------------------------------------------------------------------------------
def steps_pen(bridge, step, rest):
    """pen <x,y> <x,y,hx,hy> … [close]: one new path, as the clicks and drags of a hand."""
    pen, close = bridge.pen, rest[-1:] == ["close"]
    pen.setOn(True)
    for tok in rest[:-1] if close else rest:
        v = [float(n) for n in tok.split(",")]
        if len(v) not in (2, 4):
            raise ValueError(f"step {step!r}: a point is x,y or x,y,hx,hy (got {tok!r})")
        pen.press(v[0], v[1])
        if len(v) == 4:
            pen.pull(v[2], v[3])
        pen.release()
    if close:
        first = pen.draft[0]
        pen.press(first["x"], first["y"])
    elif not pen.finish():
        raise RuntimeError(f"step {step!r}: a path needs two points or more")
    pen.setOn(False)


def steps_pointdrag(bridge, step, rest):
    """pointdrag <layer> <i> <dx> <dy> [in|out]: drag a point (or its handle) of a path layer, one change."""
    bridge.select(rest[0])
    pen, part = bridge.pen, rest[4] if len(rest) > 4 else "point"
    if not pen.beginPointDrag(int(rest[1]), part):
        raise RuntimeError(f"step {step!r}: {rest[0]} is not a path layer")
    for f in (0.5, 1.0):
        pen.dragBy(float(rest[2]) * f, float(rest[3]) * f, False)
    pen.endPointDrag()


def steps_pointpick(bridge, step, rest):
    """pointpick <layer> <i>: select a path layer's point, so its handles show."""
    bridge.select(rest[0])
    if bridge.pen._layer() is None:
        raise RuntimeError(f"step {step!r}: {rest[0]} is not a path layer")
    bridge.pen.selectPoint(int(rest[1]))
