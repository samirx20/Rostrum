"""The brush engine's small pieces: smooth steps, value noise, paper grain, curves, and `apply_paint`, the one
place paint meets a layer. Carried over from P-PAINT (`proofs/paint/kit/brush.py`, after Team Hem's P-3D-2 engine).
A layer is HxWx4 float32: sRGB-encoded colour 0..1, **premultiplied by alpha** (rgb <= a).
"""
import colorsys, math
from typing import NamedTuple
import numpy as np
from PIL import Image

TIPS = ("round", "bristle", "chalk", "flat", "block", "line")
MODES = ("normal", "multiply", "erase", "screen", "add")
K = 64  # samples across the tip for per-bristle profiles (upsampled for wide tips)
ALONG = {"round": 1.0, "chalk": 1.0, "line": 1.0, "bristle": 0.4, "flat": 0.3, "block": 0.5}
PARAMS = dict(opacity=1.0, hardness=0.5, spacing=0.1, jitter=0.0, seed=0, angle=None, wet=0.0,
              sample_all=False, grain=0.0, mode="normal", color_jitter=0.04, hue_jitter=0.0,
              size_pressure=0.8, opacity_pressure=0.3, steady=0.0, tilt_angle=0.0, tilt_size=0.0,
              taper_start=0.0, taper_end=0.0, size_jitter=0.0, angle_jitter=0.0, even=False, texture="none")
EVEN = 0.13   # even soft edge: a dab every EVEN * sqrt(radius * edge width) px at most (ridges under ~1.5/255)


class Coverage(NamedTuple):
    a: np.ndarray        # float32 (y1-y0, x1-x0), 0..1
    bbox: tuple          # (x0, y0, x1, y1), x1/y1 exclusive


def _ss(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def _noise(h, w, cell, rng):
    """Smooth value noise 0..1 with features about `cell` pixels wide."""
    g = rng.random((int(h / cell) + 3, int(w / cell) + 3)).astype(np.float32)
    return np.asarray(Image.fromarray(g, "F").resize((w, h), Image.BICUBIC)).clip(0, 1)


def _noise1(n, cell, rng):
    knots = rng.random(int(n / cell) + 2)
    return np.interp(np.linspace(0, len(knots) - 1, n), np.arange(len(knots)), knots)


def _up(p, n):
    """Resample a K-long tip profile to n samples (linear, so wide tips don't stair-step)."""
    return p if len(p) == n else np.interp(np.linspace(0, len(p) - 1, n), np.arange(len(p)), p)


class Paper:
    """Paper / canvas tooth shared by every stroke of a document (lazy, deterministic): the engine's own procedural
    tooth, or `picture` (a pictures.PAPERS name) tiled over the canvas at `scale`. Either is fixed to the canvas."""
    def __init__(self, h, w, seed=0, size=3.0, picture="tooth", scale=1.0):
        self.h, self.w, self.seed, self.size, self._g = h, w, seed, size, None
        self.picture, self.scale = picture, scale

    def fields(self):
        if self._g is None and self.picture != "tooth":
            from .pictures import paper_tile, tiled
            g = tiled(paper_tile(self.picture), self.h, self.w, self.scale)
            self._g = (g, g)
        if self._g is None:
            rng, s = np.random.default_rng(self.seed), self.size
            g = 0.6 * _noise(self.h, self.w, s, rng) + 0.4 * _noise(self.h, self.w, s * 4, rng)
            self._g = (g, _noise(self.h, self.w, 1.5, rng))
        return self._g


def curve(*pts, n=32, pressure=(1.0, 1.0, 1.0)):
    """Smooth line through the given (x, y) points; pressure eases start -> mid -> end."""
    P = np.array([p[:2] for p in pts], float)
    if len(P) < 2:
        raise ValueError("curve needs at least two points")
    Q = np.vstack([P[0], P, P[-1]])
    segs = len(P) - 1
    t = np.linspace(0, segs, n)
    i = np.minimum(t.astype(int), segs - 1)
    f = (t - i)[:, None]
    p0, p1, p2, p3 = Q[i], Q[i + 1], Q[i + 2], Q[i + 3]
    xy = 0.5 * (2 * p1 + (p2 - p0) * f + (2 * p0 - 5 * p1 + 4 * p2 - p3) * f ** 2
                + (3 * p1 - p0 - 3 * p2 + p3) * f ** 3)
    u = np.linspace(0, 1, n)
    s, m, e = pressure
    pr = np.where(u < 0.5, s + (m - s) * _ss(u * 2), m + (e - m) * _ss(u * 2 - 1))
    return [(float(x), float(y), float(p)) for (x, y), p in zip(xy, pr)]


def apply_paint(region, c0, c1, col, mode, k=1.0):
    """The one place paint meets a layer. region: hxwx4 premultiplied view; c0 -> c1: the stroke's coverage there
    before and after this dab (hxw 0..1, c1 >= c0); k: the share of it that is paint (1 - wetness); col: straight
    sRGB (3,) or hxwx3. normal = paint over, multiply = glaze, erase = remove, screen / add = light (glows and haze
    stack instead of replacing each other).

    A stroke is one mark, not a pile of dabs: each mode lays the step c0 -> c1 so that all of a stroke's dabs
    together equal laying its final coverage once (dabs overlap many times along a stroke, so a per-dab error shows
    as ridges at dab spacing). Strokes do stack: two light strokes give twice the light."""
    inc = (k * (c1 - c0) / (1.0001 - c0))[..., None]          # the over-step: 1 - (1-c0)(1-inc) = c1
    lo, hi = (k * c0)[..., None], (k * c1)[..., None]
    if mode == "normal":
        region[..., :3] += inc * (col - region[..., :3])
        region[..., 3:] += inc * (1 - region[..., 3:])
    elif mode == "multiply":                                  # times 1 - c(1-col), once per stroke
        region[..., :3] *= (1 - hi * (1 - col)) / (1 - lo * (1 - col))
    elif mode == "erase":
        region *= 1 - inc
    elif mode in ("screen", "add"):
        rgb, a = region[..., :3], region[..., 3:]
        a += inc * (1 - a)
        if mode == "screen":                                  # screens c*col once per stroke; never passes 1
            s = (hi - lo) * col / (1 - lo * col)
            rgb[...] = rgb + s - rgb * s
        else:                                                 # adds c*col once per stroke; strokes sum. Light is
            rgb[...] = np.minimum(rgb + (hi - lo) * col, 1)   # never cut down to the alpha: the alpha grows to
            a[...] = np.maximum(a, rgb.max(axis=-1, keepdims=True))   # carry it (premultiplied rgb <= a)
    else:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
