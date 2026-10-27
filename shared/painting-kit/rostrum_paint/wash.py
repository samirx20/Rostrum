"""How a wash dries: pigment that gathers at the wet edge (`edge_darken`) and settles in the paper's tooth
(`granulation`). Both are laid once per stroke, after its dabs, from the stroke's own coverage: one more pass of the
stroke's colour in the stroke's mode, so the numpy dabs and the native stamper share it (the same pixels) and a
replay lays it the same. A stroke laid in pieces (the live ink) lays it at its last piece: the wash dries when the
pen lifts.

Edge: the coverage minus its own blur (a box `edge_px` wide each way) is what lies just inside the stroke's rim; that
much more paint goes there. Granulation: where the paper's grain is low (its valleys) more paint goes, scaled by the
coverage. Each does nothing at 0.
"""
from __future__ import annotations

import numpy as np

from .marks import apply_paint

KEYS = ("edge_darken", "granulation")                # stroke settings, 0 = off
EDGE_SHARE = 0.18        # the darkened rim is about this share of the brush size wide ...
EDGE_MAX = 24            # ... at most this many px
SETTLE = 0.62            # the grain below which pigment settles (the paper's valleys; grain is 0..1, about 0.5 mid)


def wants(p) -> bool:
    return p["edge_darken"] > 0 or p["granulation"] > 0


def edge_px(size: float) -> int:
    return int(min(EDGE_MAX, max(1, round(size * EDGE_SHARE))))


def _blur(a: np.ndarray, r: int) -> np.ndarray:
    """Box blur, zero outside, as shifted sums in a fixed order: each pixel's sum is the same wherever the window
    around it starts (a stroke in pieces and a stroke at once agree)."""
    for axis in (0, 1):
        pad = [(0, 0), (0, 0)]
        pad[axis] = (r, r)
        b = np.pad(a, pad)
        n = a.shape[axis]
        acc = np.zeros_like(a)
        for k in range(2 * r + 1):
            acc += b[k:k + n] if axis == 0 else b[:, k:k + n]
        a = acc / np.float32(2 * r + 1)
    return a


def window(shape, bbox, r):
    """The stroke's bbox grown by the rim's reach, inside the layer."""
    H, W = shape
    x0, y0, x1, y1 = bbox
    return max(0, x0 - r), max(0, y0 - r), min(W, x1 + r), min(H, y1 + r)


def dry(layer, cov_full_or_win, win, color, mode, size, p, grain) -> None:
    """Lay the wash's dried edge and granulation on `layer` in place. `cov_full_or_win`: the stroke's coverage over
    `win` (x0, y0, x1, y1, layer px); `grain`: the paper's grain HxW (needed when granulation > 0)."""
    x0, y0, x1, y1 = win
    a = np.asarray(cov_full_or_win, np.float32)
    extra = np.zeros_like(a)
    if p["edge_darken"] > 0:
        e = np.clip(a - _blur(a, edge_px(size)), 0, 1)
        extra += np.float32(2 * p["edge_darken"]) * e
    if p["granulation"] > 0:
        g = np.clip((SETTLE - grain[y0:y1, x0:x1]) / SETTLE * 2, 0, 1)
        extra += np.float32(p["granulation"]) * a * g
    extra = np.minimum(extra, 1)
    if not extra.any():
        return
    apply_paint(layer[y0:y1, x0:x1], np.zeros_like(extra), extra, np.asarray(color, np.float32), mode)


def after(layer, got, color, size, p, paper) -> None:
    """A whole stroke's dried wash, from its Coverage `got` (None: nothing laid)."""
    if got is None or not wants(p):
        return
    r = edge_px(size)
    win = window(layer.shape[:2], got.bbox, r)
    a = np.zeros((win[3] - win[1], win[2] - win[0]), np.float32)
    bx0, by0, bx1, by1 = got.bbox
    a[by0 - win[1]:by1 - win[1], bx0 - win[0]:bx1 - win[0]] = got.a
    dry(layer, a, win, color, p["mode"], size, p, paper.fields()[0] if p["granulation"] > 0 else None)


def after_pieces(layer, cov, color, size, p, paper) -> None:
    """A stroke laid in pieces, at its last piece: `cov` is its whole coverage (HxW)."""
    if cov is None or not wants(p):
        return
    rows, cols = np.flatnonzero(cov.any(axis=1)), np.flatnonzero(cov.any(axis=0))
    if not len(rows):
        return
    r = edge_px(size)
    win = window(layer.shape[:2], (int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1), r)
    dry(layer, cov[win[1]:win[3], win[0]:win[2]], win, color, p["mode"], size, p,
        paper.fields()[0] if p["granulation"] > 0 else None)
