"""The maths of the canvas handles: resize a layer's box from a corner or edge, and turn it. No Qt.

A box is described by `g`: x, y (where the anchor sits, in the layer's parent), w, h (the size on screen: own size
times scale), ax, ay (the anchor, 0..1 across the box) and rot (degrees, clockwise, about the anchor).
A handle is (hx, hy): -1 left / top, 1 right / bottom, 0 the middle (an edge handle has one 0).
"""
from __future__ import annotations

import math

MIN = 1.0       # the smallest a box gets, px


def turn(vx: float, vy: float, deg: float) -> tuple[float, float]:
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return c * vx - s * vy, s * vx + c * vy


def resize(g: dict, hx: int, hy: int, dx: float, dy: float, shift: bool = False, alt: bool = False,
           uniform: bool = False) -> dict:
    """The box after dragging handle (hx, hy) by (dx, dy) composition px: {x, y, w, h} (anchor position, size).
    The opposite side stays put (Alt: the centre does); Shift (or `uniform`, for a corner) keeps the proportion."""
    w0, h0 = g["w"], g["h"]
    ldx, ldy = turn(dx, dy, -g["rot"])                       # the drag along the box's own sides
    k = 2 if alt else 1
    w = max(MIN, w0 + hx * ldx * k) if hx else w0
    h = max(MIN, h0 + hy * ldy * k) if hy else h0
    if hx and hy and (shift or uniform):
        f = max(w / w0, h / h0)
        w, h = max(MIN, w0 * f), max(MIN, h0 * f)
    # where the fixed point sits across the box (0 left/top .. 1 right/bottom), then keep it where it was
    ux = 0.5 if (alt or not hx) else (0.0 if hx > 0 else 1.0)
    uy = 0.5 if (alt or not hy) else (0.0 if hy > 0 else 1.0)
    mx, my = turn((ux - g["ax"]) * w0 - (ux - g["ax"]) * w, (uy - g["ay"]) * h0 - (uy - g["ay"]) * h, g["rot"])
    return {"x": g["x"] + mx, "y": g["y"] + my, "w": w, "h": h}


def angle(ox: float, oy: float, px: float, py: float) -> float:
    """Degrees, clockwise from straight right, of the pointer (px, py) seen from the anchor (ox, oy)."""
    return math.degrees(math.atan2(py - oy, px - ox))


def short(d: float) -> float:
    """An angle change the short way round (-180..180)."""
    return (d + 180) % 360 - 180


def rotate(rot0: float, turned: float, shift: bool = False) -> float:
    """The new rotation after the pointer swept `turned` degrees (Shift: a multiple of 15°)."""
    r = rot0 + turned
    return round(r / 15) * 15 if shift else r


def resize_cursor(hx: int, hy: int, rot: float) -> str:
    """Which two-way arrow a resize knob shows: "hor", "ver", "fdiag" (top-left / bottom-right) or "bdiag", by the
    direction the knob points on screen (its side of the box turned by `rot`), snapped to 45 degrees."""
    octant = round((math.degrees(math.atan2(hy, hx)) + rot) / 45) % 4       # a line, so 180 degrees apart is the same
    return ("hor", "fdiag", "ver", "bdiag")[octant]
