"""Where things are, and aiming. A transform is USD's `translate`, `rotateXYZ`, `scale` in that order: a point is
scaled, then turned about X, then Y, then Z (degrees), then moved; children sit in their parent's space. An aimed
item gets the rx ry rz that point its −Z (where cameras and rect/disk lights look) at the target with its Y as
close to up as it goes, then turned by its `roll` around the way it points (roll 90 stands a strip on end).

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


def det(m) -> float:
    (a, b, c), (d, e, f), (g, h, i) = m
    return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)


def invert(m):
    """The inverse of a transform (L, t)."""
    li = _inverse(m[0])
    return li, [-x for x in _apply(li, m[1])]


def _inverse(m):
    (a, b, c), (d, e, f), (g, h, i) = m
    det_ = det(m)
    if abs(det_) < 1e-12:
        raise ValueError("a parent is scaled to zero, so nothing inside it can aim, follow or stick")
    return [[(e * i - f * h) / det_, (c * h - b * i) / det_, (b * f - c * e) / det_],
            [(f * g - d * i) / det_, (a * i - c * g) / det_, (c * d - a * f) / det_],
            [(d * h - e * g) / det_, (b * g - a * h) / det_, (a * e - b * d) / det_]]


def aim_rotation(parent, own_pos: list[float], target_world: list[float], roll: float = 0.0) -> tuple[float, float, float]:
    """rx ry rz (degrees) for an item at `own_pos` (parent space) whose −Z should point at `target_world`, turned by
    `roll` degrees around that direction (counter-clockwise as seen from behind the item, looking where it points)."""
    origin = point(parent, own_pos)
    d = _apply(_inverse(parent[0]), [t - o for t, o in zip(target_world, origin)])
    dx, dy, dz = d
    if math.hypot(dx, dy, dz) < 1e-12:
        raise ValueError("it is at the very point it aims at")
    rx = math.degrees(math.atan2(dy, math.hypot(dx, dz)))
    ry = math.degrees(math.atan2(-dx, -dz)) if math.hypot(dx, dz) > 1e-12 else 0.0
    return (rx, ry, 0.0) if not roll else euler(_mul(_rot(1, ry), _mul(_rot(0, rx), _rot(2, roll))))


def euler(m) -> tuple[float, float, float]:
    """A rotation matrix as rx ry rz in the transform's order (X first, then Y, then Z)."""
    ry = math.asin(max(-1.0, min(1.0, -m[2][0])))
    if abs(m[2][0]) < 1 - 1e-9:
        rx, rz = math.atan2(m[2][1], m[2][2]), math.atan2(m[1][0], m[0][0])
    else:                                                 # pointing straight up or down: put it all in rx
        rx, rz = math.atan2(-m[1][2], m[1][1]), 0.0
    return math.degrees(rx), math.degrees(ry), math.degrees(rz)


def ahead(world, p) -> float:
    """How far in front of an item (along its −Z, the way a camera looks and a lens measures focus) the world point
    `p` is; negative behind it."""
    eye, front = point(world, [0.0, 0.0, 0.0]), point(world, [0.0, 0.0, -1.0])
    forward = [a - e for a, e in zip(front, eye)]
    n = sum(x * x for x in forward) ** 0.5 or 1.0
    return sum((q - e) * f for q, e, f in zip(p, eye, forward)) / n
