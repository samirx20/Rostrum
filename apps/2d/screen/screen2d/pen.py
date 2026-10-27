"""The pen tool (the tool strip's Pen, P) and editing a path layer's points. Every change is an operation; each is one change.

Drawing a new path: click = a corner point, press-drag = a smooth point (symmetric handles), click the first point
= close; Enter or Escape ends. The points live here (screen state) until the path ends; then one gesture adds the
path layer: `layer.add` (type path) + `path.set` (its d, box and place). A path needs two points or more.
Editing: a picked path shows its resize box; double-clicked (or Enter) its points show instead, and the handles of the selected point (click one); dragging one is one gesture of `path.set_point`
(handles move together unless Alt breaks the symmetry).
Coordinates from QML are composition px; a path's points are in its own box px (ops_path.to_parent, its inverse
here). A path inside a group is not offset by the group yet (as drawing and the selection box).
"""
from __future__ import annotations

from rostrum_gui import news

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
        self.b, self._draft, self._press, self._drag, self._grab = bridge, [], None, None, None
        self._oneside = self._moved = False      # a press on the last point: pull its out handle alone
        self._pick = ("", -1)         # (path layer, its selected point): only that point shows its handles
        self._editing = ""            # the path layer whose points are being edited (double-click / Enter); else its box shows
        told = news.relay(self)                             # only news: its points redo on it
        bridge.outlineChanged.connect(told)
        bridge.timeChanged.connect(told)
        bridge.toolChanged.connect(self._tool_changed)
        bridge.selectedItemsChanged.connect(told)   # canEditPoints follows the selection
        bridge.shownChanged.connect(told)           # the points follow the picture on screen (shown.py)            # on = the bridge's tool is "pen" (one source of truth)

    # ---- reads for QML ----------------------------------------------------------------------------------------
    @Property(bool, notify=changed)
    def on(self):
        return self.b.tool == "pen"

    @Property("QVariantList", notify=changed)
    def draft(self):
        return [_flat(p, i) for i, p in enumerate(self._draft)]

    @Property(bool, notify=changed)
    def editing(self):
        """The selected path shows its points (double-clicked or Enter), not its resize box. Esc goes back to the box."""
        return bool(self._editing) and self._editing == self.b.selectedLayer

    @Property(bool, notify=changed)
    def canEditPoints(self):
        """Enter would show the selected path's points: one path picked, its box showing, the pen off."""
        return not self.on and not self.editing and self._layer() is not None

    @Slot(bool)
    def editPoints(self, on):
        self._editing = self.b.selectedLayer if on and self._layer() else ""
        self.changed.emit()

    @Property(int, notify=changed)
    def selected(self):
        """The selected path's selected point (-1: none); the point just drawn while the pen is on."""
        if self.on:
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
        """The selected path's points and handles in composition px: [{i, x, y, inX, inY, outX, outY}], as the picture
        on screen shows the path (shown.py)."""
        live = self._layer() if self.editing else None
        item = live and self.b.shown_item(live["id"])
        if not item or item.get("type") != "path":
            return []
        try:
            subs = PD.to_points(item["d"])
        except ValueError:
            return []
        fn = to_parent(resolve(item, self.b.own_t(item["id"], self.b.shown_t())))
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
        """The pen's own switch is the bridge's tool: on = "pen", off = back to "move" (that ends the path)."""
        if on or self.on:
            self.b.setTool("pen" if on else "move")

    @Slot(float, float, float, result=str)
    def zone(self, x, y, near=CLOSE_PX):
        """What a pen press at (x, y) composition px would do, = the pointer's badge (CANVAS 1.3 pen table): "x" no
        path started (starts one), "" a new point, "close" over the first point, "caret" over the last point (drag:
        a one-sided handle, click: a corner again), "remove" over another point, "copy" (+) over the line: adds a
        point there. With no path being drawn, a picked path's points and line answer the same way (remove / add).
        `near`: composition px that count as "over" (the pen passes CLOSE_PX / zoom, so it is 8 screen px)."""
        return pen_zone(self._draft, self._picked_points(), x, y, near)[0]

    def _picked_points(self) -> list[dict]:
        """The picked path's points in composition px (as the pen draws them), when the pen could edit it."""
        item = self._layer()
        if item is None or any(k["prop"] == "d" for k in item.get("keys", [])):
            return []
        subs = PD.to_points(item["d"])
        fn = to_parent(resolve(item, self.b.own_t(item["id"])))
        out = []
        for s in subs:
            for k, p in enumerate(s["points"]):
                x, y = fn(p["x"], p["y"])
                ix, iy = fn(p["x"] + p["in"][0], p["y"] + p["in"][1])
                ox, oy = fn(p["x"] + p["out"][0], p["y"] + p["out"][1])
                out.append({"x": x, "y": y, "in": [ix - x, iy - y], "out": [ox - x, oy - y],
                            "next": k + 1 < len(s["points"]) or (s["closed"] and len(s["points"]) > 1),
                            "wrap": len(out) - k})      # the index of this subpath's first point (a closed one's last line)
        return out

    @Slot(float, float)
    @Slot(float, float, float)
    def press(self, x, y, near=CLOSE_PX):
        zone, where = pen_zone(self._draft, self._picked_points(), x, y, near)
        if zone == "close":
            self.finish(closed=True)
            return
        if self._draft and zone == "remove":
            del self._draft[where]
            self.changed.emit()
            return
        if self._draft and zone == "caret":
            self._press, self._oneside = (x, y), True      # pull: its out handle alone; a click: back to a corner
            self._moved = False
            return
        if self._draft and zone == "copy":
            self._draft[where:where + 2] = split_at(self._draft[where], self._draft[where + 1], x, y)
            self.changed.emit()
            return
        if not self._draft and zone in ("remove", "copy"):
            self._edit_picked(zone, where, x, y)
            return
        self._draft.append(PD._pt(x, y))
        self._press, self._oneside = (x, y), False
        self.changed.emit()

    def _edit_picked(self, zone, where, x, y):
        """The pen on a picked path (none being drawn): remove a point, or add one on its line keeping the curve.
        One change; the box follows (path.fit, as a point drag)."""
        item = self._layer()
        lid = item["id"]
        local = to_local(resolve(item, self.b.own_t(lid)))
        if zone == "remove":
            calls, label = [{"op": "path.remove_point", "target": [lid], "args": {"i": where}}], "Remove point"
        else:
            pts = self._picked_points()
            a = pts[where]
            j = where + 1 if where + 1 < len(pts) and a["wrap"] == pts[where + 1]["wrap"] else a["wrap"]
            b = pts[j]
            a2, mid, b2 = split_at(a, b, x, y)

            def handle(p, part):         # a handle in composition px → an offset in the layer's own px
                px, py = local(p["x"], p["y"])
                hx, hy = local(p["x"] + p[part][0], p["y"] + p[part][1])
                return round(hx - px, 3), round(hy - py, 3)
            mx, my = local(mid["x"], mid["y"])
            (aox, aoy), (bix, biy) = handle(a2, "out"), handle(b2, "in")
            (mix, miy), (mox, moy) = handle(mid, "in"), handle(mid, "out")
            calls = [{"op": "path.set_point", "target": [lid], "args": {"i": where, "outX": aox, "outY": aoy}},
                     {"op": "path.set_point", "target": [lid], "args": {"i": j, "inX": bix, "inY": biy}},
                     {"op": "path.add_point", "target": [lid], "args": {"after": where, "x": round(mx, 3), "y": round(my, 3),
                                                                        "inX": mix, "inY": miy}},
                     {"op": "path.set_point", "target": [lid], "args": {"i": where + 1, "outX": mox, "outY": moy}}]
            label = "Add point"
        self.b.guard(lambda: self.b.done(self.b.doc.apply(calls + self._fit_calls(lid), self.b.who, label=label), ""))
        self.changed.emit()

    @Slot(int)
    def removePoint(self, i):
        """Alt+click on a point of the path being edited: removes it (one change), when two would be left."""
        if len(self._picked_points()) > 2:
            self._edit_picked("remove", i, 0, 0)

    @Slot(float, float, float, result=bool)
    def addOnLine(self, x, y, near=CLOSE_PX):
        """A click on the line of the path being edited: a point there, the curve kept (pen+)."""
        zone, where = pen_zone([], self._picked_points(), x, y, near)
        if zone == "copy":
            self._edit_picked(zone, where, x, y)
        return zone == "copy"

    @Slot(float, float)
    def pull(self, x, y):
        """Press-drag: the out handle follows the pointer, the in handle mirrors it (a smooth point); pulled from the
        last point (caret), the out handle alone (a sharp turn after a curve)."""
        if self._press is None or math.dist((x, y), self._press) < SMOOTH_PX:
            return
        p = self._draft[-1]
        p["out"] = [x - p["x"], y - p["y"]]
        if self._oneside:
            self._moved = True
        else:
            p["in"] = [-p["out"][0], -p["out"][1]]
        self.changed.emit()

    @Slot()
    def release(self):
        if self._press is not None and self._oneside and not self._moved and self._draft:
            self._draft[-1]["out"] = [0.0, 0.0]               # a click on the last point: the next line leaves it sharp
            self.changed.emit()
        self._press, self._oneside = None, False

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
            self.setOn(False)           # made: back to Move, the path selected (no Done step)
        return ok

    def _tool_changed(self):
        """Another tool ends the path being drawn (kept, open), as Enter does."""
        if self._draft and not self.on:
            self.finish()
        self.changed.emit()

    # ---- editing the selected path's points: one drag = one gesture -------------------------------------------
    @Slot(int, str, result=bool)
    def beginPointDrag(self, i, part):
        """part: "point", "in" or "out"."""
        item = self._layer()
        if item is None:
            return False
        subs = PD.to_points(item["d"])
        s, k = PD.locate(subs, i)
        props = resolve(item, self.b.own_t(item["id"]))

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
        d, grab, self._drag, self._grab = self._drag, self._grab, None, None
        if d is not None:
            self.b.guard(lambda: self.b.done(d.end(calls=self._fit_calls(grab[0])), ""))

    def _fit_calls(self, lid: str) -> list[dict]:
        """The edit's last step: the box follows the reshaped path (`path.fit`: the drawing stays where it is), so the
        resize box, the outline and a click all agree with what is painted. Not when x or y has keys (fit refuses)."""
        item = self.b.doc.item(lid)
        if any(k["prop"] in ("x", "y") for k in item.get("keys", [])):
            return []
        return [{"op": "path.fit", "target": [lid], "args": {}}]


def _bez(a, b):
    """The cubic from point a to point b (points with relative in / out handles) as four (x, y)."""
    return ((a["x"], a["y"]), (a["x"] + a["out"][0], a["y"] + a["out"][1]),
            (b["x"] + b["in"][0], b["y"] + b["in"][1]), (b["x"], b["y"]))


def _at(c, t):
    u = 1 - t
    return tuple(u * u * u * c[0][i] + 3 * u * u * t * c[1][i] + 3 * u * t * t * c[2][i] + t * t * t * c[3][i] for i in (0, 1))


def nearest_t(a, b, x, y) -> tuple[float, float]:
    """(t, distance) of the point on the curve a → b nearest (x, y): 48 samples, then a finer look round the best."""
    c = _bez(a, b)
    best = min((math.dist(_at(c, i / 48), (x, y)), i / 48) for i in range(49))
    lo, hi = max(0.0, best[1] - 1 / 48), min(1.0, best[1] + 1 / 48)
    best = min(best, *((math.dist(_at(c, lo + (hi - lo) * i / 16), (x, y)), lo + (hi - lo) * i / 16) for i in range(17)))
    return best[1], best[0]


def split_at(a, b, x, y) -> list[dict]:
    """The curve a → b split at the place nearest (x, y), the drawn curve kept: [a, new point, b] with new handles
    (de Casteljau). A straight line stays straight: the new point is a corner."""
    t, _ = nearest_t(a, b, x, y)
    a, b = {**a, "in": list(a["in"]), "out": list(a["out"])}, {**b, "in": list(b["in"]), "out": list(b["out"])}
    if a["out"] == [0, 0] and b["in"] == [0, 0]:
        return [a, PD._pt(a["x"] + (b["x"] - a["x"]) * t, a["y"] + (b["y"] - a["y"]) * t), b]
    p0, p1, p2, p3 = _bez(a, b)

    def lerp(p, q):
        return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)
    q0, q1, q2 = lerp(p0, p1), lerp(p1, p2), lerp(p2, p3)
    r0, r1 = lerp(q0, q1), lerp(q1, q2)
    m = lerp(r0, r1)
    a["out"] = [q0[0] - a["x"], q0[1] - a["y"]]
    b["in"] = [q2[0] - b["x"], q2[1] - b["y"]]
    return [a, PD._pt(m[0], m[1], [r0[0] - m[0], r0[1] - m[1]], [r1[0] - m[0], r1[1] - m[1]]), b]


def pen_zone(draft: list[dict], picked: list[dict], x, y, near=CLOSE_PX) -> tuple[str, int]:
    """(badge, point or line index) for a pen press at (x, y): see Pen.zone. Points win over lines."""
    if draft:
        if len(draft) > 1 and math.dist((x, y), (draft[0]["x"], draft[0]["y"])) <= near:
            return "close", 0
        if math.dist((x, y), (draft[-1]["x"], draft[-1]["y"])) <= near:
            return "caret", len(draft) - 1
        for i, p in enumerate(draft[1:-1], 1):
            if math.dist((x, y), (p["x"], p["y"])) <= near:
                return "remove", i
        for i in range(len(draft) - 1):
            if nearest_t(draft[i], draft[i + 1], x, y)[1] <= near / 2:
                return "copy", i
        return "", -1
    for i, p in enumerate(picked):
        if len(picked) > 2 and math.dist((x, y), (p["x"], p["y"])) <= near:   # a path keeps two points at least
            return "remove", i
    for i, p in enumerate(picked):
        if p.get("next"):
            j = i + 1 if i + 1 < len(picked) and picked[i + 1]["wrap"] == p["wrap"] else p["wrap"]
            if nearest_t(p, picked[j], x, y)[1] <= near / 2:
                return "copy", i
    return "x", -1


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
    pen.editPoints(True)                      # a hand double-clicks the path first
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
    bridge.pen.editPoints(True)
    bridge.pen.selectPoint(int(rest[1]))
