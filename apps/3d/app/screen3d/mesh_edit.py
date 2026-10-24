"""Edit mesh's maths (SPEC §4.3): an editable mesh (`shape: "poly"`) seen through the viewport's View: which point, edge
or face is under the pointer, which are inside a dragged box, the overlay to draw (the mesh's edges, the selection),
the selection as the selector text the operations read ("faces 3 4", rostrum3d.mesh_select), and the extrude arrow.
No Qt; mesh_edit_qt.py puts it on screen. Points are in the item's own space; `world` is its world transform.
"""
from __future__ import annotations

import math

from rostrum3d import aim, mesh_select

from .viewcam import _cross, _norm, _sub

NEAR = 8.0                   # how near (screen px) the pointer must be to a point or an edge
ARROW = 70.0                 # the extrude arrow's length, screen px
KINDS = ("points", "edges", "faces")
WORD = {"points": ("point", "points"), "edges": ("edge", "edges"), "faces": ("face", "faces")}


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


class Geo:
    """The poly item in the world: its points, faces and edges, and where each projects on the picture."""

    def __init__(self, item, world, view):
        self.item, self.world, self.view = item, world, view
        self.pts = [aim.point(world, p) for p in item["points"]]
        self.faces = mesh_select.faces_of(item)
        self.edges = mesh_select.edges_of(item)
        self.scr = [view.project(p) for p in self.pts]

    def anchor(self, kind, i):
        """The picture point that stands for element i: a point, an edge's middle, a face's centre."""
        idx = [i] if kind == "points" else list(self.edges[i]) if kind == "edges" else self.faces[i]
        ps = [self.scr[k] for k in idx]
        if any(p is None for p in ps):
            return None
        return [sum(p[0] for p in ps) / len(ps), sum(p[1] for p in ps) / len(ps)]

    def count(self, kind) -> int:
        return len(self.pts) if kind == "points" else len(self.edges) if kind == "edges" else len(self.faces)


def _seg(p, a, b):
    ab, ap = [b[0] - a[0], b[1] - a[1]], [p[0] - a[0], p[1] - a[1]]
    t = max(0.0, min(1.0, (ap[0] * ab[0] + ap[1] * ab[1]) / ((ab[0] ** 2 + ab[1] ** 2) or 1e-9)))
    return math.hypot(p[0] - a[0] - ab[0] * t, p[1] - a[1] - ab[1] * t)


def _ray_tri(o, d, a, b, c):
    """Distance along the ray o + t·d to triangle abc, or None (Möller–Trumbore, both sides)."""
    e1, e2 = _sub(b, a), _sub(c, a)
    h = _cross(d, e2)
    det = _dot(e1, h)
    if abs(det) < 1e-12:
        return None
    s = _sub(o, a)
    u = _dot(s, h) / det
    q = _cross(s, e1)
    v = _dot(d, q) / det
    if u < 0 or v < 0 or u + v > 1:
        return None
    t = _dot(e2, q) / det
    return t if t > 1e-9 else None


def face_hit(geo, x, y):
    """(face, depth) of the nearest face the pointer's ray goes through, or (None, None)."""
    v, best = geo.view, (None, None)
    d = v.ray(x, y)
    for f, idx in enumerate(geo.faces):
        a = geo.pts[idx[0]]
        for k in range(1, len(idx) - 1):
            t = _ray_tri(v.eye, d, a, geo.pts[idx[k]], geo.pts[idx[k + 1]])
            if t is not None and (best[1] is None or t < best[1]):
                best = (f, t)
    return best


def pick(geo, kind, x, y, px=1.0):
    """The element of `kind` under picture point (x, y), or None. Points and edges: the nearest within NEAR screen px
    that isn't hidden behind a face nearer the camera; faces: the ray hit."""
    face, depth = face_hit(geo, x, y)
    if kind == "faces":
        return face
    best = None
    for i in range(geo.count(kind)):
        idx = [i] if kind == "points" else list(geo.edges[i])
        ps = [geo.scr[k] for k in idx]
        if any(p is None for p in ps):
            continue
        d = math.hypot(x - ps[0][0], y - ps[0][1]) if kind == "points" else _seg([x, y], ps[0], ps[1])
        z = min(p[2] for p in ps)
        if d <= NEAR * px and (depth is None or z <= depth * 1.02 + 1e-4) and (best is None or d < best[0]):
            best = (d, i)
    return best[1] if best else None


def boxed(geo, kind, rect):
    """Every element of `kind` whose anchor (point, edge middle, face centre) is inside rect (x0, y0, x1, y1)."""
    x0, x1 = sorted(rect[0::2])
    y0, y1 = sorted(rect[1::2])
    out = set()
    for i in range(geo.count(kind)):
        p = geo.anchor(kind, i)
        if p and x0 <= p[0] <= x1 and y0 <= p[1] <= y1:
            out.add(i)
    return out


def overlay(geo, kind, sel) -> dict:
    """What to draw, in picture px: every edge (thin), and the selection: points, edges, or faces (tinted polygons)."""
    def xy(k):
        return geo.scr[k][:2] if geo.scr[k] else None
    lines = [[xy(a), xy(b)] for a, b in geo.edges if xy(a) and xy(b)]
    out = {"lines": lines, "points": [], "edges": [], "faces": []}
    if kind == "points":
        out["points"] = [xy(i) for i in sorted(sel) if i < len(geo.pts) and xy(i)]
        out["dots"] = [xy(i) for i in range(len(geo.pts)) if xy(i) and i not in sel]
    elif kind == "edges":
        out["edges"] = [[xy(a), xy(b)] for i, (a, b) in enumerate(geo.edges) if i in sel and xy(a) and xy(b)]
    else:
        out["faces"] = [[xy(k) for k in geo.faces[f]] for f in sorted(sel) if f < len(geo.faces)
                        and all(xy(k) for k in geo.faces[f])]
    return out


def selector(kind, sel) -> str:
    """The selection as the operations' selector text: "faces 3 4", "points 0 1", "edges 0-1 1-5" (pairs for edges)."""
    return mesh_select.text(kind, sel)


def as_items(geo, kind, sel):
    """The selection in the selector's own terms: edges as (a, b) pairs, the rest as indices."""
    return {geo.edges[i] for i in sel} if kind == "edges" else set(sel)


def centre(geo, kind, sel):
    """The selection's centre in the world."""
    idx = sorted({k for i in sel for k in ([i] if kind == "points" else geo.edges[i] if kind == "edges" else geo.faces[i])})
    ps = [geo.pts[k] for k in idx] or geo.pts
    return [sum(p[c] for p in ps) / len(ps) for c in range(3)]


def normal(geo, sel):
    """The selected faces' average outward normal in the world (unit), from their own corners (CCW from outside)."""
    n = [0.0, 0.0, 0.0]
    for f in sel:
        idx = geo.faces[f]
        a = geo.pts[idx[0]]
        for k in range(1, len(idx) - 1):
            c = _cross(_sub(geo.pts[idx[k]], a), _sub(geo.pts[idx[k + 1]], a))
            n = [n[i] + c[i] for i in range(3)]
    return _norm(n) if _dot(n, n) > 1e-18 else [0.0, 1.0, 0.0]


def arrow(geo, sel, px=1.0, distance=0.0):
    """The extrude arrow in picture px: (base, tip, world units per screen px along it), from the selection's centre
    along its normal; `distance` (m) moves its base with the drag."""
    c, n = centre(geo, "faces", sel), normal(geo, sel)
    base = [c[i] + n[i] * distance for i in range(3)]
    b = geo.view.project(base)
    if b is None:
        return None
    units = geo.view.units(b[2]) * px
    tip = geo.view.project([base[i] + n[i] * units * ARROW for i in range(3)])
    return (b[:2], tip[:2], units) if tip else None


def along(base, tip, units, start, now) -> float:
    """Metres the pointer moved along the arrow from `start` to `now` (picture px)."""
    ax, ay = tip[0] - base[0], tip[1] - base[1]
    n = math.hypot(ax, ay) or 1e-9
    return ((now[0] - start[0]) * ax + (now[1] - start[1]) * ay) / n * (ARROW * units / n)


def label(kind, n) -> str:
    return f"{n} {WORD[kind][0 if n == 1 else 1]}" if n else f"No {WORD[kind][1]} picked"
