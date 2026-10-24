"""Edit mesh's maths (SPEC §4.3): an editable mesh (`shape: "poly"`) seen through the viewport's View: which point, edge
or face is under the pointer, which are inside a dragged box, the overlay to draw (the mesh's edges, the selection),
the selection as the selector text the operations read ("faces 3 4", rostrum3d.mesh_select).
No Qt; mesh_edit_qt.py puts it on screen. Points are in the item's own space; `world` is its world transform.
"""
from __future__ import annotations

import math

from rostrum3d import aim, mesh_select

from . import mesh_look
from .viewcam import _cross, _norm, _sub

NEAR = 8.0                   # how near (screen px) the pointer must be to a point or an edge
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
        self._soft, self._seen = None, {}

    @property
    def soft(self) -> set:
        """Edges drawn faint (mesh_look.soft_edges): both sides part of one curved run."""
        if self._soft is None:
            self._soft = mesh_look.soft_edges(self.pts, self.faces, self.edges)
        return self._soft

    def seen(self, kind) -> list:
        """For every element of `kind`: is it visible from the camera (not behind the mesh)? Worked out once per Geo."""
        if kind not in self._seen:
            idx = lambda i: [i] if kind == "points" else list(self.edges[i]) if kind == "edges" else self.faces[i]   # noqa: E731
            spots = [[sum(self.pts[k][c] for k in idx(i)) / len(idx(i)) for c in range(3)] for i in range(self.count(kind))]
            self._seen[kind] = mesh_look.visible(self.view.eye, spots, mesh_look.triangles(self.pts, self.faces))
        return self._seen[kind]

    def anchor(self, kind, i):
        """The picture point that stands for element i: a point, an edge's middle, a face's centre."""
        idx = [i] if kind == "points" else list(self.edges[i]) if kind == "edges" else self.faces[i]
        ps = [self.scr[k] for k in idx]
        if any(p is None for p in ps):
            return None
        return [sum(p[0] for p in ps) / len(ps), sum(p[1] for p in ps) / len(ps)]

    def places(self, kind, sel) -> set:
        """Where the elements `sel` are (their points, own space, to 0.1 µm): what a selection is when numbers change."""
        idx = lambda i: [i] if kind == "points" else list(self.edges[i]) if kind == "edges" else self.faces[i]  # noqa: E731
        return {self._place(idx(i)) for i in sel if i < self.count(kind)}

    def at_places(self, kind, places) -> set:
        idx = lambda i: [i] if kind == "points" else list(self.edges[i]) if kind == "edges" else self.faces[i]  # noqa: E731
        return {i for i in range(self.count(kind)) if self._place(idx(i)) in places}

    def _place(self, ids):
        return tuple(sorted(tuple(round(c * 1e7) for c in self.item["points"][k]) for k in ids))

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


def pick(geo, kind, x, y, px=1.0, xray=False):
    """The element of `kind` under picture point (x, y), or None. Points and edges: the nearest within NEAR screen px
    that is visible (mesh_look; any with X-ray); faces: the nearest face the ray goes through."""
    if kind == "faces":
        return face_hit(geo, x, y)[0]
    seen, best = geo.seen(kind), None
    for i in range(geo.count(kind)):
        if not (xray or seen[i]):
            continue
        idx = [i] if kind == "points" else list(geo.edges[i])
        ps = [geo.scr[k] for k in idx]
        if any(p is None for p in ps):
            continue
        d = math.hypot(x - ps[0][0], y - ps[0][1]) if kind == "points" else _seg([x, y], ps[0], ps[1])
        if d <= NEAR * px and (best is None or d < best[0]):
            best = (d, i)
    return best[1] if best else None


def boxed(geo, kind, rect, xray=False):
    """Every element of `kind` whose anchor (point, edge middle, face centre) is inside rect (x0, y0, x1, y1) and
    visible (mesh_look), or any with X-ray."""
    x0, x1 = sorted(rect[0::2])
    y0, y1 = sorted(rect[1::2])
    out, seen = set(), (None if xray else geo.seen(kind))
    for i in range(geo.count(kind)):
        p = geo.anchor(kind, i)
        if seen is not None and not seen[i]:
            continue
        if p and x0 <= p[0] <= x1 and y0 <= p[1] <= y1:
            out.add(i)
    return out


def overlay(geo, kind, sel) -> dict:
    """What to draw, in picture px: the edges (`lines` full, `faint` the soft ones inside a curved run), and the
    selection: points, edges, or faces (tinted polygons)."""
    def xy(k):
        return geo.scr[k][:2] if geo.scr[k] else None
    segs = [(i, [xy(a), xy(b)]) for i, (a, b) in enumerate(geo.edges) if xy(a) and xy(b)]
    out = {"lines": [s for i, s in segs if i not in geo.soft], "faint": [s for i, s in segs if i in geo.soft],
           "points": [], "edges": [], "faces": []}
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


def label(kind, n) -> str:
    return f"{n} {WORD[kind][0 if n == 1 else 1]}" if n else f"No {WORD[kind][1]} picked"
