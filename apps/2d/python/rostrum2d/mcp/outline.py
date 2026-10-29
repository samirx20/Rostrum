"""Where a hollow layer paints: a ring, an outlined box or a path drawn only by its stroke covers just the band along its
outline, not its box. A rectangle or ellipse shape and a path are measured (the others, a star or an arrow, count as
their box, as before). `points` is the outline's centre line in picture px, for checks that ask whether a line runs
through something (review_layout: a ring crossing a title); `near` is the band test geometry.covers uses."""
from __future__ import annotations

import math

from rostrum2d import pathdata

STEP = 4.0          # own px between outline samples
SLOP = 1.0          # own px: a point this close to the band's edge is on it


def hollow(n: dict) -> bool:
    """A shape (rectangle, ellipse) or path drawn by its outline alone: no fill (or a clear one), a stroke on."""
    p = n["props"]
    if n["type"] not in ("shape", "path") or n["type"] == "shape" and p.get("shape", "rect") not in ("rect", "ellipse"):
        return False
    unfilled = not p.get("filled", True) or p.get("fillOpacity", 1.0) <= 0.01 or p.get("fill") in ("none", "transparent")
    return unfilled and bool(p.get("stroke")) and p.get("strokeWidth", 0) > 0


def _own(n: dict) -> list[tuple[float, float]]:
    """The outline's centre line in the layer's own px (STEP apart), the drawn part of a trimmed path only."""
    if "_outline" in n:
        return n["_outline"]
    w, h = n["size"]
    p = n["props"]
    if n["type"] == "shape" and p.get("shape") == "ellipse":
        k = max(16, int(math.pi * (w + h) / 2 / STEP))
        pts = [(w / 2 + w / 2 * math.cos(2 * math.pi * i / k), h / 2 + h / 2 * math.sin(2 * math.pi * i / k)) for i in range(k + 1)]
    elif n["type"] == "shape":
        pts = _line([(0, 0), (w, 0), (w, h), (0, h), (0, 0)])
    else:
        pts = _path(p.get("d", ""))
        a, b = p.get("trimStart", 0.0), p.get("trimEnd", 1.0)
        if (a, b) != (0.0, 1.0) and pts:
            pts = pts[int(len(pts) * min(a, b)):int(math.ceil(len(pts) * max(a, b)))]
    n["_outline"] = pts
    return pts


def _line(corners) -> list[tuple[float, float]]:
    out = []
    for (x0, y0), (x1, y1) in zip(corners, corners[1:]):
        k = max(1, int(math.hypot(x1 - x0, y1 - y0) / STEP))
        out += [(x0 + (x1 - x0) * i / k, y0 + (y1 - y0) * i / k) for i in range(k)]
    return out + [corners[-1]]


def _path(d: str) -> list[tuple[float, float]]:
    out, cur, start = [], (0.0, 0.0), (0.0, 0.0)
    for c in pathdata.commands(d):
        if c[0] == "M":
            cur = start = (c[1], c[2])
            out.append(cur)
        elif c[0] == "L":
            out += _line([cur, (c[1], c[2])])[1:]
            cur = (c[1], c[2])
        elif c[0] == "C":
            q = (cur, (c[1], c[2]), (c[3], c[4]), (c[5], c[6]))
            k = max(4, int(sum(math.dist(q[i], q[i + 1]) for i in range(3)) / STEP))
            out += [tuple(pathdata._cubic([v[axis] for v in q], i / k) for axis in (0, 1)) for i in range(1, k + 1)]
            cur = (c[5], c[6])
        elif c[0] == "Z":
            out += _line([cur, start])[1:]
            cur = start
    return out


def near(n: dict, lx: float, ly: float) -> bool:
    """(lx, ly), in the layer's own px, is on its stroke band."""
    r = n["props"].get("strokeWidth", 0) / 2 + SLOP + STEP / 2
    return any(abs(x - lx) <= r and abs(y - ly) <= r and (x - lx) ** 2 + (y - ly) ** 2 <= r * r for x, y in _own(n))


def points(n: dict) -> list[tuple[float, float]]:
    """The outline's centre line in picture px."""
    a, b, c, d, e, f = n["matrix"]
    return [(a * x + c * y + e, b * x + d * y + f) for x, y in _own(n)]


def width(n: dict) -> float:
    """The stroke's width in picture px (the layer's scale applied)."""
    a, b, c, d, _, _ = n["matrix"]
    return n["props"].get("strokeWidth", 0) * math.sqrt(abs(a * d - b * c))
