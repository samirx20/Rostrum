"""Where a layer's box sits in its parent's px at a time, from its evaluated values alone: the maths the select-then-act
operations (group.make, layer.align …) share. A layer's box runs from (0, 0) to (w, h) in its own px; its anchor sits at
(x, y) in the parent, then it is scaled and turned. mcp/geometry.py, screen2d/bounds.py and ops_path.to_parent use this
matrix (they carry the camera and the whole chain; this is the one flat step). A text's size is the engine's laid-out one. `painted`: the part of the box a click
picks (what the layer itself paints)."""
from __future__ import annotations

import math

from . import pathdata
from .drawing import canvas_size, frame_at
from .evaluate import resolve
from .sizes import own_size


def matrix(p: dict, w: float, h: float) -> tuple:
    """(a b c d e f): own px -> parent px, x' = a x + c y + e, y' = b x + d y + f."""
    r = math.radians(p["rotation"])
    c, s = math.cos(r), math.sin(r)
    sx, sy = p["scale"] * p["scaleX"], p["scale"] * p["scaleY"]
    ax, ay = p["anchorX"] * w, p["anchorY"] * h
    a, b, c2, d = c * sx, s * sx, -s * sy, c * sy
    return a, b, c2, d, p["x"] - (a * ax + c2 * ay), p["y"] - (b * ax + d * ay)


def corners(layer: dict, t: float = 0.0) -> list[tuple[float, float]]:
    """The four corners of the layer's box in its parent's px at its own time t."""
    p = resolve(layer, t)
    w, h = own_size(layer["type"], p)
    a, b, c, d, e, f = matrix(p, w, h)
    return [(a * x + c * y + e, b * x + d * y + f) for x, y in ((0, 0), (w, 0), (w, h), (0, h))]


def extent(points) -> tuple[float, float, float, float]:
    """(x0, y0, x1, y1) of some points."""
    xs, ys = zip(*points)
    return min(xs), min(ys), max(xs), max(ys)


def box(layer: dict, t: float = 0.0) -> tuple[float, float, float, float]:
    """(x0, y0, x1, y1) of a layer in its parent's px at time t (turned layers: the box round the turned corners)."""
    return extent(corners(layer, t))


def _drawn(p: dict, w: float, h: float):
    """A path's drawn extent in its own px: its curve's bounds widened by half the outline (the whole box when it has
    no points yet, so a new path can still be picked)."""
    cmds = pathdata.commands(p.get("d", ""))
    if not cmds:
        return (0.0, 0.0, w, h)
    x0, y0, x1, y1 = pathdata.bounds(cmds)
    r = p["strokeWidth"] / 2 if p.get("stroke") else 0.0
    return x0 - r, y0 - r, x1 + r, y1 + r


def painted(layer: dict, w: float, h: float, n: int, p: dict | None = None) -> tuple[float, float, float, float] | None:
    """The part of a layer's own box (x0, y0, x1, y1 in its own px) that its own picture covers, at composition frame n:
    what a click picks (the screen and the agents' look_at alike). A group paints nothing of its own (only its layers
    do); a path only its drawn curve (`p`: its evaluated values); a drawing only where the strokes of the drawing
    showing at frame n lie (with their brush size); None: nothing."""
    if layer["type"] == "group":
        return None
    if layer["type"] == "path" and p is not None:
        return _drawn(p, w, h)
    if layer["type"] != "drawing":
        return (0.0, 0.0, w, h)
    frame = frame_at(layer, n)
    cw, ch = canvas_size(layer)
    xs, ys = [], []
    for paint in (frame or {}).get("paints", []):
        if paint.get("visible", True):
            for s in paint.get("strokes", []):
                r = s.get("size", 0) / 2
                for q in s.get("points", []):
                    xs += [q[0] - r, q[0] + r]
                    ys += [q[1] - r, q[1] + r]
    if not xs:
        return None
    kx, ky = w / (cw or 1), h / (ch or 1)            # canvas px -> the layer's own px
    return max(0.0, min(xs)) * kx, max(0.0, min(ys)) * ky, min(cw, max(xs)) * kx, min(ch, max(ys)) * ky
