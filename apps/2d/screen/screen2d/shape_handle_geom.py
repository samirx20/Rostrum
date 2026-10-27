"""Where a picked shape's setting handles sit and what dragging one sets (ShapeHandles.qml, shape_handle_slots.py).
Pure maths in the shape's own px (0..w, 0..h), the way the engine draws the shape (engine/render/src/scene/shape_geom.rs:
angles 0° = up, clockwise; the point at angle a, k of the way out on the box's ellipse is cx + rx·k·sin a, cy − ry·k·cos a).
No Qt.

Each handle is one row of HANDLES: its look ("dot" / "diamond"), the box size on screen it hides under, the fields it
sets, where it sits (`place(p, s)`) and what a drag sets (`drag(g, x, y, shift, alt)`). `s` is (sx, sy), screen px per
own px. A drag reads where it was pressed (g.x0, g.y0) and the values at the press (g.p), so nothing jumps on the press.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

from .corner_rows import CORNERS
from .transform import short

DOT_IN = 10.0          # screen px: a radius dot sits at least this far in from its corner (it never sits on the square)
ROUND_IN = 18.0        # screen px: a roundness dot sits at least this far in from its corner (clear of the diamond there)
ARC_IN = 12.0          # screen px: the arc's end dots sit this far in from the edge
OUT = 12.0             # screen px: a count diamond sits this far out from its tip
COUNT_STEP = 12.0      # screen px of sideways drag per point or side
TURN = 15.0            # degrees: Shift on an angle
FULL = {"ellipse"}     # a whole ellipse is an arc from 0° round 360° (its first angle drag makes it one)


@dataclass
class Grab:
    name: str
    layer: str
    p: dict                      # the shape's values at the press
    x0: float                    # the press, own px
    y0: float
    s: tuple                     # screen px per own px (sx, sy) at the press
    last: float | None = None    # an angle drag: the pointer's last angle
    turned: float = 0.0          # ... and how far it has swept
    state: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Handle:
    look: str
    hide_under: float            # the box's short side on screen (px) under which it hides
    fields: tuple
    place: Callable
    drag: Callable
    chip: Callable               # the words while dragging, from the values after the drag ("Radius 24")
    word: str                    # what the undo step is called ("Undo Corner radius Card")


def _wh(p):
    return max(p.get("w", 0.0), 1e-6), max(p.get("h", 0.0), 1e-6)


def on(p, a, k=1.0):
    w, h = _wh(p)
    r = math.radians(a)
    return w / 2 + w / 2 * k * math.sin(r), h / 2 - h / 2 * k * math.cos(r)


def angle_of(p, x, y) -> float:
    """The angle (0° = up, clockwise) of an own-px point round the box's middle, read on its ellipse."""
    w, h = _wh(p)
    return math.degrees(math.atan2((x - w / 2) / (w / 2), -(y - h / 2) / (h / 2)))


def out_of(p, x, y, a) -> float:
    """How far out (0 = middle, 1 = the box's ellipse) an own-px point is, along angle a."""
    w, h = _wh(p)
    r = math.radians(a)
    return (x - w / 2) / (w / 2) * math.sin(r) - (y - h / 2) / (h / 2) * math.cos(r)


def _clamp(v, lo, hi):
    return min(max(v, lo), hi)


def _toward(pt, to, d_screen, s):
    """`pt` moved d_screen screen px toward `to` (own px both)."""
    dx, dy = to[0] - pt[0], to[1] - pt[1]
    ln = math.hypot(dx * s[0], dy * s[1]) or 1.0
    return pt[0] + dx / ln * d_screen, pt[1] + dy / ln * d_screen


def _short_side(p):
    return min(_wh(p)) / 2


# ---- corner radius (rectangle): a dot inside each corner ------------------------------------------------------------
def _corner_r(p, c):
    r = p.get("radius" + CORNERS[c][2]) if p.get("eachCorner") else p.get("radius")
    return _clamp(r or 0.0, 0.0, _short_side(p))


def _radius_place(c):
    def place(p, s):
        (cx, cy, _), (w, h) = CORNERS[c], _wh(p)
        r = _corner_r(p, c)
        return cx * w + (1 - 2 * cx) * max(r, DOT_IN / s[0]), cy * h + (1 - 2 * cy) * max(r, DOT_IN / s[1])
    return place


def _radius_drag(c):
    def drag(g, x, y, shift, alt):
        cx, cy, _ = CORNERS[c]
        along = ((x - g.x0) * (1 - 2 * cx) + (y - g.y0) * (1 - 2 * cy)) / 2           # along the diagonal, inward
        r = round(_clamp(_corner_r(g.p, c) + along, 0.0, _short_side(g.p)), 1)
        if not alt:                                                                     # all four corners
            return {**({"eachCorner": False} if g.p.get("eachCorner") else {}), "radius": r}
        each = {} if g.p.get("eachCorner") else {"eachCorner": True, **{"radius" + k[2]: _corner_r(g.p, n) for n, k in CORNERS.items()}}
        return {**each, "radius" + CORNERS[c][2]: r}                                  # this corner only (Each corner on)
    return drag


def _radius_chip(c):
    return lambda v: f"Radius {_n(_corner_r(v, c))}"


def _n(v):
    return f"{v:g}" if isinstance(v, (int, float)) else str(v)


# ---- a corner's roundness (triangle, polygon, star): a dot inward from the first corner -----------------------------
def _first_corner(p):
    """The first corner and its two neighbours, own px, per kind."""
    kind = p.get("shape")
    if kind == "triangle":
        w, h = _wh(p)
        return (p.get("tip", 0.5) * w, 0.0), (0.0, h), (w, h)
    n = max(3, round(p.get("sides" if kind == "polygon" else "points", 5)))
    if kind == "polygon":
        return on(p, 0), on(p, -360 / n), on(p, 360 / n)
    inner = _clamp(p.get("innerRadius", 0.5), 0.0, 1.0)
    return on(p, 0), on(p, -180 / n, inner), on(p, 180 / n, inner)


def _inward(p):
    """The first corner and the unit direction into the shape (the corner's bisector), own px."""
    v, a, b = _first_corner(p)
    ua, ub = [((q[0] - v[0]) / (math.hypot(q[0] - v[0], q[1] - v[1]) or 1), (q[1] - v[1]) / (math.hypot(q[0] - v[0], q[1] - v[1]) or 1)) for q in (a, b)]
    bx, by = ua[0] + ub[0], ua[1] + ub[1]
    ln = math.hypot(bx, by) or 1.0
    return v, (bx / ln, by / ln)


def _round_place(p, s):
    v, u = _inward(p)
    least = ROUND_IN / (math.hypot(u[0] * s[0], u[1] * s[1]) or 1.0)
    d = max(_clamp(p.get("radius", 0.0), 0.0, _short_side(p)), least)
    return v[0] + u[0] * d, v[1] + u[1] * d


def _round_drag(g, x, y, shift, alt):
    _, u = _inward(g.p)
    along = (x - g.x0) * u[0] + (y - g.y0) * u[1]
    return {"radius": round(_clamp(_clamp(g.p.get("radius", 0.0), 0.0, _short_side(g.p)) + along, 0.0, _short_side(g.p)), 1)}


# ---- counts (star points, polygon sides): a diamond just out from the first tip, dragged sideways ---------------------
def _count_place(p, s):
    w, h = _wh(p)
    return _toward(on(p, 0), (w / 2, h / 2), -OUT, s)


def _count_drag(name):
    def drag(g, x, y, shift, alt):
        return {name: int(_clamp(round(g.p.get(name, 5)) + round((x - g.x0) * g.s[0] / COUNT_STEP), 3, 60))}
    return drag


# ---- radial amounts (star inner radius, arc hole): a diamond dragged in or out ---------------------------------------
def _star_inner_angle(p):
    return 180 / max(3, round(p.get("points", 5)))


def _arc(p):
    """(start, sweep) of an arc; a whole ellipse is 0° round 360°."""
    return (0.0, 360.0) if p.get("shape") in FULL else (p.get("startAngle", 0.0), _clamp(p.get("sweep", 270.0), -360, 360))


def _hole_angle(p):
    a0, sw = _arc(p)
    return a0 + sw / 2


def _radial(name, angle_fn, hi=1.0):
    def place(p, s):
        return on(p, angle_fn(p), _clamp(p.get(name, 0.0), 0.0, 1.0))

    def drag(g, x, y, shift, alt):
        a = angle_fn(g.p)
        return {name: round(_clamp(g.p.get(name, 0.0) + out_of(g.p, x, y, a) - out_of(g.p, g.x0, g.y0, a), 0.0, hi), 3)}
    return place, drag


# ---- the triangle's tip: a diamond on the top corner, dragged along the top edge --------------------------------------
def _tip_place(p, s):
    return _clamp(p.get("tip", 0.5), 0, 1) * _wh(p)[0], 0.0


def _tip_drag(g, x, y, shift, alt):
    return {"tip": round(_clamp(g.p.get("tip", 0.5) + (x - g.x0) / _wh(g.p)[0], 0.0, 1.0), 3)}


# ---- angles (arc ends, spiral turns): dragged round the middle --------------------------------------------------------
def _swept(g, x, y) -> float:
    a = angle_of(g.p, x, y)
    if g.last is None:
        g.last = angle_of(g.p, g.x0, g.y0)
    g.turned += short(a - g.last)
    g.last = a
    return g.turned


def _fold(sweep):
    return math.fmod(sweep, 360.0) if abs(sweep) > 360 else sweep


def _end_place(end):
    def place(p, s):
        a0, sw = _arc(p)
        pt = on(p, a0 + sw if end else a0)
        w, h = _wh(p)
        return _toward(pt, (w / 2, h / 2), ARC_IN, s)
    return place


def _end_drag(end):
    def drag(g, x, y, shift, alt):
        a0, sw = _arc(g.p)
        d = _swept(g, x, y)
        if end:
            tip = a0 + sw + d
            sw = (round(tip / TURN) * TURN if shift else tip) - a0
        else:
            start = a0 + d
            start = round(start / TURN) * TURN if shift else start
            sw, a0 = sw - (start - a0), start
        sets = {"startAngle": round(math.fmod(a0, 360.0), 2), "sweep": round(_fold(sw), 2)}
        return {"shape": "arc", **sets} if g.p.get("shape") in FULL else sets      # an ellipse becomes an arc, same box
    return drag


def _turns_place(p, s):
    return on(p, p.get("turns", 3.0) * 360.0)


def _turns_drag(g, x, y, shift, alt):
    t = g.p.get("turns", 3.0) + _swept(g, x, y) / 360.0
    return {"turns": round(_clamp(round(t * 24) / 24 if shift else t, 0.05, 100.0), 3)}


def _pct(word, name):
    return lambda v: f"{word} {round(v.get(name, 0) * 100)} %"


_inner = _radial("innerRadius", _star_inner_angle)
_hole = _radial("hole", _hole_angle, 0.99)
_deg = lambda a: f"{round(a) or 0:g}"     # noqa: E731  whole degrees in the chip (never "-0")
_ARC_CHIP = lambda v: f"Start {_deg(v.get('startAngle', 0))}° · Sweep {_deg(v.get('sweep', 360))}°"   # noqa: E731

HANDLES = {
    **{f"radius:{c}": Handle("dot", 60, ("radius", "eachCorner") + tuple("radius" + k[2] for k in CORNERS.values()),
                             _radius_place(c), _radius_drag(c), _radius_chip(c), "Corner radius") for c in CORNERS},
    "radius": Handle("dot", 60, ("radius",), _round_place, _round_drag, lambda v: f"Radius {_n(v.get('radius', 0))}", "Corner radius"),
    "points": Handle("diamond", 48, ("points",), _count_place, _count_drag("points"), lambda v: f"{v.get('points')} points", "Points"),
    "sides": Handle("diamond", 48, ("sides",), _count_place, _count_drag("sides"), lambda v: f"{v.get('sides')} sides", "Sides"),
    "inner": Handle("diamond", 48, ("innerRadius",), *_inner, _pct("Inner radius", "innerRadius"), "Inner radius"),
    "tip": Handle("diamond", 48, ("tip",), _tip_place, _tip_drag, _pct("Tip", "tip"), "Tip"),
    "start": Handle("dot", 48, ("shape", "startAngle", "sweep"), _end_place(False), _end_drag(False), _ARC_CHIP, "Start angle"),
    "end": Handle("dot", 48, ("shape", "startAngle", "sweep"), _end_place(True), _end_drag(True), _ARC_CHIP, "Sweep"),
    "hole": Handle("diamond", 48, ("hole",), *_hole, _pct("Hole", "hole"), "Hole"),
    "turns": Handle("diamond", 48, ("turns",), _turns_place, _turns_drag, lambda v: f"{_n(round(v.get('turns', 0), 2))} turns", "Turns"),
}
