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
    if name == "canvas":            # a plain weave of uneven yarn: threads that wander, thicken and thin, crossings raised
        return _weave(n, rng)
    if name == "cold press":        # watercolour paper: soft round hills and dimples
        return _norm(_periodic(n, 6, rng) ** 1.4 + 0.6 * _periodic(n, 18, rng) + 0.2 * _periodic(n, 1.5, rng))
    if name == "laid":              # fine laid lines (each wavering and fading a little, as wires leave them), chain lines across
        lines = (0.5 + 0.5 * np.cos(2 * math.pi * (y + 1.2 * (_periodic(n, 16, rng) - 0.5)) / 4)) * (0.5 + 0.5 * _periodic(n, 8, rng))
        chain = _ss((np.abs((x % 32) - 16) - 14.5) / 1.5)
        return _norm(0.6 * lines * (1 - 0.5 * chain) + 0.4 * _periodic(n, 3, rng))
    return _norm(_periodic(n, 2, rng) + 0.8 * _periodic(n, 9, rng))   # rough: coarse, deep tooth


def _yarns(n, threads, rng):
    """Where each pixel lies across the yarns, 0..threads: yarns of uneven width (no two gaps alike), so the weave
    has no fixed pitch to read as a grid; whole yarns over the tile, so it still tiles seamlessly."""
    edges = np.concatenate([[0.0], np.cumsum(rng.uniform(0.6, 1.4, threads))])
    return np.interp(np.arange(n + 1), edges * n / edges[-1], np.arange(threads + 1.0))[:n]


def _weave(n, rng, threads=36):
    """Canvas: `threads` yarns each way over the tile (about 7 px apart), never a lattice at 100 %: yarns of uneven
    width that wander off their line (a smooth warp of a few px), thicken and thin along their length, rise where they
    pass over; fine fibres and a soft mottle lie over the whole."""
    y, x = np.mgrid[0:n, 0:n]
    wx, wy = 3.0 * (_periodic(n, 20, rng) - 0.5), 3.0 * (_periodic(n, 20, rng) - 0.5)     # the wander, in px
    across, down = _yarns(n, threads, rng), _yarns(n, threads, rng)
    u = np.interp((x + wx) % n, np.arange(n), across, period=n)
    v = np.interp((y + wy) % n, np.arange(n), down, period=n)
    i, j = np.floor(u).astype(int) % threads, np.floor(v).astype(int) % threads
    fu, fv = u - np.floor(u), v - np.floor(v)
    slub = 0.65 + 0.35 * _periodic(n, 4, rng)                           # thicker and thinner along each yarn
    col = _ss((rng.uniform(0.5, 0.95, threads)[i] * slub / 2 - np.abs(fu - 0.5)) / 0.22)
    row = _ss((rng.uniform(0.5, 0.95, threads)[j] * slub / 2 - np.abs(fv - 0.5)) / 0.22)
    over = ((i + j) % 2).astype(bool)
    rise_c, rise_r = np.sin(math.pi * fv) ** 0.7, np.sin(math.pi * fu) ** 0.7   # the yarn on top bulges mid-crossing
    weave = np.where(over, np.maximum(col * (0.5 + 0.5 * rise_c), 0.55 * row), np.maximum(row * (0.5 + 0.5 * rise_r), 0.55 * col))
    fibre, mottle = _periodic(n, 1.2, rng), _periodic(n, 10, rng)
    return _norm(0.24 * weave * (0.3 + 0.7 * mottle) + 0.46 * fibre + 0.3 * mottle)   # the weave fades in and out


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


def tiled(tile, h, w, scale, origin=(0, 0), wrap=False):
    """The tile repeated over an h x w canvas at `scale` (bilinear, wrapping, so the seams never show), from canvas px
    `origin` (where the paper starts: marks.Paper). `wrap`: a whole number of tiles across and down (the scale a hair
    off on each axis), so the paper itself repeats with a seamless canvas."""
    n = tile.shape[0]
    sx = sy = scale
    if wrap:
        sx, sy = w / max(1, round(w / (n * scale))) / n, h / max(1, round(h / (n * scale))) / n
    fy, fx = ((np.arange(h) - origin[1]) / sy) % n, ((np.arange(w) - origin[0]) / sx) % n
    y0, x0 = fy.astype(int), fx.astype(int)
    gy, gx = (fy - y0)[:, None], (fx - x0)[None, :]
    y1, x1 = (y0 + 1) % n, (x0 + 1) % n
    t = lambda a, b: tile[np.ix_(a, b)]  # noqa: E731
    out = (t(y0, x0) * (1 - gx) + t(y0, x1) * gx) * (1 - gy) + (t(y1, x0) * (1 - gx) + t(y1, x1) * gx) * gy
    return np.ascontiguousarray(out, np.float32)
