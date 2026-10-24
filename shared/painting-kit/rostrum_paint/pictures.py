"""The built-in tip and paper pictures: made here, by code, from a fixed seed (our own work, under the project's MIT
licence; no downloaded image). A tip picture is the tip's shape inside the dab (it turns with the tip); a paper is a
tile repeated over the canvas, so its grain stays put under the stroke and moves only with the layer.

Every picture is a float32 0..1 array, made once and kept. "none" / "tooth" are the engine's first ones: a stroke
that names neither paints exactly as before. A name that is not built in is one of the project's own pictures, an
item id (library.py).
"""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

TEXTURES = ("none", "sponge", "speckle", "streaks", "ragged", "charcoal")
PAPERS = ("tooth", "canvas", "cold press", "laid", "rough")
TIP_N, PAPER_N = 128, 256


def _ss(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def _norm(g):
    g = g - g.min()
    return g / max(float(g.max()), 1e-9)


def _periodic(n, cell, rng):
    """Smooth noise 0..1 with features about `cell` px wide that tiles seamlessly (white noise blurred in frequency)."""
    k = np.fft.fftfreq(n)[:, None] ** 2 + np.fft.fftfreq(n)[None, :] ** 2
    f = np.fft.fft2(rng.standard_normal((n, n))) * np.exp(-2 * math.pi ** 2 * (cell / 2) ** 2 * k)
    return _norm(np.real(np.fft.ifft2(f)))


def _tip(name):
    rng, n = np.random.default_rng(["sponge", "speckle", "streaks", "ragged", "charcoal"].index(name) + 11), TIP_N
    v, u = np.mgrid[-1:1:n * 1j, -1:1:n * 1j]
    r = np.hypot(u, v)
    if name == "sponge":            # open pores, wider apart toward the rim
        return _ss((_periodic(n, 7, rng) - 0.3 - 0.25 * r) / 0.18)
    if name == "speckle":           # loose dots, like a spray or a stipple
        out = np.zeros((n, n))
        for x, y, s in zip(rng.uniform(-1, 1, 160), rng.uniform(-1, 1, 160), rng.uniform(0.02, 0.06, 160)):
            out = np.maximum(out, _ss((s - np.hypot(u - x, v - y)) / 0.015))
        return out
    if name == "streaks":           # lines along the stroke, the dry-brush drag
        row = _ss((_periodic(n, 3, rng)[0] - 0.25) / 0.4) * (0.6 + 0.4 * _periodic(n, 12, rng)[0])
        return np.repeat(row[:, None], n, 1)
    if name == "ragged":            # a torn edge round a solid middle: big bites, a fine fibrous fringe, flecks off it
        at = ((np.arctan2(v, u) + math.pi) / (2 * math.pi) * (n - 1)).astype(int)
        edge = (0.62 + 0.2 * _periodic(n, 14, rng)[0][at] + 0.14 * _periodic(n, 2, rng)[1][at] ** 2
                + 0.06 * _periodic(n, 1, rng))
        fleck = _ss((_periodic(n, 2, rng) - 0.62) / 0.06) * _ss((r - edge + 0.12) / 0.06) * _ss((0.98 - r) / 0.05)
        return np.maximum(_ss((edge - r) / 0.025), fleck)
    return _ss((0.45 * _periodic(n, 1.5, rng) + 0.55 * _periodic(n, 5, rng) - 0.3) / 0.45)   # charcoal


def _paper(name):
    rng, n = np.random.default_rng(PAPERS.index(name) + 21), PAPER_N
    y, x = np.mgrid[0:n, 0:n]
    if name == "canvas":            # a plain weave of fine threads: each crossing a raised grain, gaps between threads
        p = 4
        fx, fy = (x % p + 0.5) / p, (y % p + 0.5) / p
        over = ((x // p + y // p) % 2).astype(bool)
        row, col = rng.uniform(0.7, 1, n // p)[y // p], rng.uniform(0.7, 1, n // p)[x // p]   # uneven yarn
        across, along = np.sin(math.pi * fy) ** 0.6, np.sin(math.pi * fx) ** 0.6
        bump = np.where(over, row * across * (0.5 + 0.5 * along), col * along * (0.5 + 0.5 * across))
        return _norm(0.75 * bump + 0.15 * _periodic(n, 1, rng) + 0.1 * _periodic(n, 24, rng))
    if name == "cold press":        # watercolour paper: soft round hills and dimples
        return _norm(_periodic(n, 6, rng) ** 1.4 + 0.6 * _periodic(n, 18, rng) + 0.2 * _periodic(n, 1.5, rng))
    if name == "laid":              # fine laid lines, chain lines across them
        lines = 0.5 + 0.5 * np.cos(2 * math.pi * y / 4)
        chain = _ss((np.abs((x % 32) - 16) - 14.5) / 1.5)
        return _norm(0.6 * lines * (1 - 0.5 * chain) + 0.4 * _periodic(n, 3, rng))
    return _norm(_periodic(n, 2, rng) + 0.8 * _periodic(n, 9, rng))   # rough: coarse, deep tooth


def tip(name: str):
    """The tip picture `name` (TIP_N square, u along the stroke, rows across it), or None for "none"."""
    if name in TEXTURES:
        return _built_tip(name)
    from .library import picture
    return picture(name, "tip")


def paper_tile(name: str):
    if name == "tooth":
        raise ValueError("the tooth paper is the engine's own, not a picture")
    if name in PAPERS:
        return _built_paper(name)
    from .library import picture
    return picture(name, "paper")


@lru_cache(maxsize=None)
def _built_tip(name):
    return None if name == "none" else np.ascontiguousarray(_tip(name), np.float32)


@lru_cache(maxsize=None)
def _built_paper(name):
    return np.ascontiguousarray(_paper(name), np.float32)


def tiled(tile, h, w, scale, origin=(0, 0)):
    """The tile repeated over an h x w canvas at `scale` (bilinear, wrapping, so the seams never show), from canvas px
    `origin` (where the paper starts: marks.Paper)."""
    n = tile.shape[0]
    fy, fx = ((np.arange(h) - origin[1]) / scale) % n, ((np.arange(w) - origin[0]) / scale) % n
    y0, x0 = fy.astype(int), fx.astype(int)
    gy, gx = (fy - y0)[:, None], (fx - x0)[None, :]
    y1, x1 = (y0 + 1) % n, (x0 + 1) % n
    t = lambda a, b: tile[np.ix_(a, b)]  # noqa: E731
    out = (t(y0, x0) * (1 - gx) + t(y0, x1) * gx) * (1 - gy) + (t(y1, x0) * (1 - gx) + t(y1, x1) * gx) * gy
    return np.ascontiguousarray(out, np.float32)
