"""A clay's paint, kept on its surface (paint_fields.STROKE) and laid back on whatever shape the clay has now.

A clay has no fixed unfolded surface: every reshape makes a new one. So the core unfolds the painted clay's surface
for each shape (ENGINE_CONTRACT v1.17, clay `paint`) into a CLS1 file in the shared cache (`surface_file`: keyed by
the clay's last step key, its detail and the paint size), and a clay stroke is kept as `anchors` on the surface
([x, y, z, nx, ny, nz, pressure] in the clay's own space) and `reach` (its brush radius in metres). Each time the
paint pictures are made, `laid` turns those into the kit's stroke on this surface: the path is resampled densely in
3D, each sample goes along its own normal to where the surface is now (so paint rides over a bulge raised under it,
or sinks into a carve, instead of sliding to the nearest rim), then to the nearest point of the surface on its side
(a triangle and where in it), that point's
(u, v) to canvas pixels, the brush size from `reach` and the surface's metres per pixel there; where the path crosses
a cut of the unfolded surface (a seam) the stroke is split there; each stretch's round end covers the cut. Strokes with `points` and no anchors are used as they are (pixels). A brush near a cut spills past its own
piece into the picture's neighbouring pieces, which are other places on the clay: `trim` keeps a layer's paint only
on texels whose spot on the clay is within the brush's reach of its strokes.

CLS1 (little-endian): "CLS1", u32 version, size, nPoints, nTris, nBlocks; f32 points[3n], normals[3n]; i32 tris[3m];
f32 uv[6m] (per triangle corner, t up); i32 blocks[4b].
"""
from __future__ import annotations

import threading
from collections import OrderedDict
from pathlib import Path

import numpy as np
from rostrum_core.cache import CACHE, cache_key

VERSION = "rostrum3d-claysurf@4"     # bump with the core's CLS1 writer (its unfold) or this file's reading of it
MAGIC, FORMAT = b"CLS1", 1
STEP = 0.25                          # resample the path every STEP × reach in 3D ...
MOST = 4000                          # ... and at most this many samples a stroke
NEAR_VERTS, VALENCE = 8, 16          # nearest-point search: triangles round the 8 nearest points (≤ 16 each),
CHUNK = 256                          # for this many samples at a time
REACH_EDGES = 48                     # along the normal: up to this many edge lengths each way, one edge a step
_LOCK = threading.RLock()


def surface_file(last_key: str, detail: float, size: int) -> Path:
    """Where the core keeps a painted clay's unfolded surface for this shape, detail and paint size."""
    key = cache_key("clay.surface", VERSION, [last_key], {"detail": detail, "size": size})
    return CACHE.path("claysurf", key) / "surface.cls"


class Surface:
    """A CLS1 file, read: `points`, `normals` (n×3), `tris` (m×3), `uv` (m×3×2), `size`, `key` (its cache name)."""

    def __init__(self, path: Path):
        raw = Path(path).read_bytes()
        head = np.frombuffer(raw, "<u4", 5, 4) if len(raw) >= 24 else None
        if raw[:4] != MAGIC or head is None or head[0] != FORMAT:
            raise ValueError(f"{path}: not a CLS1 surface (version {FORMAT}) file")
        _, self.size, n, m, b = (int(v) for v in head)
        want = 24 + 4 * (6 * n + 3 * m + 6 * m + 4 * b)
        if len(raw) != want:
            raise ValueError(f"{path}: a CLS1 file of {n} points, {m} triangles and {b} blocks is {want} bytes; "
                             f"it has {len(raw)} (cut short or written by another version)")
        at = 24
        def take(dtype, count):
            nonlocal at
            out = np.frombuffer(raw, dtype, count, at)
            at += 4 * count
            return out
        self.points = take("<f4", 3 * n).reshape(n, 3).astype(np.float64)
        self.normals = take("<f4", 3 * n).reshape(n, 3).astype(np.float64)
        self.tris = take("<i4", 3 * m).reshape(m, 3).astype(np.int64)
        self.uv = take("<f4", 6 * m).reshape(m, 3, 2).astype(np.float64)
        if m and (self.tris.min() < 0 or self.tris.max() >= n):
            raise ValueError(f"{path}: a triangle names a point that isn't there")
        self.key = Path(path).parent.name
        a, b_, c = (self.points[self.tris[:, i]] for i in range(3))
        cross = np.cross(b_ - a, c - a)
        area3 = np.linalg.norm(cross, axis=1) / 2
        self.facing = cross / np.maximum(area3 * 2, 1e-30)[:, None]
        e1, e2 = self.uv[:, 1] - self.uv[:, 0], self.uv[:, 2] - self.uv[:, 0]
        area_px = np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]) / 2 * self.size ** 2
        ok = area_px > 1e-12
        mpp = np.where(ok, np.sqrt(area3 / np.where(ok, area_px, 1)), np.nan)     # metres per canvas px
        self.mpp = np.where(np.isfinite(mpp), mpp, np.nanmedian(mpp) if ok.any() else 1e-3)
        self._tree = self._around = None

    def _index(self):
        """The search: a k-d tree of the points, and each point's triangles (padded with -1)."""
        if self._tree is None:
            from scipy.spatial import cKDTree
            flat = self.tris.ravel()
            order = np.argsort(flat, kind="stable")
            verts, tri = flat[order], order // 3
            starts = np.searchsorted(verts, np.arange(len(self.points)))
            rank = np.arange(len(verts)) - starts[verts]
            keep = rank < VALENCE
            around = np.full((len(self.points), VALENCE), -1, np.int64)
            around[verts[keep], rank[keep]] = tri[keep]
            self._around, self._tree = around, cKDTree(self.points)
        return self._tree, self._around

    def nearest(self, pts: np.ndarray, nrm: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """(triangle, barycentric (a×3)) of the surface point nearest each of `pts` (a×3) on the side its normal
        (`nrm`) faces: a thin part's far side is never taken while a near triangle faces the same way."""
        if len(pts) > CHUNK:                                             # bounded memory: CHUNK samples at a time
            parts = [self.nearest(pts[i:i + CHUNK], nrm[i:i + CHUNK]) for i in range(0, len(pts), CHUNK)]
            return np.concatenate([p[0] for p in parts]), np.concatenate([p[1] for p in parts])
        tree, around = self._index()
        _, near = tree.query(pts, min(NEAR_VERTS, len(self.points)))
        cand = around[near].reshape(len(pts), -1)                         # a × (k·VALENCE), -1 = none
        safe = np.maximum(cand, 0)
        corners = self.points[self.tris[safe]]                            # a × c × 3 × 3
        bary = _closest(pts[:, None, :], corners[..., 0, :], corners[..., 1, :], corners[..., 2, :])
        spot = np.einsum("acj,acjk->ack", bary, corners)
        d2 = np.where(cand >= 0, ((spot - pts[:, None, :]) ** 2).sum(-1), np.inf)
        d2 = np.where(np.isfinite(d2), d2, np.inf)
        away = np.einsum("ack,ak->ac", self.facing[safe], nrm) < 0
        pick = np.argmin(np.where(away, d2 + 1e6, d2), axis=1)            # facing its way first; else the nearest
        rows = np.arange(len(pts))
        return cand[rows, pick], bary[rows, pick]

    def along_normal(self, pts: np.ndarray, nrm: np.ndarray) -> np.ndarray:
        """Each of `pts` moved along its normal to where the surface is now: the step nearest the old place (either
        way) whose nearest surface point is within an edge. A point still on the surface, or with no surface along its
        line, stays (the nearest-point search then takes it)."""
        if not len(pts) or not len(self.points):
            return pts
        tree, _ = self._index()
        edge = self.edge
        ts = np.arange(-REACH_EDGES, REACH_EDGES + 1) * edge
        ts = ts[np.argsort(np.abs(ts), kind="stable")]                     # 0, -e, +e, -2e, … nearest first
        out = pts.copy()
        for i in range(0, len(pts), CHUNK):
            p, n = pts[i:i + CHUNK], nrm[i:i + CHUNK]
            line = p[:, None, :] + ts[None, :, None] * n[:, None, :]       # a × t × 3
            d, _ = tree.query(line.reshape(-1, 3), 1)
            d = d.reshape(len(p), len(ts))
            near = d < 0.75 * edge
            first = np.argmax(near, axis=1)
            # a point still on the surface (within 1.5 edges of it: ts[0] is 0) stays exactly where it is, so an
            # unchanged part of a stroke is laid exactly as before; only a point the reshape left off it moves
            hit = near[np.arange(len(p)), first] & (d[:, 0] > 1.5 * edge)
            out[i:i + CHUNK] = np.where(hit[:, None], p + ts[first][:, None] * n, p)
        return out

    @property
    def edge(self) -> float:
        """The surface's typical edge length (metres)."""
        if getattr(self, "_edge", None) is None:
            e = np.linalg.norm(self.points[self.tris[:, 1]] - self.points[self.tris[:, 0]], axis=1)
            self._edge = float(np.median(e)) if len(e) else 1e-3
        return self._edge

    def canvas_px(self, tri: np.ndarray, bary: np.ndarray) -> np.ndarray:
        """Canvas pixels (x right, y down) of points given as (triangle, barycentric): u × size, (1 − v) × size."""
        uv = np.einsum("aj,ajk->ak", bary, self.uv[tri])
        return np.stack([uv[:, 0] * self.size, (1.0 - uv[:, 1]) * self.size], axis=1)

    def at(self, tri: np.ndarray, pts: np.ndarray) -> np.ndarray:
        """Barycentric of `pts` in the planes of triangles `tri`, outside them too (a seam's one step across)."""
        a, b, c = (self.points[self.tris[tri, i]] for i in range(3))
        v0, v1, v2 = b - a, c - a, pts - a
        d00, d01, d11 = (v0 * v0).sum(1), (v0 * v1).sum(1), (v1 * v1).sum(1)
        d20, d21 = (v2 * v0).sum(1), (v2 * v1).sum(1)
        den = np.where(np.abs(d00 * d11 - d01 ** 2) > 1e-30, d00 * d11 - d01 ** 2, 1e-30)
        v, w = (d11 * d20 - d01 * d21) / den, (d00 * d21 - d01 * d20) / den
        return np.stack([1 - v - w, v, w], axis=1)


def _dot(x, y):
    return (x * y).sum(-1)


def _closest(p, a, b, c):
    """Barycentric of the point of triangle abc nearest p (Ericson, Real-Time Collision Detection 5.1.5), batched."""
    ab, ac, ap, bp, cp = b - a, c - a, p - a, p - b, p - c
    d1, d2, d3, d4, d5, d6 = _dot(ab, ap), _dot(ac, ap), _dot(ab, bp), _dot(ac, bp), _dot(ab, cp), _dot(ac, cp)
    va, vb, vc = d3 * d6 - d5 * d4, d5 * d2 - d1 * d6, d1 * d4 - d3 * d2
    with np.errstate(divide="ignore", invalid="ignore"):
        s = va + vb + vc
        v, w = vb / s, vc / s
        out = np.stack([1 - v - w, v, w], -1)                                     # inside
        t = (d4 - d3) / ((d4 - d3) + (d5 - d6))
        out = _where((va <= 0) & (d4 - d3 >= 0) & (d5 - d6 >= 0), [0 * t, 1 - t, t], out)   # edge bc
        t = d2 / (d2 - d6)
        out = _where((vb <= 0) & (d2 >= 0) & (d6 <= 0), [1 - t, 0 * t, t], out)    # edge ac
        out = _where((d6 >= 0) & (d5 <= d6), [0 * d6, 0 * d6, 0 * d6 + 1], out)   # corner c
        t = d1 / (d1 - d3)
        out = _where((vc <= 0) & (d1 >= 0) & (d3 <= 0), [1 - t, t, 0 * t], out)    # edge ab
        out = _where((d3 >= 0) & (d4 <= d3), [0 * d3, 0 * d3 + 1, 0 * d3], out)   # corner b
        out = _where((d1 <= 0) & (d2 <= 0), [0 * d1 + 1, 0 * d1, 0 * d1], out)     # corner a
    return np.nan_to_num(out, nan=1 / 3, posinf=1 / 3, neginf=1 / 3)


def _where(cond, parts, out):
    return np.where(cond[..., None], np.stack(parts, -1), out)


_SURFACES: OrderedDict = OrderedDict()      # path -> Surface (a path is content-keyed: never rewritten)
_LAID: OrderedDict = OrderedDict()          # (surface key, stroke id) -> (the stroke item, its laid strokes)


def read(path) -> Surface:
    """The surface in the file at `path` (kept: the same file is read once)."""
    path = str(path)
    with _LOCK:
        if path in _SURFACES:
            _SURFACES.move_to_end(path)
            return _SURFACES[path]
    s = Surface(Path(path))
    with _LOCK:
        _SURFACES[path] = s
        while len(_SURFACES) > 3:
            _SURFACES.popitem(last=False)
    return s


def _samples(anchors: np.ndarray, reach: float) -> np.ndarray:
    """The path resampled every STEP × reach (at most MOST samples), each row [x, y, z, nx, ny, nz, pressure]."""
    if len(anchors) < 2:
        return anchors
    seg = np.linalg.norm(np.diff(anchors[:, :3], axis=0), axis=1)
    run = np.concatenate([[0.0], np.cumsum(seg)])
    n = int(min(MOST, max(2, np.ceil(run[-1] / max(STEP * reach, 1e-9)) + 1)))
    at = np.linspace(0, run[-1], n)
    out = np.stack([np.interp(at, run, anchors[:, k]) for k in range(7)], axis=1)
    out[:, 3:6] /= np.maximum(np.linalg.norm(out[:, 3:6], axis=1), 1e-12)[:, None]
    return out


def lay(surface: Surface, stroke: dict) -> list[dict]:
    """One anchored stroke → the kit's strokes on this surface (one per stretch between seams), each with `points`
    (canvas px, pressure) and `size` (px), `anchors` and `reach` left out. The first keeps the stroke's id."""
    a = _samples(np.asarray(stroke["anchors"], np.float64), float(stroke["reach"]))
    tri, bary = surface.nearest(surface.along_normal(a[:, :3], a[:, 3:6]), a[:, 3:6])
    px = surface.canvas_px(tri, bary)
    mpp = surface.mpp[tri]
    step3 = np.linalg.norm(np.diff(a[:, :3], axis=0), axis=1)
    step_px = np.linalg.norm(np.diff(px, axis=0), axis=1)
    cut = np.nonzero(step_px > 3 * step3 / np.minimum(mpp[:-1], mpp[1:]) + 4)[0]    # a jump: the path crossed a seam
    bounds = [0, *(cut + 1), len(a)]
    base = {k: v for k, v in stroke.items() if k not in ("anchors", "reach")}
    out = []
    for k, (i, j) in enumerate(zip(bounds[:-1], bounds[1:])):
        # a stretch ends at its last sample before the cut: the brush's round end (a quarter reach on) covers the
        # cut, and `trim` keeps what spills past it off other places. (A point extrapolated past the cut in the
        # stretch's own plane made blots where small, curved pieces meet.)
        pts = [[*px[q], a[q, 6]] for q in range(i, j)]
        if len(pts) == 1:                                    # a click: one dab
            pts.append([pts[0][0] + 0.01, *pts[0][1:]])
        size = max(0.5, 2 * float(stroke["reach"]) / float(np.median(mpp[i:j])))
        out.append({**base, "id": stroke["id"] if k == 0 else f'{stroke["id"]}.{k}', "size": round(size, 3),
                    "points": [[round(float(x), 2), round(float(y), 2), round(float(p), 4)] for x, y, p in pts]})
    return out


def laid(canvas: dict, surface: Surface) -> dict:
    """The clay `canvas` (its paints and paintmasks) with every anchored stroke laid on `surface`: what the kit draws.
    A laid stroke is kept while the stroke item and the surface are the same, so the kit's own memo of its strokes
    (rostrum_paint.canvas) holds across compiles."""
    paints = []
    for layer in canvas.get("paints", []):
        strokes = []
        for s in layer.get("strokes", []):
            if s.get("type") != "stroke" or not s.get("anchors"):
                strokes.append(s)
                continue
            key = (surface.key, s["id"])
            with _LOCK:
                got = _LAID.get(key)
            if got is None or got[0] is not s:
                got = (s, lay(surface, s))
                with _LOCK:
                    _LAID[key] = got
                    _LAID.move_to_end(key)
                    while len(_LAID) > 4096:
                        _LAID.popitem(last=False)
            strokes += got[1]
        paints.append({**layer, "strokes": strokes})
    return {"id": canvas["id"], "paints": paints, "paintmasks": canvas.get("paintmasks", [])}


TRIM = "trim@1"                       # in the picture's cache key: bump when `trim` changes


def _spots(surface: Surface, stroke: dict) -> np.ndarray:
    """Where a stroke's samples lie on `surface` (3D, the clay's own space)."""
    a = _samples(np.asarray(stroke["anchors"], np.float64), float(stroke["reach"]))
    tri, bary = surface.nearest(surface.along_normal(a[:, :3], a[:, 3:6]), a[:, 3:6])
    return np.einsum("aj,ajk->ak", bary, surface.points[surface.tris[tri]])


def _texel_spots(surface: Surface, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    """The clay spot (3D) each canvas texel shows: the triangle holding it in the unfolded picture, else (a texel of
    a piece's padding) the nearest one's edge."""
    if getattr(surface, "_uvtree", None) is None:
        from scipy.spatial import cKDTree
        surface._uvtree = cKDTree(surface.uv.mean(axis=1))
    uv = np.stack([(xs + 0.5) / surface.size, 1.0 - (ys + 0.5) / surface.size], 1)
    out = np.empty((len(uv), 3))
    for i in range(0, len(uv), 4096):
        q = uv[i:i + 4096]
        _, cand = surface._uvtree.query(q, min(8, len(surface.tris)))
        cand = cand.reshape(len(q), -1)
        a, b, c = (surface.uv[cand][..., k, :] for k in range(3))     # q × k × 2
        v0, v1, v2 = b - a, c - a, q[:, None, :] - a
        den = v0[..., 0] * v1[..., 1] - v1[..., 0] * v0[..., 1]
        den = np.where(np.abs(den) > 1e-20, den, 1e-20)
        w1 = (v2[..., 0] * v1[..., 1] - v1[..., 0] * v2[..., 1]) / den
        w2 = (v0[..., 0] * v2[..., 1] - v2[..., 0] * v0[..., 1]) / den
        w0 = 1 - w1 - w2
        worst = np.minimum(np.minimum(w0, w1), w2)                      # ≥ 0 inside
        pick = np.argmax(worst, axis=1)                                 # inside if any, else the least outside
        rows = np.arange(len(q))
        bary = np.clip(np.stack([w0[rows, pick], w1[rows, pick], w2[rows, pick]], 1), 0, 1)
        bary /= np.maximum(bary.sum(1, keepdims=True), 1e-12)
        corners = surface.points[surface.tris[cand[rows, pick]]]
        out[i:i + 4096] = np.einsum("aj,ajk->ak", bary, corners)
    return out


def trim(surface: Surface, layers: list, alpha: np.ndarray) -> np.ndarray:
    """`alpha` (size × size × 1, the layers' paint) kept only where the texel's spot on the clay is within reach of
    an anchored stroke of `layers`. Layers with a pixel stroke (no anchors) are left as they are."""
    strokes = [s for layer in layers for s in layer.get("strokes", []) if s.get("type") == "stroke"]
    if not strokes or any(not s.get("anchors") for s in strokes):
        return alpha
    ys, xs = np.nonzero(alpha[..., 0] > 0)
    if not len(xs):
        return alpha
    from scipy.spatial import cKDTree
    spots = [(_spots(surface, s), float(s["reach"])) for s in strokes]
    pts = np.concatenate([p for p, _ in spots])
    reach = np.concatenate([np.full(len(p), r) for p, r in spots])
    d, idx = cKDTree(pts).query(_texel_spots(surface, xs, ys), 1)
    far = d > 1.25 * reach[idx] + 1.5 * surface.edge
    out = alpha.copy()
    out[ys[far], xs[far], 0] = 0
    return out


def metres_per_px(surface: Surface, local, normal) -> float:
    """The surface's metres per canvas pixel at the point nearest `local` (the clay's own space)."""
    tri, _ = surface.nearest(np.asarray([local], np.float64), np.asarray([normal], np.float64))
    return float(surface.mpp[tri[0]])
