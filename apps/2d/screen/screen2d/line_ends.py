"""Dragging one end of a line or an arrow (handle_kinds.py "ends"). No Qt.

The line runs along the middle of its box, from the box's left side to its right. Dragging an end moves that end by the
pointer's drag; the other end stays (Alt: the middle stays, the other end mirrors). The length and the turn follow;
Shift snaps the turn to 15 degree steps. Everything is in the layer's parent's px, as transform.resize.
"""
from __future__ import annotations

import math

from .transform import MIN, turn


def drag_end(g: dict, hx: int, dx: float, dy: float, shift: bool = False, alt: bool = False) -> dict:
    """g: x, y (where the anchor sits), w (the length), h (the thickness), ax, ay, rot. hx: 1 the right end, -1 the left.
    Returns {x, y, w, rot}: the anchor's new place, the new length and turn (degrees, clockwise)."""
    cy = (0.5 - g["ay"]) * g["h"]
    start = tuple(a + b for a, b in zip(turn(-g["ax"] * g["w"], cy, g["rot"]), (g["x"], g["y"])))
    end = tuple(a + b for a, b in zip(turn((1 - g["ax"]) * g["w"], cy, g["rot"]), (g["x"], g["y"])))
    mid = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
    if hx > 0:
        end = (end[0] + dx, end[1] + dy)
        start = (2 * mid[0] - end[0], 2 * mid[1] - end[1]) if alt else start
    else:
        start = (start[0] + dx, start[1] + dy)
        end = (2 * mid[0] - start[0], 2 * mid[1] - start[1]) if alt else end
    length = max(MIN, math.hypot(end[0] - start[0], end[1] - start[1]))
    rot = math.degrees(math.atan2(end[1] - start[1], end[0] - start[0])) if length > MIN else g["rot"]
    if shift:
        rot = round(rot / 15) * 15
    ux, uy = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    if alt:
        centre = mid
    elif hx > 0:
        centre = (start[0] + ux * length / 2, start[1] + uy * length / 2)
    else:
        centre = (end[0] - ux * length / 2, end[1] - uy * length / 2)
    ox, oy = turn((g["ax"] - 0.5) * length, (g["ay"] - 0.5) * g["h"], rot)
    return {"x": centre[0] + ox, "y": centre[1] + oy, "w": length, "rot": rot}
