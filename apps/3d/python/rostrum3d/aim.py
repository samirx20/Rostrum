"""Where things are, and aiming. A transform is USD's `translate`, `rotateXYZ`, `scale` in that order: a point is
scaled, then turned about X, then Y, then Z (degrees), then moved; children sit in their parent's space. An aimed
item gets the rx ry rz that point its −Z (where cameras and rect/disk lights look) at the target with its Y as
close to up as it goes (no roll: rz = 0).

Affine transforms are (L, t): L a 3×3 row-major list, t a 3-list. Plain Python, no numpy.
"""
from __future__ import annotations

import math

IDENTITY = ([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], [0.0, 0.0, 0.0])


def _mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _apply(m, v):
    return [sum(m[i][k] * v[k] for k in range(3)) for i in range(3)]


def _rot(axis: int, deg: float):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    i, j = [(1, 2), (2, 0), (0, 1)][axis]
    m = [[1.0 if r == q else 0.0 for q in range(3)] for r in range(3)]
    m[i][i], m[i][j], m[j][i], m[j][j] = c, -s, s, c
    return m


def local(v: dict):
    """The item's own transform (in its parent's space) from x y z rx ry rz sx sy sz."""
    r = _mul(_rot(2, v["rz"]), _mul(_rot(1, v["ry"]), _rot(0, v["rx"])))
    s = [[v["sx"], 0, 0], [0, v["sy"], 0], [0, 0, v["sz"]]]
    return _mul(r, s), [v["x"], v["y"], v["z"]]


def compose(parent, child):
    """The child's transform in world space."""
    (pl, pt), (cl, ct) = parent, child
    return _mul(pl, cl), [a + b for a, b in zip(_apply(pl, ct), pt)]


def point(m, p) -> list[float]:
    return [a + b for a, b in zip(_apply(m[0], p), m[1])]


def _inverse(m):
    (a, b, c), (d, e, f), (g, h, i) = m
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if abs(det) < 1e-12:
        raise ValueError("a parent is scaled to zero, so nothing inside it can aim")
    return [[(e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det],
            [(f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det],
            [(d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det]]


def aim_rotation(parent, own_pos: list[float], target_world: list[float]) -> tuple[float, float, float]:
    """rx ry rz (degrees) for an item at `own_pos` (parent space) whose −Z should point at `target_world`."""
    origin = point(parent, own_pos)
    d = _apply(_inverse(parent[0]), [t - o for t, o in zip(target_world, origin)])
    dx, dy, dz = d
    if math.hypot(dx, dy, dz) < 1e-12:
        raise ValueError("it is at the very point it aims at")
    rx = math.degrees(math.atan2(dy, math.hypot(dx, dz)))
    ry = math.degrees(math.atan2(-dx, -dz)) if math.hypot(dx, dz) > 1e-12 else 0.0
    return rx, ry, 0.0
