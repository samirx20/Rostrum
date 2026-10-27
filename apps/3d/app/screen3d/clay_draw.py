"""The Clay tool's Draw and Spin sums (clay_draw_qt.py), no Qt (3d-simplicity SPEC § 3.1, CL3 CONTRACT § 5): which plane
an outline drawn on the picture lies on, and the outline's pixels as points on it.

The plane rule: the press's pick landed on a clay → the plane through that point, facing the view (its normal the view
direction, reversed), and the outline joins that clay. Anywhere else → a vertical plane standing on the ground point
under the outline's lowest pixel, facing the view flattened to horizontal (the shape stands on the ground, its front to
the camera). Each pixel's ray meets that plane; a pixel whose ray misses it (parallel, or behind the camera) is left out.
Points are world metres; the caller moves them into the clay's own space for a join (clay_ring.to_clay).
"""
from __future__ import annotations

import math

from .placing import ground_hit

FLAT = 0.2                  # a view looking down more steeply than this (the flattened view's length) can't stand a plane


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _norm(v):
    n = math.sqrt(_dot(v, v)) or 1.0
    return [c / n for c in v]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def on_plane(view, x, y, origin, normal):
    """Where the view's ray through picture px (x, y) meets the plane (origin, normal); None when it misses."""
    d = view.ray(x, y)
    den = _dot(d, normal)
    if abs(den) < 1e-9:
        return None
    t = _dot([o - e for o, e in zip(origin, view.eye)], normal) / den
    return None if t <= 1e-6 else [e + c * t for e, c in zip(view.eye, d)]


def ground_plane(view, pts):
    """(origin, normal) of the vertical plane on the ground under the lowest of `pts` (picture px), facing the view
    flattened; None when that pixel looks above the horizon or the view looks (nearly) straight down."""
    if not pts:
        return None
    low = max(pts, key=lambda p: p[1])
    hit = ground_hit(view, low[0], low[1])
    flat = [-view.fwd[0], 0.0, -view.fwd[2]]
    if hit is None or math.hypot(flat[0], flat[2]) < FLAT:
        return None
    return hit[0], _norm(flat)


def plane_for(view, start: dict | None, pts, is_clay) -> tuple[list, list, str] | None:
    """(origin, normal, the clay to join or "") for an outline of `pts` (picture px) whose press picked `start` (the
    engine's pick answer); `is_clay(id)` says whether an item is a clay. None: no plane (above the horizon, or looking
    straight down)."""
    if start and start.get("hit") and is_clay(start.get("item", "")):
        return list(start["point"]), [-c for c in view.fwd], start["item"]
    g = ground_plane(view, pts)
    return (g[0], g[1], "") if g is not None else None


def lift(view, pts, origin, normal) -> list[list[float]]:
    """`pts` (picture px) as world points on the plane, to a tenth of a millimetre; the ones that miss it left out."""
    out = []
    for x, y in pts:
        p = on_plane(view, x, y, origin, normal)
        if p is not None:
            out.append([round(c, 4) for c in p])
    return out


def axes(normal) -> tuple[list[float], list[float]]:
    """The plane's (u, v): u its most horizontal direction, v up along it (as clay.draw stores it)."""
    u = _cross([0.0, 1.0, 0.0], normal)
    if _dot(u, u) < 1e-9:                                   # a level plane: u along x
        u = [1.0, 0.0, 0.0]
    u = _norm(u)
    return u, _cross(normal, u)


def _length(m: float) -> str:
    if m >= 1:
        return f"{m:.2f} m"
    return f"{m * 1000:.0f} mm" if m < 0.01 else f"{m * 100:.0f} cm"


def size_text(points, normal) -> str:
    """The outline's width × height on its plane ("18 × 30 cm"; "" under 3 points)."""
    if len(points) < 2:
        return ""
    u, v = axes(normal)
    us, vs = [_dot(p, u) for p in points], [_dot(p, v) for p in points]
    w, h = max(us) - min(us), max(vs) - min(vs)
    a, b = _length(w), _length(h)
    unit = a.split(" ")[1]
    return f"{a.split(' ')[0]} × {b}" if b.endswith(" " + unit) else f"{a} × {b}"


def direction_into(to_space, p, d) -> list[float]:
    """Direction `d` at world point `p` in another space, given its point map `to_space` (unit length)."""
    a, b = to_space(p), to_space([p[k] + d[k] for k in range(3)])
    return [round(c, 6) for c in _norm([y - x for x, y in zip(a, b)])]


def axis_line(view, point, px: float = 1.0) -> list[list[float]]:
    """The Spin axis shown at the pointer: the vertical through world `point`, as [x, y] parts of the picture, from
    40 screen px under it to 140 over it ([] when it is behind the camera). `px`: picture px per screen px."""
    o = view.project(point)
    if o is None:
        return []
    k = view.units(o[2]) * px
    out = []
    for h in (-40 * k, 140 * k):
        q = view.project([point[0], point[1] + h, point[2]])
        if q is None:
            return []
        out.append([q[0] / view.w, q[1] / view.h])
    return out
