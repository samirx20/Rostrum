"""One flat sewing-pattern piece → a fine, even triangle mesh (garment.py): the outline resampled at spacing ≤ h, cut into
triangles (ear clipping), made Delaunay by edge flips, then filled with a hex lattice of points h apart, each put in by
splitting the triangle it lands in and flipping its neighbours back to Delaunay. The outline's edges are never flipped
(the piece keeps its exact outline). Python and numpy only.
"""
from __future__ import annotations

import math

import numpy as np


def area2(poly) -> float:
    """Twice the signed area (anticlockwise > 0)."""
    return sum(poly[i - 1][0] * p[1] - p[0] * poly[i - 1][1] for i, p in enumerate(poly))


def _orient(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _incircle(a, b, c, d) -> bool:
    """d strictly inside the circle through anticlockwise a, b, c."""
    ax, ay, bx, by, cx, cy = a[0] - d[0], a[1] - d[1], b[0] - d[0], b[1] - d[1], c[0] - d[0], c[1] - d[1]
    a2, b2, c2 = ax * ax + ay * ay, bx * bx + by * by, cx * cx + cy * cy
    det = a2 * (bx * cy - cx * by) - b2 * (ax * cy - cx * ay) + c2 * (ax * by - bx * ay)
    return det > 1e-12 * (a2 + b2 + c2) ** 2          # relative: four points on one circle never flip back and forth


def _ears(pts, loop) -> list[list[int]]:
    """Ear clipping of the anticlockwise loop (point indices); collinear runs (a resampled edge) are never an ear tip."""
    idx, tris = list(loop), []
    while len(idx) > 3:
        n, best = len(idx), None
        for k in range(n):
            a, b, c = idx[k - 1], idx[k], idx[(k + 1) % n]
            if _orient(pts[a], pts[b], pts[c]) <= 1e-14:
                continue
            tri = (pts[a], pts[b], pts[c])
            if not any(q not in (a, b, c) and all(_orient(tri[i], tri[(i + 1) % 3], pts[q]) >= -1e-14 for i in range(3))
                       for q in idx):
                best = k
                break
        if best is None:                    # only touching points block every ear: take the fattest convex corner
            best = max(range(n), key=lambda k: _orient(pts[idx[k - 1]], pts[idx[k]], pts[idx[(k + 1) % n]]))
        tris.append([idx[best - 1], idx[best], idx[(best + 1) % n]])
        del idx[best]
    tris.append(list(idx))
    return tris


class _Mesh:
    """Triangles (anticlockwise) with neighbours: nb[t][k] is across the edge opposite corner k, -1 on the outline."""

    def __init__(self, pts, tris):
        self.p, self.t, self.nb = pts, tris, [[-1, -1, -1] for _ in tris]
        edges = {}
        for t, (a, b, c) in enumerate(tris):
            for k, (u, v) in enumerate(((b, c), (c, a), (a, b))):
                if (v, u) in edges:
                    s, j = edges.pop((v, u))
                    self.nb[t][k], self.nb[s][j] = s, t
                else:
                    edges[(u, v)] = (t, k)

    def _link(self, t, u, v, new):
        """Point t's neighbour across edge (u, v) at `new`."""
        if t < 0:
            return
        tri = self.t[t]
        for k in range(3):
            if {tri[(k + 1) % 3], tri[(k + 2) % 3]} == {u, v}:
                self.nb[t][k] = new
                return

    def flip(self, t, k) -> bool:
        """Flip the edge opposite corner k of t when the quad is convex and the far point is in t's circle."""
        s = self.nb[t][k]
        if s < 0:
            return False
        a, b, c = self.t[t][k], self.t[t][(k + 1) % 3], self.t[t][(k + 2) % 3]
        j = self.nb[s].index(t)
        d = self.t[s][j]
        P = self.p
        if not _incircle(P[a], P[b], P[c], P[d]) or _orient(P[a], P[b], P[d]) <= 0 or _orient(P[a], P[d], P[c]) <= 0:
            return False
        # t = (a, b, c), s = (d, c, b) → t = (a, b, d), s = (a, d, c)
        n_ab, n_ca = self.nb[t][(k + 2) % 3], self.nb[t][(k + 1) % 3]
        n_bd, n_dc = self.nb[s][(j + 1) % 3], self.nb[s][(j + 2) % 3]     # s = (d, c, b): opposite c, opposite b
        self.t[t], self.t[s] = [a, b, d], [a, d, c]
        self.nb[t], self.nb[s] = [n_bd, s, n_ab], [n_dc, n_ca, t]
        self._link(n_bd, b, d, t)
        self._link(n_ca, c, a, s)
        return True

    def legalise(self, stack):
        """Flip until every (t, k) on the stack, and what each flip exposes, is Delaunay; k is the edge facing the new point."""
        while stack:
            t, pnt = stack.pop()
            k = self.t[t].index(pnt)
            if self.flip(t, k):
                s = self.nb[t][1]          # t = (pnt, b, d), s = (pnt, d, c): their far edges face pnt
                stack += [(t, pnt), (s, pnt)]

    def lawson(self):
        """The whole triangulation to Delaunay (after ear clipping)."""
        stack = [(t, k) for t in range(len(self.t)) for k in range(3)]
        while stack:
            t, k = stack.pop()
            if self.flip(t, k):                # t = (a, b, d), s = (a, d, c): their other edges may now be wrong
                s = self.nb[t][1]
                stack += [(t, 0), (t, 2), (s, 0), (s, 1)]

    def locate(self, q, start):
        """(triangle holding q, edge k when q lies on its edge else -1); walks, then searches all when the walk leaves."""
        t, P = start, self.p
        for _ in range(int(4 * len(self.t) ** 0.5) + 50):
            tri, moved = self.t[t], False
            for k in range(3):
                if _orient(P[tri[(k + 1) % 3]], P[tri[(k + 2) % 3]], q) < -1e-15:
                    if self.nb[t][k] < 0:
                        break
                    t, moved = self.nb[t][k], True
                    break
            else:
                return t
            if not moved:
                break
        for t, tri in enumerate(self.t):
            if all(_orient(P[tri[(k + 1) % 3]], P[tri[(k + 2) % 3]], q) >= -1e-15 for k in range(3)):
                return t
        return -1

    def insert(self, q, t) -> int:
        """Split triangle t at the new point q into three, then legalise."""
        n = len(self.p)
        self.p.append(q)
        a, b, c = self.t[t]
        na, nbb, nc = self.nb[t]
        t1, t2 = len(self.t), len(self.t) + 1
        self.t[t] = [n, b, c]
        self.t.append([n, c, a])
        self.t.append([n, a, b])
        self.nb[t] = [na, t1, t2]
        self.nb.append([nbb, t2, t])
        self.nb.append([nc, t, t1])
        self._link(nbb, c, a, t1)
        self._link(nc, a, b, t2)
        self.legalise([(t, n), (t1, n), (t2, n)])
        return t


def _lattice(boundary, h: float):
    """The hex lattice points inside the outline and at least h / 2 from it: a coarse lattice first, then finer ones
    (every 8th row and column, 4th, 2nd, then the rest), each row by row, back and forth, so the triangles stay well
    shaped as it fills (few flips per point) and each walk to the next point is short."""
    b = np.asarray(boundary, dtype=float)
    lo, hi, dy = b.min(0), b.max(0), h * math.sqrt(3) / 2
    rows, level = [], []
    for r in range(int((hi[1] - lo[1]) / dy) + 1):
        c = np.arange(int((hi[0] - lo[0]) / h) + 2)
        c = c if r % 2 == 0 else c[::-1]
        xs = lo[0] + (c + 0.1234 + 0.5 * (r % 2)) * h                       # off the outline's grid
        rows.append(np.stack([xs, np.full(len(xs), lo[1] + (r + 0.0567) * dy)], 1))
        level.append(np.select([(r % 8 == 0) & (c % 8 == 0), (r % 4 == 0) & (c % 4 == 0), (r % 2 == 0) & (c % 2 == 0)],
                               [0, 1, 2], 3))
    q, level = np.concatenate(rows), np.concatenate(level)
    a, e = b, np.roll(b, -1, 0) - b                       # segment starts and directions
    inside = np.zeros(len(q), bool)
    near = np.full(len(q), np.inf)
    for i in range(len(b)):                               # one segment at a time: memory stays len(q)
        (ax, ay), (ex, ey) = a[i], e[i]
        cross = (ay > q[:, 1]) != (ay + ey > q[:, 1])
        with np.errstate(divide="ignore", invalid="ignore"):
            inside ^= cross & (q[:, 0] < ax + (q[:, 1] - ay) * ex / np.where(ey == 0, 1, ey))
        s = np.clip(((q[:, 0] - ax) * ex + (q[:, 1] - ay) * ey) / max(ex * ex + ey * ey, 1e-30), 0, 1)
        np.minimum(near, np.hypot(q[:, 0] - ax - s * ex, q[:, 1] - ay - s * ey), out=near)
    keep = inside & (near >= 0.5 * h)
    return [tuple(p) for p in q[keep][np.argsort(level[keep], kind="stable")].tolist()]


def triangulate(boundary, h: float) -> tuple[list, list]:
    """(points, triangles) of the anticlockwise resampled outline `boundary` ([x, y] each, consecutive ≤ h apart) filled
    with a hex lattice h apart. The first len(boundary) points are the boundary's, in order."""
    pts = [tuple(p) for p in boundary]
    m = _Mesh(pts, _ears(pts, range(len(pts))))
    m.lawson()
    t = 0
    for q in _lattice(boundary, h):
        found = m.locate(q, t)
        if found >= 0:
            t = m.insert(q, found)
    return m.p, m.t


def min_angle(pts, tris) -> float:
    """The smallest corner angle over all triangles, in degrees."""
    worst = 180.0
    for tri in tris:
        for k in range(3):
            a, b, c = pts[tri[k]], pts[tri[k - 1]], pts[tri[k - 2]]
            u, v = (b[0] - a[0], b[1] - a[1]), (c[0] - a[0], c[1] - a[1])
            cosv = (u[0] * v[0] + u[1] * v[1]) / max(1e-30, math.hypot(*u) * math.hypot(*v))
            worst = min(worst, math.degrees(math.acos(max(-1.0, min(1.0, cosv)))))
    return worst
