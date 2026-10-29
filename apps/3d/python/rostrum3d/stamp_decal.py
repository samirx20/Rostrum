"""A stamp on a clay, laid as a decal (paint.stamp with `at`). A clay's surface is laid flat in very many small pieces
(the core unfolds each shape anew: a typical clay's million triangles cover a small share of the picture), so one
round dab drawn on the flat picture would spill over dozens of unrelated pieces and only its middle would land. A
stamp is laid on the surface instead: every texel near the spot is placed on the stamp's own flat frame there (its up:
stamp_turn.surface_up, turned clockwise by `stampTurn`; its right) and reads the picture at that place, whatever piece
it is in. The picture fills the stamp's square of side 2 × `reach` (its padded copy: paint_stamp_pictures), times the
stroke's opacity, in the stroke's colour. Texels farther than `reach` from the spot along its direction (the clay's
other side) stay unpainted. paint_scene lays these under the layer's own strokes (as a projected picture is).
"""
from __future__ import annotations

import hashlib
import json
import math

import numpy as np
from rostrum_paint import pictures

from .stamp_turn import surface_up
from .uv_raster import Geo, raster


def is_stamp(stroke: dict) -> bool:
    return stroke.get("type", "stroke") == "stroke" and stroke.get("stampTurn") is not None and bool(stroke.get("anchors"))


def key(surface, strokes: list) -> str:
    """What a layer's decals depend on: the surface and the stamp strokes."""
    return hashlib.sha1(json.dumps([surface.key, strokes], sort_keys=True, default=str).encode()).hexdigest()


def frame(normal, turn: float, toward=None) -> tuple[np.ndarray, np.ndarray]:
    """(up, right) on the surface: upright (or along `toward` laid on the surface: a view stamp's screen up,
    stamp_view.py), turned clockwise by `turn` degrees as seen from outside."""
    n = np.asarray(normal, np.float64)
    n = n / max(np.linalg.norm(n), 1e-12)
    up = surface_up(n)
    if toward is not None:
        t = np.asarray(toward, np.float64)
        t = t - (t @ n) * n
        up = t / np.linalg.norm(t) if np.linalg.norm(t) > 1e-12 else up
    right = np.cross(up, n)
    c, s = math.cos(math.radians(turn)), math.sin(math.radians(turn))
    return c * up + s * right, c * right - s * up


def _sample(tip: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """The tip picture (n × n, rows top first) at x, y in -1..1 (y up), bilinear; 0 outside."""
    n = tip.shape[0]
    fx, fy = (x + 1) * (n - 1) / 2, (1 - y) * (n - 1) / 2
    inside = (fx >= 0) & (fx <= n - 1) & (fy >= 0) & (fy <= n - 1)
    fx, fy = np.clip(fx, 0, n - 1.001), np.clip(fy, 0, n - 1.001)
    x0, y0 = fx.astype(int), fy.astype(int)
    gx, gy = fx - x0, fy - y0
    v = (tip[y0, x0] * (1 - gx) + tip[y0, x0 + 1] * gx) * (1 - gy) + (tip[y0 + 1, x0] * (1 - gx) + tip[y0 + 1, x0 + 1] * gx) * gy
    return np.where(inside, v, 0.0)


def layer_rgba(surface, strokes: list, size: int) -> np.ndarray:
    """size × size × 4 float32 straight RGBA: the layer's stamps on `surface`, in order, each over the last."""
    out = np.zeros((size, size, 4), np.float32)
    if not strokes:
        return out
    from scipy.spatial import cKDTree
    tree = cKDTree(surface.points)
    for s in strokes:
        a = np.asarray(s["anchors"][0][:6], np.float64)
        n = a[3:6]
        tri0, bary0 = surface.nearest(surface.along_normal(a[None, :3], n[None]), n[None])
        p = (bary0[0] @ surface.points[surface.tris[tri0[0]]])
        reach = float(s["reach"])
        near = tree.query_ball_point(p, reach * 1.5 + surface.edge * 2)
        if not near:
            continue
        hit = np.isin(surface.tris, np.asarray(near)).any(1)
        ids = np.nonzero(hit)[0]
        tri, bary = raster(Geo(surface.points, surface.tris[ids], surface.uv[ids]), size)
        on = tri >= 0
        corners = surface.points[surface.tris[ids[tri[on]]]]
        d = np.einsum("aj,ajk->ak", bary[on], corners) - p
        up, right = frame(n, float(s["stampTurn"]), s.get("stampUp"))
        x, y = d @ right / reach, d @ up / reach
        alpha = _sample(pictures.tip(s["texture"]), x, y) * float(s.get("opacity", 1.0))
        alpha = np.where(np.abs(d @ n) < reach, alpha, 0.0)
        rgb = np.array([int(s["color"][i:i + 2], 16) / 255 for i in (1, 3, 5)], np.float32)
        ys, xs = np.nonzero(on)
        src_a = alpha.astype(np.float32)
        dst = out[ys, xs]
        out_a = src_a + dst[:, 3] * (1 - src_a)
        col = (rgb[None] * src_a[:, None] + dst[:, :3] * (dst[:, 3:] * (1 - src_a[:, None]))) / np.maximum(out_a, 1e-6)[:, None]
        out[ys, xs] = np.concatenate([np.where(out_a[:, None] > 1e-6, col, 0), out_a[:, None]], 1)
    return out
