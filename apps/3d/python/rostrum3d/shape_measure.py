"""An item's form in numbers (SPEC § 6, look_shape): its outlines from the front, the side and the top as three masks
on one grid, and what they measure. numpy only.

The item's own space: +Y up, it faces +Z, its left is +X (the joint finder's convention). A `Views` holds
`front` [x, y], `side` [z, y] and `top` [x, z] (True = the item is there), the cell size (metres) and the centres of
the grid's first cell on each axis. From a clay's grid (clay_grid, inside cells [x, y, z]) or from a mesh's triangles
(raster: each triangle's shadow on each plane).

Measures: height, width, depth; the width (front) and depth (side) at each tenth of the height, and in how many
parts the item is cut there (two legs: 2); the widest; the left–right difference (the front outline against its
mirror across X = 0); thin spots (a clay's grid only: where its middle is thinner than `thin`).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

LEVELS = range(1, 10)           # tenths of the height
OFF = 1.5                       # a side differing by more than this many cells is "off"
SLACK = 0.5                     # cells: a curved surface's staircase on the grid is not a thin spot


@dataclass
class Views:
    front: np.ndarray           # [x, y]
    side: np.ndarray            # [z, y]
    top: np.ndarray             # [x, z]
    cell: float
    start: tuple                # (x, y, z) of the first cell's centre
    exact: tuple | None = None  # (low, high) corners when known exactly (a mesh's points), else from the cells


def from_grid(occ: np.ndarray, origin, cell: float) -> Views:
    """From a bool grid [x, y, z] whose cell (i, j, k) centres at origin + (index + 0.5) × cell."""
    return Views(occ.any(axis=2), occ.any(axis=0).T, occ.any(axis=1), float(cell),
                 tuple(float(o) + 0.5 * cell for o in origin))


def from_triangles(points, tris, cells: int = 160) -> Views:
    """From a mesh (points [N, 3], triangles [M, 3] indices): each triangle's shadow drawn on each plane."""
    from PIL import Image, ImageDraw
    p = np.asarray(points, float)
    lo, hi = p.min(axis=0), p.max(axis=0)
    cell = float((hi - lo).max()) / cells or 1e-3
    lo = lo - cell
    n = np.ceil((hi - lo) / cell).astype(int) + 2
    g = (p - lo) / cell - 0.5                                     # grid units, cell centres on integers

    def shadow(a, b):
        im = Image.new("1", (int(n[a]), int(n[b])))
        d = ImageDraw.Draw(im)
        for t in tris:
            d.polygon([(g[i, a], g[i, b]) for i in t], fill=1, outline=1)
        return np.asarray(im, bool).T                             # [a, b]
    return Views(shadow(0, 1), shadow(2, 1), shadow(0, 2), cell, tuple(float(v) + 0.5 * cell for v in lo),
                 (p.min(axis=0).tolist(), p.max(axis=0).tolist()))


def _span(row: np.ndarray) -> tuple[int, int, int]:
    """(first, last, parts) of a row of cells; (-1, -1, 0) when empty."""
    on = np.flatnonzero(row)
    if not on.size:
        return -1, -1, 0
    return int(on[0]), int(on[-1]), int(1 + (np.diff(on) > 1).sum())


def _extent(mask: np.ndarray, axis: int) -> tuple[int, int]:
    on = np.flatnonzero(mask.any(axis=1 - axis))
    return int(on[0]), int(on[-1])


def measure(v: Views) -> dict:
    """Height, width, depth (m), the low/high corners, the widths at each tenth, the widest, the left–right check."""
    c, (sx, sy, sz) = v.cell, v.start
    x0, x1 = _extent(v.front, 0)
    y0, y1 = _extent(v.front, 1)
    z0, z1 = _extent(v.side, 0)
    size = [(x1 - x0 + 1) * c, (y1 - y0 + 1) * c, (z1 - z0 + 1) * c]
    out = {"height": size[1], "width": size[0], "depth": size[2], "cell": c,
           "low": [sx + (x0 - 0.5) * c, sy + (y0 - 0.5) * c, sz + (z0 - 0.5) * c],
           "high": [sx + (x1 + 0.5) * c, sy + (y1 + 0.5) * c, sz + (z1 + 0.5) * c], "levels": []}
    if v.exact:
        out["low"], out["high"] = [float(a) for a in v.exact[0]], [float(a) for a in v.exact[1]]
        out["width"], out["height"], out["depth"] = (out["high"][k] - out["low"][k] for k in range(3))
    mid = -sx / c                                                 # X = 0, in cells (may fall between two)
    for k in LEVELS:
        j = min(y1, y0 + int(k / 10 * (y1 - y0 + 1)))
        a, b, parts = _span(v.front[:, j])
        za, zb, _ = _span(v.side[:, j])
        row = {"percent": k * 10, "y": sy + j * c, "width": (b - a + 1) * c if parts else 0.0, "parts": parts,
               "depth": (zb - za + 1) * c if za >= 0 else 0.0}
        if parts:
            row["left"], row["right"] = (b + 0.5 - mid) * c, (mid - a + 0.5) * c     # +X is the item's left
        out["levels"].append(row)
    widths = [(_span(v.front[:, j]), j) for j in range(y0, y1 + 1)]
    (a, b, _), j = max(widths, key=lambda w: w[0][1] - w[0][0])
    out["widest"] = {"width": (b - a + 1) * c, "percent": round(100 * (j - y0 + 0.5) / (y1 - y0 + 1))}
    out["mirror"] = _mirror(v.front, mid, y0, y1, c)
    return _rounded(out)


def _rounded(v):
    if isinstance(v, float):
        return round(v, 4) + 0.0
    if isinstance(v, dict):
        return {k: _rounded(x) for k, x in v.items()}
    return [_rounded(x) for x in v] if isinstance(v, list) else v


def _mirror(front: np.ndarray, mid: float, y0: int, y1: int, c: float) -> dict:
    """The front outline against itself mirrored across X = 0: the share of it that differs, and the worst rows."""
    n = front.shape[0]
    flip = np.zeros_like(front)
    src = np.rint(2 * mid - np.arange(n)).astype(int)
    ok = (src >= 0) & (src < n)
    flip[ok] = front[src[ok]]
    differ = front ^ flip
    share = float(differ.sum()) / max(1, int(front.sum()))
    rows = []
    for j in range(y0, y1 + 1):
        d = int(differ[:, j].sum()) // 2
        if d > OFF:
            rows.append((d * c, round(100 * (j - y0 + 0.5) / (y1 - y0 + 1))))
    worst = max(rows, default=(0.0, 0))
    return {"differs": round(share * 100, 1), "worst": worst[0], "worstPercent": worst[1],
            "offFrom": min((p for _, p in rows), default=None), "offTo": max((p for _, p in rows), default=None)}


def thin_spots(occ: np.ndarray, origin, cell: float, thin: float, depth=None, most: int = 6) -> list[dict]:
    """Places thinner than `thin` metres: the cells no ball `thin` across fits round (the shape opened by that ball),
    grouped where they touch; [{at (clay space, the group's middle), thickness (its thickest middle), cells}], thinnest
    first; groups of fewer than 3 cells (a sharp corner's tip) are left out. `depth`: pose_joints.depth(occ) when known."""
    from .pose_joints import depth as edt
    d = edt(occ) if depth is None else depth
    r = thin / (2 * cell)                                         # the ball's radius in cells
    core = d >= r                                                 # where the ball's centre can stand
    reach = edt(~core) <= r + SLACK if core.any() else np.zeros_like(occ)     # within the ball of a centre that fits
    left = occ & ~reach & ~core
    groups = []
    seen = np.zeros_like(left)
    for start in map(tuple, np.argwhere(left)):
        if seen[start]:
            continue
        seen[start], todo, cells = True, [start], []
        while todo:
            c = todo.pop()
            cells.append(c)
            for o in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                n = (c[0] + o[0], c[1] + o[1], c[2] + o[2])
                if all(0 <= n[k] < left.shape[k] for k in range(3)) and left[n] and not seen[n]:
                    seen[n] = True
                    todo.append(n)
        if len(cells) >= 3:
            a = np.asarray(cells)
            t = max(1.0, 2 * float(d[tuple(a.T)].max()) - 1) * cell
            groups.append({"at": [round(float(v), 4) for v in np.asarray(origin) + (a.mean(axis=0) + 0.5) * cell],
                           "thickness": round(t, 4), "cells": len(cells)})
    return sorted(groups, key=lambda g: (g["thickness"], -g["cells"]))[:most]
