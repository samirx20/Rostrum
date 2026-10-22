"""Where a layer's box sits in its parent's px at a time, from its evaluated values alone: the maths the select-then-act
operations (group.make, layer.align …) share. A layer's box runs from (0, 0) to (w, h) in its own px; its anchor sits at
(x, y) in the parent, then it is scaled and turned (the same rule as mcp/geometry.py and screen2d/bounds.py, which
carry the camera and the whole chain; this is the one flat step). A text's size is the engine's laid-out one."""
from __future__ import annotations

import math

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
