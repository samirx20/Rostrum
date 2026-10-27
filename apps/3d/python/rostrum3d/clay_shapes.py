"""The geometry behind a drawn or spun clay piece (CL3 CONTRACT § 1, § 4), plain Python: points given in 3-D become a
plane (`plane` = origin, u, v: nine numbers) and 2-D points in it, the same way for the screen, operations and scripts.

- Draw: the points are fitted to a plane (`facing` is its normal when given, else the outline's own: Newell's
  normal); u is the plane's most horizontal direction (the view's left-right for a plane facing the view), v = n × u.
- Spin: v is the axis (vertical, through the first point, when not given), u points to the profile's side; each point
  is kept as (distance from the axis, height along it).
- A new clay made from a drawing stands at the outline's middle (horizontally centred, at its lowest point's height),
  turned about Y so its X is the plane's u: Mirror's X = 0 runs down the middle of what was drawn.
"""
from __future__ import annotations

import hashlib
import json
import math

Y, X = (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)
GRID = 32                      # cells per side when measuring an outline's inner radius
SAMPLE = 64                    # outline points kept for that measure


def sub(a, b): return [a[i] - b[i] for i in range(3)]
def add(a, b): return [a[i] + b[i] for i in range(3)]
def mul(a, k): return [a[i] * k for i in range(3)]
def dot(a, b): return sum(a[i] * b[i] for i in range(3))
def cross(a, b): return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def unit(a):
    n = math.sqrt(dot(a, a))
    return [v / n for v in a] if n > 1e-12 else None


def r6(xs):
    return [round(float(v), 6) + 0.0 for v in xs]


def mean(points):
    return [sum(p[i] for p in points) / len(points) for i in range(3)]


def _axes(n):
    """u (the plane's most horizontal direction) and v = n × u for a unit normal n."""
    u = unit(cross(Y, n)) or unit(sub(X, mul(n, dot(X, n))))
    return u, cross(n, u)


def fit_plane(points, facing=None):
    """(origin, u, v) of the plane through the points' middle; None when they don't span a plane (a line, a dot)."""
    if facing is not None:
        n = unit(facing)
    else:
        nx = ny = nz = 0.0
        for a, b in zip(points, points[1:] + points[:1]):          # Newell: the closed outline's area normal
            nx += (a[1] - b[1]) * (a[2] + b[2])
            ny += (a[2] - b[2]) * (a[0] + b[0])
            nz += (a[0] - b[0]) * (a[1] + b[1])
        n = unit([nx, ny, nz])
        if n is not None and next((c for c in (n[2], n[0], n[1]) if abs(c) > 1e-9), 0) < 0:
            n = mul(n, -1.0)                                          # either winding: the same plane, the same u
    if n is None:
        return None
    u, v = _axes(n)
    return mean(points), u, v


def in_plane(points, o, u, v):
    """3-D points → [u, v] in the plane."""
    return [r6([dot(sub(p, o), u), dot(sub(p, o), v)]) for p in points]


def _seg(px, py, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = ((px - a[0]) * dx + (py - a[1]) * dy) / (dx * dx + dy * dy or 1e-30)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - a[0] - t * dx, py - a[1] - t * dy)


def inside(px, py, poly) -> bool:
    """Even-odd: a crossing outline still has an inside."""
    c = False
    for a, b in zip(poly, poly[1:] + poly[:1]):
        if (a[1] > py) != (b[1] > py) and px < a[0] + (py - a[1]) * (b[0] - a[0]) / (b[1] - a[1]):
            c = not c
    return c


def inner_radius(poly) -> float:
    """The largest circle inside a 2-D outline (its radius), measured on a grid: how fat the drawing is."""
    if len(poly) < 3:
        return 0.0
    pts = poly[:: max(1, len(poly) // SAMPLE)]
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    cell = max(w, h) / GRID
    if cell <= 0:
        return 0.0
    best = 0.0
    for i in range(int(w / cell) + 1):
        for j in range(int(h / cell) + 1):
            x, y = min(xs) + (i + 0.5) * cell, min(ys) + (j + 0.5) * cell
            if inside(x, y, pts):
                best = max(best, min(_seg(x, y, a, b) for a, b in zip(pts, pts[1:] + pts[:1])))
    return best


def spin_frame(points, axis=None):
    """(origin, u, v, profile) of a spun shape: v along the axis (default: up through the first point), u to the
    profile's side, profile [[distance from the axis, height along it], …]."""
    a0 = [float(c) for c in (axis[0] if axis else points[0])]
    v = unit(sub(axis[1], axis[0])) if axis else list(Y)
    if v is None:
        return None
    side, profile = [0.0, 0.0, 0.0], []
    for p in points:
        w = sub(p, a0)
        h = dot(w, v)
        perp = sub(w, mul(v, h))
        side = add(side, perp)
        profile.append(r6([math.sqrt(dot(perp, perp)), h]))
    u = unit(side) or _axes(v)[0]
    u = unit(sub(u, mul(v, dot(u, v))))
    return a0, u, v, profile


def plane9(o, u, v) -> list[float]:
    return r6([*o, *u, *v])


# ---- a new clay standing where it was drawn ------------------------------------------------------------------------
def standing(points, u, centre=None):
    """(origin, turn about Y in degrees) for a new clay made from these scene points: at their horizontal middle
    (`centre`'s x, z when given: a spin's axis) and lowest height, its X along the horizontal part of u."""
    xs, zs = [p[0] for p in points], [p[2] for p in points]
    cx, cz = (centre[0], centre[2]) if centre else ((min(xs) + max(xs)) / 2, (min(zs) + max(zs)) / 2)
    turn = math.degrees(math.atan2(-u[2], u[0])) if abs(u[0]) + abs(u[2]) > 1e-9 else 0.0
    return r6([cx, min(p[1] for p in points), cz]), round(turn, 6) + 0.0


def to_local(p, origin, turn_deg, vector=False):
    """A scene point (or a direction) into a clay at `origin`, turned `turn_deg` about Y (its scale 1)."""
    t = math.radians(turn_deg)
    x, y, z = p if vector else sub(p, origin)
    return [x * math.cos(t) - z * math.sin(t), y, x * math.sin(t) + z * math.cos(t)]


# ---- what Python knows of a shape's size (clay_detail's bounds) ----------------------------------------------------
def balls(step) -> list[tuple[list[float], float]]:
    """(centre, radius) balls round an outline or spin piece, in the clay's own space."""
    plane = step.get("plane") or []
    if len(plane) != 9:
        return []
    o, u, v = plane[:3], plane[3:6], plane[6:]
    if step.get("shape") == "outline":
        pts = step.get("outline") or []                 # thickness: at most half its narrower side, puffed (cheap)
        if not pts:
            return []
        w = min(max(p[i] for p in pts) - min(p[i] for p in pts) for i in (0, 1))
        thick = w / 2 * max(1.0, float(step.get("puff", 1.0)))
        return [(add(o, add(mul(u, a), mul(v, b))), thick) for a, b in pts]
    pts = step.get("profile") or []
    out = []
    for r, h in pts:
        c = add(o, mul(v, h))
        out.append((c, r))
    return out


def source_key(item: dict) -> str:
    """A short hash of an item's own fields (its subtree; its name and Visible left out: hiding it for Turn into clay
    changes nothing), so a clay made from it is rebuilt when it changes."""
    own = {k: x for k, x in item.items() if k not in ("name", "visible")}
    return hashlib.sha256(json.dumps(own, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]
