"""Seamless: a canvas whose edges are joined (its left edge meets its right, its top its bottom), so a picture made on it
repeats with no seam. Made while painting, never fixed after: a stroke with `wrap` lays every dab that crosses an
edge again on the opposite side (and in the corner, at a corner), so the two sides always meet.

`parts`: a planned stroke's dabs -> the parts each dab lays, in order: the dab moved into the canvas first, then its
copies a canvas width or height away that still reach the canvas. Every part of one dab is the same dab: they lay
with the same wet reservoir, the first part picks it up (reading across the edges: `ring`) and only the last takes it
up, so a smudge drags paint across the edge exactly as it does anywhere else. Both stampers (brush.dabs, the native
one) lay the parts as plain dabs; `again` marks a part that reuses its dab's pick-up.
"""
from __future__ import annotations

import math

import numpy as np


def parts(H: int, W: int, X, Y, R):
    """(which dab each part is, its x and y, again: not the dab's first part, last: the dab's last part) for dabs at X, Y
    of radius R on an H × W canvas that wraps. A part reaches the canvas when its box (brush.plan's: trunc(x - r) - 1
    to trunc(x + r) + 2) does."""
    bx, by = np.floor(X / W) * W, np.floor(Y / H) * H
    X0, Y0 = X - bx, Y - by                               # the dab moved into the canvas: its first part
    kx, ky = math.ceil((R.max() + 3) / W), math.ceil((R.max() + 3) / H)
    shifts = sorted(((mx, my) for mx in range(-kx, kx + 1) for my in range(-ky, ky + 1)),
                    key=lambda m: (m != (0, 0), abs(m[0]) + abs(m[1]), m))
    sx = np.array([m[0] * W for m in shifts], np.float64)[None, :]
    sy = np.array([m[1] * H for m in shifts], np.float64)[None, :]
    px, py, r = X0[:, None] + sx, Y0[:, None] + sy, R[:, None]
    reach = ((np.minimum(W, np.trunc(px + r).astype(int) + 2) > np.maximum(0, np.trunc(px - r).astype(int) - 1))
             & (np.minimum(H, np.trunc(py + r).astype(int) + 2) > np.maximum(0, np.trunc(py - r).astype(int) - 1)))
    reach[:, 0] = True                                    # the first part is always laid (its centre is on the canvas)
    i, m = np.nonzero(reach)                              # dab by dab, each dab's parts in `shifts` order
    again = np.concatenate([[False], i[1:] == i[:-1]])
    last = np.concatenate([i[:-1] != i[1:], [True]])
    return i, px[i, m], py[i, m], again, last


def ring(start: int, n: int, size: int) -> np.ndarray:
    """Indices start .. start + n - 1 read round a joined edge (the pick-up of a dab near it)."""
    return np.arange(start, start + n) % size
