"""The geometry of selecting and moving strokes, in composition px. No Qt, no document: points in, points out.

A lasso is a closed polygon of composition px; a stroke is picked when more than half of its points lie inside. A move
or a transform (scale, turn) is done on a stroke's points in composition px and then put back on its canvas: the screen
(stroke_select.py) changes each point with the layer's own mapping (rostrum2d/placement.py), so a stroke keeps its look.
"""
from __future__ import annotations

import math


def inside(poly: list, x: float, y: float) -> bool:
    """Even-odd test: is (x, y) inside the closed polygon [[x, y], …]."""
    hit, n, j = False, len(poly), len(poly) - 1
    for i in range(n):
        (xi, yi), (xj, yj) = poly[i][:2], poly[j][:2]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            hit = not hit
        j = i
    return hit


def picked(poly: list, points: list) -> bool:
    """A stroke (its points in composition px) is inside the lasso when more than half of its points are."""
    return len(poly) >= 3 and bool(points) and 2 * sum(inside(poly, p[0], p[1]) for p in points) > len(points)


def bounds(groups: list[list]) -> tuple[float, float, float, float] | None:
    """(x0, y0, x1, y1) of all the points of all the strokes, or None."""
    pts = [p for g in groups for p in g]
    if not pts:
        return None
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def moved(points: list, dx: float, dy: float) -> list:
    return [[p[0] + dx, p[1] + dy, *p[2:]] for p in points]


def transformed(points: list, around: tuple[float, float], scale: float = 1.0, turn: float = 0.0) -> list:
    """The points scaled by `scale` and turned by `turn` degrees (clockwise on screen) about `around`."""
    ax, ay = around
    c, s = math.cos(math.radians(turn)), math.sin(math.radians(turn))
    out = []
    for p in points:
        x, y = (p[0] - ax) * scale, (p[1] - ay) * scale
        out.append([ax + x * c - y * s, ay + x * s + y * c, *p[2:]])
    return out


def outline(points: list) -> str:
    """A stroke's path as SVG path data (composition px), for the selection's outline."""
    return "M " + " L ".join(f"{p[0]:.1f} {p[1]:.1f}" for p in points) if points else ""
