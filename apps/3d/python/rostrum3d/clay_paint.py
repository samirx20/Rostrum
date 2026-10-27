"""A clay's paint, kept on its surface (paint_fields.STROKE) and laid back on whatever shape the clay has now.

A clay has no fixed unfolded surface: every reshape makes a new one. So the core unfolds the painted clay's surface
for each shape (ENGINE_CONTRACT v1.17, clay `paint`) into a CLS1 file in the shared cache (`surface_file`: keyed by
the clay's last step key, its detail and the paint size), and a clay stroke is kept as `anchors` on the surface
([x, y, z, nx, ny, nz, pressure] in the clay's own space) and `reach` (its brush radius in metres). Each time the
paint pictures are made, `laid` turns those into the kit's stroke on this surface: the path is resampled densely in
3D, each sample goes to the nearest point of the surface on its side (a triangle and where in it), that point's
(u, v) to canvas pixels, the brush size from `reach` and the surface's metres per pixel there; where the path crosses
a cut of the unfolded surface (a seam) the stroke is split, each half reaching one sample past the cut, so it crosses
cleanly. Strokes with `points` and no anchors are used as they are (pixels).

CLS1 (little-endian): "CLS1", u32 version, size, nPoints, nTris, nBlocks; f32 points[3n], normals[3n]; i32 tris[3m];
f32 uv[6m] (per triangle corner, t up); i32 blocks[4b].
"""
from __future__ import annotations

import threading
from collections import OrderedDict
from pathlib import Path

import numpy as np
from rostrum_core.cache import CACHE, cache_key

VERSION = "rostrum3d-claysurf@1"     # bump with the core's CLS1 writer (its unfold) or this file's reading of it
MAGIC, FORMAT = b"CLS1", 1
STEP = 0.25                          # resample the path every STEP × reach in 3D ...
MOST = 4000                          # ... and at most this many samples a stroke
NEAR_VERTS, VALENCE = 8, 16          # nearest-point search: triangles round the 8 nearest points (≤ 16 each),
CHUNK = 256                          # for this many samples at a time
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
    tri, bary = surface.nearest(a[:, :3], a[:, 3:6])
    px = surface.canvas_px(tri, bary)
    mpp = surface.mpp[tri]
    step3 = np.linalg.norm(np.diff(a[:, :3], axis=0), axis=1)
    step_px = np.linalg.norm(np.diff(px, axis=0), axis=1)
    cut = np.nonzero(step_px > 3 * step3 / np.minimum(mpp[:-1], mpp[1:]) + 4)[0]    # a jump: the path crossed a seam
    bounds = [0, *(cut + 1), len(a)]
    base = {k: v for k, v in stroke.items() if k not in ("anchors", "reach")}
    out = []
    for k, (i, j) in enumerate(zip(bounds[:-1], bounds[1:])):
        pts = [[*px[q], a[q, 6]] for q in range(i, j)]
        if j < len(a):                                       # one step past the cut, in this stretch's own plane
            pts.append([*surface.canvas_px(tri[j - 1:j], surface.at(tri[j - 1:j], a[j:j + 1, :3]))[0], a[j, 6]])
        if i > 0:
            pts.insert(0, [*surface.canvas_px(tri[i:i + 1], surface.at(tri[i:i + 1], a[i - 1:i, :3]))[0], a[i - 1, 6]])
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


def metres_per_px(surface: Surface, local, normal) -> float:
    """The surface's metres per canvas pixel at the point nearest `local` (the clay's own space)."""
    tri, _ = surface.nearest(np.asarray([local], np.float64), np.asarray([normal], np.float64))
    return float(surface.mpp[tri[0]])
