"""What Edit mesh draws and what it may pick, from the mesh alone (SPEC §4.3). No Qt. Two rules, each in one place:

- Which edges a person edits. An edge between two faces that meet at a shallow angle (under SOFT_DEG: both sides are
  part of one curved run, like a rounded corner) is drawn faint; flat faces meeting at a real angle, open borders and
  edges shared by three or more faces are drawn in full.
- What is visible. A point, an edge middle or a face centre is seen when nothing of the mesh stands between it and the
  camera (a ray from the camera, tested against every triangle). Box select and click pick only what is seen, unless
  X-ray is on.
"""
from __future__ import annotations

import math

import numpy as np

SOFT_DEG = 35.0
EPS = 1e-3                       # a ray that stops this near its target (of its length) has arrived


def _unit_normals(pts, faces):
    out = []
    for idx in faces:
        n, a = np.zeros(3), pts[idx[0]]
        for k in range(1, len(idx) - 1):
            n += np.cross(pts[idx[k]] - a, pts[idx[k + 1]] - a)
        length = np.linalg.norm(n)
        out.append(n / length if length > 1e-18 else None)
    return out


def soft_edges(pts, faces, edges) -> set[int]:
    """Indices into `edges` of those drawn faint: two faces, normals within SOFT_DEG of each other."""
    p = np.asarray(pts, dtype=float)
    normals, on = _unit_normals(p, faces), {}
    for f, idx in enumerate(faces):
        for i, a in enumerate(idx):
            b = idx[(i + 1) % len(idx)]
            on.setdefault((min(a, b), max(a, b)), []).append(f)
    cos = math.cos(math.radians(SOFT_DEG))
    soft = set()
    for i, e in enumerate(edges):
        fs = on.get(tuple(e), [])
        if len(fs) == 2 and normals[fs[0]] is not None and normals[fs[1]] is not None \
                and float(np.dot(normals[fs[0]], normals[fs[1]])) >= cos:
            soft.add(i)
    return soft


def triangles(pts, faces):
    """Every face as a fan of triangles: array (n, 3, 3)."""
    p = np.asarray(pts, dtype=float)
    return np.array([[p[idx[0]], p[idx[k]], p[idx[k + 1]]] for idx in faces for k in range(1, len(idx) - 1)]
                    or np.zeros((0, 3, 3)))


def visible(eye, targets, tris) -> list[bool]:
    """For each target (a world point): True when no triangle blocks the ray from `eye` to it (Möller–Trumbore, both
    sides, vectorised: meshes here are small)."""
    t = np.asarray(targets, dtype=float).reshape(-1, 3)
    if len(tris) == 0 or len(t) == 0:
        return [True] * len(t)
    o = np.asarray(eye, dtype=float)
    a, e1, e2 = tris[:, 0], tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]
    out = []
    for lo in range(0, len(t), 128):
        d = t[lo:lo + 128] - o                                   # (n, 3), a hit at s in (0, 1) is in front of the target
        h = np.cross(d[:, None, :], e2[None])                    # (n, m, 3)
        det = np.einsum("mk,nmk->nm", e1, h)
        ok = np.abs(det) > 1e-14
        inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        s = o - a                                                # (m, 3)
        u = np.einsum("mk,nmk->nm", s, h) * inv
        q = np.cross(s, e1)                                      # (m, 3)
        v = np.einsum("nk,mk->nm", d, q) * inv
        dist = np.einsum("mk,mk->m", e2, q)[None] * inv
        hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (dist > 1e-9) & (dist < 1 - EPS)
        out.extend(~hit.any(axis=1))
    return [bool(x) for x in out]
