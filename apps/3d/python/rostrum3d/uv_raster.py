"""Which spot of a surface each texel of its unfolded paint picture shows: the triangles laid into the picture by
their (u, v), each texel's centre taking the triangle holding it and where in it (barycentric). Numpy, in chunks of
triangles (a clay's many small ones and a mesh's few large ones alike); a texel outside every piece shows none.

`Geo` is a surface as the masks need it: `points` (n × 3, the item's own space), `tris` (m × 3), `uv` (m × 3 × 2, per
triangle corner, t up): a clay's CLS1 surface (clay_paint.Surface) or a mesh's built mesh with its `uvs`.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

CHUNK = 4_000_000                   # texel candidates per step (memory: ~100 MB at most)


@dataclass
class Geo:
    points: np.ndarray
    tris: np.ndarray
    uv: np.ndarray

    @classmethod
    def of_surface(cls, surface) -> "Geo":
        return cls(surface.points, surface.tris, surface.uv)

    @classmethod
    def of_mesh(cls, geometry: dict, uvs) -> "Geo":
        """A mesh's built mesh (the engine's `geometry`: points, faceCounts, faceIndices) and its `uvs` (one per face
        corner, the same order), each face a fan of triangles. Loud when the uvs don't fit the faces."""
        pts = np.asarray(geometry["points"], np.float64).reshape(-1, 3)
        counts = np.asarray(geometry["faceCounts"], np.int64)
        idx = np.asarray(geometry["faceIndices"], np.int64)
        uv = np.asarray(uvs, np.float64).reshape(-1, 2)
        if len(uv) != len(idx):
            raise ValueError(f"the mesh's unfolding has {len(uv)} corners, its faces {len(idx)}: unfold it again")
        starts = np.concatenate([[0], np.cumsum(counts)[:-1]])
        fan = [(s, s + k, s + k + 1) for s, c in zip(starts.tolist(), counts.tolist()) for k in range(1, c - 1)]
        corner = np.asarray(fan, np.int64).reshape(-1, 3)
        return cls(pts, idx[corner], uv[corner])


def raster(geo: Geo, size: int) -> tuple[np.ndarray, np.ndarray]:
    """(tri: size × size int32, -1 where none; bary: size × size × 3 float32), rows top first (y = (1 − v) × size)."""
    px = np.stack([geo.uv[..., 0] * size - 0.5, (1.0 - geo.uv[..., 1]) * size - 0.5], -1)   # texel-centre coordinates
    lo = np.clip(np.ceil(px.min(1)), 0, size - 1).astype(np.int64)
    hi = np.clip(np.floor(px.max(1)), 0, size - 1).astype(np.int64)
    w, h = np.maximum(hi[:, 0] - lo[:, 0] + 1, 0), np.maximum(hi[:, 1] - lo[:, 1] + 1, 0)
    n = w * h
    tri_of = np.full(size * size, -1, np.int32)
    bary = np.zeros((size * size, 3), np.float32)
    order = np.nonzero(n)[0]
    at = 0
    while at < len(order):
        take = np.cumsum(n[order[at:]])
        end = at + max(1, int(np.searchsorted(take, CHUNK)))
        t = order[at:end]
        at = end
        k = n[t]
        rep = np.repeat(np.arange(len(t)), k)
        local = np.arange(int(k.sum())) - np.repeat(np.cumsum(k) - k, k)
        x = lo[t, 0][rep] + local % w[t][rep]
        y = lo[t, 1][rep] + local // w[t][rep]
        a, b, c = (px[t, i][rep] for i in range(3))
        v0, v1 = b - a, c - a
        v2 = np.stack([x, y], 1) - a
        den = v0[:, 0] * v1[:, 1] - v1[:, 0] * v0[:, 1]
        ok = np.abs(den) > 1e-12
        den = np.where(ok, den, 1.0)
        w1 = (v2[:, 0] * v1[:, 1] - v1[:, 0] * v2[:, 1]) / den
        w2 = (v0[:, 0] * v2[:, 1] - v2[:, 0] * v0[:, 1]) / den
        w0 = 1 - w1 - w2
        inside = ok & (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        cell = (y * size + x)[inside]
        tri_of[cell] = t[rep[inside]]
        bary[cell] = np.stack([w0, w1, w2], 1)[inside]
    return tri_of.reshape(size, size), bary.reshape(size, size, 3)
