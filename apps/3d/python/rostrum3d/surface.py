"""A mesh's surface as triangles in its own space, and the top of a set of triangles straight above a point: what
Stick to surface stands things on (follow.py). The shapes are the core's (core/src/primitives.cpp: every shape
centred on its origin, a plane and a disc flat at y = 0 facing up), at a fixed fineness: a stuck item rests within
a millimetre or so of the drawn surface; an editable mesh uses its own faces exactly.
"""
from __future__ import annotations

import math

ROUND = 32                                                   # steps around a round shape
SHAPES = ("plane", "disc", "box", "sphere", "cylinder", "cone", "capsule", "poly")


def _turned(rows: list[tuple[float, float]]) -> list[list[list[float]]]:
    """Triangles of the surface made by turning a profile (radius, y) rows around Y."""
    tris = []
    for (r0, y0), (r1, y1) in zip(rows, rows[1:]):
        for i in range(ROUND):
            a, b = (2 * math.pi * i / ROUND, 2 * math.pi * (i + 1) / ROUND)
            p = [[r0 * math.cos(a), y0, r0 * math.sin(a)], [r0 * math.cos(b), y0, r0 * math.sin(b)],
                 [r1 * math.cos(b), y1, r1 * math.sin(b)], [r1 * math.cos(a), y1, r1 * math.sin(a)]]
            tris += [[p[0], p[1], p[2]], [p[0], p[2], p[3]]]
    return tris


def _arc(r: float, mid: float, up: bool) -> list[tuple[float, float]]:
    """A quarter circle of radius r from the side (y = ±mid) to the pole, as profile rows."""
    rows = [(r * math.cos(t), mid + r * math.sin(t)) for t in (math.pi / 2 * k / (ROUND // 4) for k in range(ROUND // 4 + 1))]
    return rows if up else [(x, -y) for x, y in reversed(rows)]


def triangles(v: dict) -> list[list[list[float]]]:
    """The surface of a mesh with values `v` (its fields), in its own space. Raises ValueError for a shape that has
    no surface here (a torus, text, svg, path2d)."""
    s = v["shape"]
    if s == "poly":
        pts, out, i = v.get("points") or [], [], 0
        for n in v.get("faceCounts", []):
            f = v["faceIndices"][i:i + n]
            out += [[pts[f[0]], pts[f[k]], pts[f[k + 1]]] for k in range(1, n - 1)]
            i += n
        return out
    if s in ("plane", "box"):
        w, d = v["width"] / 2, v["depth"] / 2
        ys = (0.0,) if s == "plane" else (-v["height"] / 2, v["height"] / 2)
        c = [[x, y, z] for y in ys for x, z in ((-w, -d), (w, -d), (w, d), (-w, d))]
        faces = [(0, 1, 2, 3)] if s == "plane" else [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5),
                                                     (2, 3, 7, 6), (3, 0, 4, 7)]
        return [[c[f[0]], c[f[k]], c[f[k + 1]]] for f in faces for k in (1, 2)]
    r, h = v.get("radius", 0.5), v.get("height", 1.0) / 2
    rows = {"disc": [(0.0, 0.0), (r, 0.0)],
            "cylinder": [(0.0, -h), (r, -h), (r, h), (0.0, h)],
            "cone": [(0.0, -h), (r, -h), (0.0, h)],
            "sphere": _arc(r, 0.0, False) + _arc(r, 0.0, True)[1:],
            "capsule": _arc(r, max(0.0, h - r), False) + _arc(r, max(0.0, h - r), True)}.get(s)
    if rows is None:
        raise ValueError(f'a {s} has no surface to stick to (stick to a {", ".join(SHAPES[:-1])} or editable mesh)')
    return _turned(rows)


def top(tris: list[list[list[float]]], x: float, z: float) -> float | None:
    """The highest y of the triangles (world space) straight above or below the point (x, z); None off their edge."""
    best = None
    for a, b, c in tris:
        d = (b[0] - a[0]) * (c[2] - a[2]) - (c[0] - a[0]) * (b[2] - a[2])
        if abs(d) < 1e-14:
            continue                                          # seen edge-on from above
        u = ((x - a[0]) * (c[2] - a[2]) - (c[0] - a[0]) * (z - a[2])) / d
        w = ((b[0] - a[0]) * (z - a[2]) - (x - a[0]) * (b[2] - a[2])) / d
        if u >= -1e-9 and w >= -1e-9 and u + w <= 1 + 1e-9:
            y = a[1] + u * (b[1] - a[1]) + w * (c[1] - a[1])
            best = y if best is None else max(best, y)
    return best
