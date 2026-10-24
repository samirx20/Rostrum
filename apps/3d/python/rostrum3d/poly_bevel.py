"""Bevel: round chosen edges of an editable mesh with rows of faces (SPEC §4.3). Pure geometry on plain lists, like
poly.py; ops_mesh2.py makes it one undo step.

How: every point at the end of a chosen edge is replaced. Each face around it gets a new corner `width` in from the
chosen edges it has (where two chosen edges meet in a face: the inset corner; where one does: a point slid along the
other edge, shared with the face across it). Each chosen edge becomes a band of `segments` rows whose cross-section is
a quarter ellipse from one face's new edge to the other's, bending round the old edge (1 segment: a flat chamfer).
Two chosen edges meeting at a corner with a third, unchosen edge share their end profile (a mitre, like a picture
frame); any hole left at a corner (three chosen edges, or an edge ending at a point) is filled by one corner face.
"""
from __future__ import annotations

import math

from .poly import Change, add, cross, dot, normal, sub, unit

ZERO = [0.0, 0.0, 0.0]


def bevel(points, faces, chosen: set[tuple[int, int]], width: float, segments: int = 1) -> Change:
    half = {(f[i], f[(i + 1) % len(f)]): n for n, f in enumerate(faces) for i in range(len(f))}
    for a, b in sorted(chosen):
        if (a, b) not in half or (b, a) not in half:
            raise ValueError(f"edge {a}-{b} is on the mesh's open border; "
                             "only an edge between two faces can be bevelled")
    ends = {v for e in chosen for v in e}

    def sel(a, b):
        return (min(a, b), max(a, b)) in chosen
    pts, off = [list(p) for p in points], {}            # off: new point -> its offset from its old point, per metre

    def new(v, o):
        off[len(pts)] = o
        pts.append(add(points[v], o, width))
        return len(pts) - 1

    slides: dict[tuple[int, int], list[float]] = {}     # (end, other point) -> slide lengths along that unchosen edge
    for f in faces:
        for i, v in enumerate(f):
            if v in ends:
                p, q = f[i - 1], f[(i + 1) % len(f)]
                for u, o in ((p, q), (q, p)):
                    if not sel(v, u):
                        got = slides.setdefault((v, u), [])
                        if sel(v, o):
                            c = dot(unit(sub(points[u], points[v])), unit(sub(points[o], points[v])))
                            got.append(1.0 / max(1e-6, math.sqrt(max(0.0, 1 - c * c))))
    slide = {(v, u): new(v, [x * (sum(s) / len(s) if s else 1.0) for x in unit(sub(points[u], points[v]))])
             for (v, u), s in slides.items()}

    corner = {}                                         # (face, old point) -> its new corner points, in face order
    for n, f in enumerate(faces):
        nm = normal(points, f)
        for i, v in enumerate(f):
            if v not in ends:
                continue
            p, q = f[i - 1], f[(i + 1) % len(f)]
            if sel(p, v) and sel(v, q):
                in1, in2 = unit(cross(nm, sub(points[v], points[p]))), unit(cross(nm, sub(points[q], points[v])))
                k = 1.0 + dot(in1, in2)
                corner[n, v] = [new(v, [x / k for x in add(in1, in2)] if k > 1e-6 else in1)]
            elif sel(p, v):
                corner[n, v] = [slide[v, q]]
            elif sel(v, q):
                corner[n, v] = [slide[v, p]]
            else:
                corner[n, v] = [slide[v, p], slide[v, q]]

    fit, out = math.inf, []
    for n, f in enumerate(faces):
        out.append([w for v in f for w in corner.get((n, v), [v])])
        for a, b in zip(f, f[1:] + f[:1]):              # each old edge, shortened from both ends, must keep its way
            x, y = corner.get((n, a), [a])[-1], corner.get((n, b), [b])[0]
            d = sub(points[b], points[a])
            k = dot(sub(off.get(y, ZERO), off.get(x, ZERO)), d)
            if k < -1e-12:
                fit = min(fit, dot(d, d) / -k)
    if width >= fit * 0.999:
        raise ValueError(f"width {width:g} m doesn't fit these edges: at most {fit * 0.999:.4g} m fits")

    prof: dict[tuple, list[int]] = {}

    def profile(c, s, e):
        """The points from s to e round old point c (shared by every band that ends there with the same ends)."""
        key = (c, min(s, e), max(s, e))
        if key not in prof:
            lo, hi = key[1], key[2]
            a, b = sub(pts[lo], points[c]), sub(pts[hi], points[c])
            mid = []
            for k in range(1, segments):
                t = k / segments * math.pi / 2
                mid.append(len(pts))
                pts.append(add(add(points[c], a, 1 - math.sin(t)), b, 1 - math.cos(t)))
            prof[key] = [lo, *mid, hi]
        r = prof[key]
        return r if r[0] == s else r[::-1]

    parents, kept = list(range(len(faces))), set()
    for a, b in sorted(chosen):
        fl, fr = half[a, b], half[b, a]
        pa = profile(a, corner[fl, a][0], corner[fr, a][0])
        pb = profile(b, corner[fl, b][0], corner[fr, b][0])
        for k in range(segments):
            kept.add(len(out))
            out.append([pa[k], pa[k + 1], pb[k + 1], pb[k]])
            parents.append(fl if 2 * k < segments else fr)
    _fill_holes(out, parents, kept)
    chains = {}
    for (v, u), s in slide.items():
        far = slide.get((u, v), u)
        lo, hi = (s, far) if v < u else (far, s)
        chains[min(v, u), max(v, u)] = [lo, hi]
    return Change(pts, out, parents, chains, kept)


def _fill_holes(out, parents, kept):
    """One face for each hole the bands leave at a corner (half-edges with no twin, walked the other way)."""
    owner = {(f[i], f[(i + 1) % len(f)]): n for n, f in enumerate(out) for i in range(len(f))}
    nxt = {y: x for (x, y) in owner if (y, x) not in owner}
    while nxt:
        start = v = next(iter(nxt))
        ring = []
        while True:
            ring.append(v)
            v = nxt.pop(v)
            if v == start:
                break
            if v not in nxt:
                raise ValueError("internal: the bevel left an open hole it could not close")
        if len(ring) >= 3:
            kept.add(len(out))
            parents.append(parents[owner[ring[1], ring[0]]])
            out.append(ring)
