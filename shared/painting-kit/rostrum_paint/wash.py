"""How a wash dries: pigment that gathers at the wet edge (`edge_darken`), settles in the paper's tooth
(`granulation`), pools unevenly inside the wash (`pooling`) and creeps past the edge into damp paper (`bloom`). All are
laid once per stroke, after its dabs, from the stroke's own coverage, so the numpy dabs and the native stamper share
them (the same pixels) and a replay lays them the same. A stroke laid in pieces (the live ink) lays them at its last
piece: the wash dries when the pen lifts.

Gathered pigment is *more* pigment, so it is deeper than the stroke's colour, not just more of it: in normal mode it
goes on as the colour glazed over itself (multiplied by itself), the way a puddle of the same paint dries darker; in
multiply mode another pass of the colour; in the light modes (screen, add) more of the light.

Edge: the coverage minus its own blur (a box `edge_px` wide each way) is what lies just inside the stroke's rim; the rim
is strong in some places and faint in others along its length (smooth noise about a brush size across), as a drying edge
is. Granulation: pigment settles in the paper's valleys (its grain) and clumps (a few px across), scaled by the
coverage. Pooling: puddles of deeper colour inside the wash, soft blotches at three sizes from about two brush sizes
across down to a quarter, so a flat wash is never one even colour. Bloom (a backrun): the wet paint runs out past the
edge to a front whose distance wanders at three sizes (a cauliflower edge, soft but defined), pale inside, with the
pushed pigment drying darker along the front. The noise is fixed to the paper (marks.Paper.noise), never to the stroke's
box. Each does nothing at 0.
"""
from __future__ import annotations

import numpy as np

from .marks import _ss, apply_paint

KEYS = ("edge_darken", "granulation", "bloom", "pooling")     # stroke settings, 0 = off
EDGE_SHARE = 0.18        # the darkened rim is about this share of the brush size wide ...
EDGE_MAX = 24            # ... at most this many px
SETTLE = 0.62            # the grain below which pigment settles (the paper's valleys; grain is 0..1, about 0.5 mid)
CLUMP = 5.0              # granulation clumps about this many px across (times the paper scale)
BLOOM_SHARE = 0.6        # a full bloom runs out about this share of the brush size past the edge ...
BLOOM_MAX = 90           # ... at most this many px
SALT = 40                # the noise salts this module uses (40..49), apart from the paper's own


def wants(p) -> bool:
    return any(p.get(k, 0) > 0 for k in KEYS)


def edge_px(size: float) -> int:
    return int(min(EDGE_MAX, max(1, round(size * EDGE_SHARE))))


def bloom_px(size: float, bloom: float) -> int:
    return int(min(BLOOM_MAX, max(2, round(size * BLOOM_SHARE * bloom)))) if bloom > 0 else 0


def reach(size: float, p) -> int:
    """How far past the stroke's laid paint the drying reaches, in px."""
    return max(edge_px(size), bloom_px(size, p.get("bloom", 0.0)))


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


def _wide(a: np.ndarray, r: int, at=(0, 0)) -> np.ndarray:
    """A soft blur about `r` px each way (two box passes, a tent), worked out on a coarser grid when r is big: a bloom
    spreads tens of px and the full-size box sums cost a second on a canvas-wide wash. The grid is fixed to the canvas
    (`at`: the window's top-left in canvas px), so a stroke dried whole and in pieces agree. Zero outside."""
    f = max(1, r // 8)
    if f == 1:
        h = max(1, r // 2)
        return _blur(_blur(a, h), h)
    oy, ox = at[1] % f, at[0] % f
    H0, W0 = a.shape
    H, W = H0 + oy, W0 + ox
    Hc, Wc = -(-H // f), -(-W // f)
    pad = np.zeros((Hc * f, Wc * f), np.float32)
    pad[oy:H, ox:W] = a
    small = pad.reshape(Hc, f, Wc, f).mean(axis=(1, 3))
    h = max(1, round(r / f / 2))
    return _upsample(_blur(_blur(small, h), h), f, H, W, 0.5)[oy:, ox:]


def _upsample(small, f, H, W, at):
    """A coarse grid (one sample per f px, sample k at px (k + at) * f) back up to H x W, bilinear."""
    Hc, Wc = small.shape
    ys = (np.arange(H, dtype=np.float32) + 0.5) / f - at
    xs = (np.arange(W, dtype=np.float32) + 0.5) / f - at
    y0 = np.clip(np.floor(ys).astype(int), 0, Hc - 1); y1 = np.minimum(y0 + 1, Hc - 1)
    x0 = np.clip(np.floor(xs).astype(int), 0, Wc - 1); x1 = np.minimum(x0 + 1, Wc - 1)
    wy = np.clip(ys - y0, 0, 1)[:, None]; wx = np.clip(xs - x0, 0, 1)[None, :]
    rows = small[y0] * (1 - wy) + small[y1] * wy                   # rows first, then across: two gathers, not four
    return (rows[:, x0] * (1 - wx) + rows[:, x1] * wx).astype(np.float32)


def _fbm(paper, win, cell, salt):
    """Three octaves of the paper's smooth noise (cell, cell / 2.6, cell / 6.5), 0..1 about 0.5 mid. Worked out on a
    grid about a tenth of the finest octave apart (fixed to the canvas) and brought back up: noise this smooth loses
    nothing, and at full size a canvas-wide wash's pooling cost ~90 ms a stroke."""
    octaves = ((1.0, 0.55), (1 / 2.6, 0.3), (1 / 6.5, 0.15))
    f = 1 if paper.wrap else max(1, int(cell / 6.5 / 10))
    x0, y0, x1, y1 = win
    if f < 2:
        return sum(np.float32(w) * paper.noise(x0, y0, x1, y1, max(1.5, cell * s), SALT + salt + k).astype(np.float32)
                   for k, (s, w) in enumerate(octaves))
    from .marks import _noise
    cx0, cy0 = (x0 // f) * f, (y0 // f) * f
    wc, hc = -(-(x1 - cx0) // f) + 1, -(-(y1 - cy0) // f) + 1
    at = ((paper.origin[0] - cx0) / f, (paper.origin[1] - cy0) / f)
    small = sum(np.float32(w) * _noise(hc, wc, cell * s / f, paper.seed, SALT + salt + k, at).astype(np.float32)
                for k, (s, w) in enumerate(octaves))
    return _upsample(small, f, y1 - cy0, x1 - cx0, 0.5)[y0 - cy0:, x0 - cx0:]


def _deep(color, mode):
    """The colour gathered pigment dries to (see the module's note)."""
    c = np.asarray(color, np.float32)
    return (c * c, "normal") if mode == "normal" else (c, mode)


def dry(layer, cov_full_or_win, win, color, mode, size, p, paper) -> None:
    """Lay the wash's dried edge, granulation, pooling and bloom on `layer` in place. `cov_full_or_win`: the stroke's
    coverage over `win` (x0, y0, x1, y1, layer px); `paper`: the canvas's marks.Paper (its grain and noise)."""
    x0, y0, x1, y1 = win
    a = np.asarray(cov_full_or_win, np.float32)
    deep = np.zeros_like(a)          # gathered pigment: the deeper colour
    light = np.zeros_like(a)         # the stroke's own colour, past its edge (a bloom's pale body)
    if p["edge_darken"] > 0:
        thin = np.clip(a - _blur(a, max(1, round(size * 0.04))), 0, 1)        # the hard line the edge dries to
        e = 1.6 * thin + 0.7 * np.clip(a - _blur(a, edge_px(size)), 0, 1)     # and the darker band inside it
        along = np.clip(0.25 + 1.3 * (_fbm(paper, win, size * 1.2, 0) - 0.25), 0.15, 1.25)
        deep += np.float32(1.6 * p["edge_darken"]) * e * along
    if p["granulation"] > 0:
        G = paper.fields()[0][y0:y1, x0:x1]
        clump = paper.noise(x0, y0, x1, y1, CLUMP * paper.size / 3.0, SALT + 9)
        g = np.clip((SETTLE - G) / SETTLE * 2, 0, 1) * _ss((clump - 0.3) / 0.5)
        deep += np.float32(0.45 * p["granulation"]) * a * g
    if p.get("pooling", 0) > 0:
        n = _fbm(paper, win, max(8.0, size * 2.0), 3)
        deep += np.float32(0.75 * p["pooling"]) * a * _ss((n - 0.42) / 0.3)
    if p.get("bloom", 0) > 0:
        r = bloom_px(size, p["bloom"])
        spread = np.clip(_wide(a, r, (x0, y0)) * np.float32(2.0), 0, 1)         # 1 at the edge and in, falling to 0 r px out
        n = _fbm(paper, win, max(4.0, r * 2.2), 6)
        front = np.clip(0.05 + 1.1 * (1 - n) - 0.2, 0.04, 0.95)       # where the run stops: nearer or farther, by the noise
        wet = _ss((spread - front) / 0.08) * (1 - a)                   # the bloom past the edge: soft but defined
        rim = np.clip(wet - _blur(wet, max(1, r // 7)), 0, 1)          # the pushed pigment, dried along the front ...
        strong = _ss((_fbm(paper, win, max(4.0, r * 1.5), 7) - 0.3) / 0.4)   # ... heavy in places, gone in others
        amt = np.float32(min(1.0, p["bloom"]))
        light += amt * np.float32(0.45) * wet * (0.6 + 0.4 * n)
        deep += amt * np.float32(1.8) * rim * strong
    for extra, col, m in ((light, np.asarray(color, np.float32), mode), (deep, *_deep(color, mode))):
        extra = np.minimum(extra, 1)
        if extra.any():
            apply_paint(layer[y0:y1, x0:x1], np.zeros_like(extra), extra, col, m)


def after(layer, got, color, size, p, paper) -> None:
    """A whole stroke's dried wash, from its Coverage `got` (None: nothing laid)."""
    if got is None or not wants(p):
        return
    win = window(layer.shape[:2], got.bbox, reach(size, p))
    a = np.zeros((win[3] - win[1], win[2] - win[0]), np.float32)
    bx0, by0, bx1, by1 = got.bbox
    a[by0 - win[1]:by1 - win[1], bx0 - win[0]:bx1 - win[0]] = got.a
    dry(layer, a, win, color, p["mode"], size, p, paper)


def after_pieces(layer, cov, color, size, p, paper) -> None:
    """A stroke laid in pieces, at its last piece: `cov` is its whole coverage (HxW)."""
    if cov is None or not wants(p):
        return
    rows, cols = np.flatnonzero(cov.any(axis=1)), np.flatnonzero(cov.any(axis=0))
    if not len(rows):
        return
    win = window(layer.shape[:2], (int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1), reach(size, p))
    dry(layer, cov[win[1]:win[3], win[0]:win[2]], win, color, p["mode"], size, p, paper)


def window(shape, bbox, r):
    """The stroke's bbox grown by the rim's reach, inside the layer."""
    H, W = shape
    x0, y0, x1, y1 = bbox
    return max(0, x0 - r), max(0, y0 - r), min(W, x1 + r), min(H, y1 + r)
