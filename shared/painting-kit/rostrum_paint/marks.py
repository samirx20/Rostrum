"""The brush engine's small pieces: smooth steps, value noise, paper grain, curves, and `apply_paint`, the one
place paint meets a layer. Carried over from P-PAINT (`proofs/paint/kit/brush.py`, after Team Hem's P-3D-2 engine).
A layer is HxWx4 float32: sRGB-encoded colour 0..1, **premultiplied by alpha** (rgb <= a).
"""
import colorsys, math
from typing import NamedTuple
import numpy as np

TIPS = ("round", "bristle", "chalk", "flat", "block", "line")
MODES = ("normal", "multiply", "erase", "screen", "add", "overlay", "soft_light", "color")
UNDER = ("overlay", "soft_light", "color")   # the modes that read a copy of what was under the stroke
K = 64  # samples across the tip for per-bristle profiles (upsampled for wide tips)
ALONG = {"round": 1.0, "chalk": 1.0, "line": 1.0, "bristle": 0.4, "flat": 0.3, "block": 0.5}
PARAMS = dict(opacity=1.0, hardness=0.5, spacing=0.1, jitter=0.0, seed=0, angle=None, wet=0.0,
              sample_all=False, grain=0.0, mode="normal", color_jitter=0.04, hue_jitter=0.0,
              size_pressure=0.8, opacity_pressure=0.3, steady=0.0, tilt_angle=0.0, tilt_size=0.0,
              taper_start=0.0, taper_end=0.0, size_jitter=0.0, angle_jitter=0.0, even=False, texture="none", wrap=False)
EVEN = 0.13   # even soft edge: a dab every EVEN * sqrt(radius * edge width) px at most (ridges under ~1.5/255)


class Coverage(NamedTuple):
    a: np.ndarray        # float32 (y1-y0, x1-x0), 0..1
    bbox: tuple          # (x0, y0, x1, y1), x1/y1 exclusive


def _ss(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def _knots(seed, salt, ky, kx):
    """Value-noise knots 0..1 at whole lattice points (ky, kx): a hash of the point, so any part of the endless plane
    is the same wherever and however big the canvas around it is."""
    h = (kx * 0x27D4EB2D + ky * 0x165667B1 + seed * 0x9E3779B1 + salt * 0x85EBCA6B) & 0xFFFFFFFF
    for mul, shift in ((0x2C1B3C6D, 12), (0x297A2D39, 15)):
        h ^= h >> 15
        h = (h * mul) & 0xFFFFFFFF
        h ^= h >> shift
    return (h / 4294967296.0).astype(np.float32)


def _cubic(u):
    """Catmull-Rom weights (4, n) and the lattice cell of each sample of `u`."""
    i = np.floor(u).astype(np.int64)
    t = (u - i).astype(np.float32)
    t2, t3 = t * t, t * t * t
    return i, ((-t3 + 2 * t2 - t) / 2, (3 * t3 - 5 * t2 + 2) / 2, (-3 * t3 + 4 * t2 + t) / 2, (t3 - t2) / 2)


def _noise(h, w, cell, seed, salt, origin=(0, 0), wrap=False):
    """Smooth value noise 0..1 with features about `cell` px wide, over canvas px (0..w, 0..h) whose paper starts at
    `origin` (canvas px): the plane's (x - ox, y - oy). Fixed to the paper, not to the canvas's size. `wrap`: it
    repeats every w and h px (a seamless canvas, wrap.py): a whole number of features across, the knots round again."""
    nkx, nky = (max(1, round(w / cell)), max(1, round(h / cell))) if wrap else (0, 0)
    ix, wx = _cubic((np.arange(w) - origin[0]) / (w / nkx if wrap else cell))
    iy, wy = _cubic((np.arange(h) - origin[1]) / (h / nky if wrap else cell))
    kx0, ky0 = int(ix.min()) - 1, int(iy.min()) - 1
    nx, ny = int(ix.max()) - kx0 + 3, int(iy.max()) - ky0 + 3
    ky, kx = np.arange(ky0, ky0 + ny, dtype=np.int64), np.arange(kx0, kx0 + nx, dtype=np.int64)
    if wrap:
        ky, kx = ky % nky, kx % nkx
    g = _knots(seed, salt, ky[:, None], kx[None, :])
    rows = sum(g[:, ix - kx0 - 1 + j] * wx[j] for j in range(4))
    return sum(rows[iy - ky0 - 1 + j] * wy[j][:, None] for j in range(4)).clip(0, 1)


def _noise1(n, cell, rng):
    knots = rng.random(int(n / cell) + 2)
    return np.interp(np.linspace(0, len(knots) - 1, n), np.arange(len(knots)), knots)


def _up(p, n):
    """Resample a K-long tip profile to n samples (linear, so wide tips don't stair-step)."""
    return p if len(p) == n else np.interp(np.linspace(0, len(p) - 1, n), np.arange(len(p)), p)


class Paper:
    """Paper / canvas tooth shared by every stroke of a document (lazy, deterministic): the engine's own procedural
    tooth, or `picture` (a pictures.PAPERS name) tiled at `scale`. Either is fixed to the paper, which starts at canvas
    px `origin`: a drawing that grows (its strokes moved by the growth, the origin with them) keeps every grain where it
    was, and a canvas made bigger keeps the grain it had."""
    def __init__(self, h, w, seed=0, size=3.0, picture="tooth", scale=1.0, origin=(0, 0), wrap=False):
        self.h, self.w, self.seed, self.size, self._g = h, w, seed, size, None
        self.picture, self.scale, self.origin, self.wrap = picture, scale, tuple(origin), wrap

    def fields(self):
        """(grain, chalk fibre) HxW. On a seamless canvas (`wrap`) both repeat every w and h px, so the tooth meets
        itself across the joined edges, a hair bigger or smaller to fit a whole number of times. On a picture paper the
        chalk's fibre is the picture with fine loose fibres through it: chalk catching on the picture alone broke
        into the picture's own pattern, a dot grid on canvas."""
        if self._g is None and self.picture != "tooth":
            from .pictures import paper_tile, tiled
            g = tiled(paper_tile(self.picture), self.h, self.w, self.scale, self.origin, self.wrap)
            fibre = _noise(self.h, self.w, 1.5 * self.scale, self.seed, 2, self.origin, self.wrap)
            self._g = (g, np.ascontiguousarray(0.55 * g + 0.45 * fibre, np.float32))
        if self._g is None:
            s, o, h, w, r = self.size, self.origin, self.h, self.w, self.wrap
            g = 0.6 * _noise(h, w, s, self.seed, 0, o, r) + 0.4 * _noise(h, w, s * 4, self.seed, 1, o, r)
            self._g = (g, _noise(h, w, 1.5, self.seed, 2, o, r))
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


def _lum(c):
    return 0.3 * c[..., 0:1] + 0.59 * c[..., 1:2] + 0.11 * c[..., 2:3]


def blend_under(base, col, mode):
    """overlay / soft_light / color of straight `col` over `base` (premultiplied, what was under the stroke): the
    premultiplied result, alpha unchanged. W3C compositing formulas, all in f64 (stamp/src/paint.rs: the same steps)."""
    base = base.astype(np.float64)
    a = base[..., 3:]
    b = np.clip(np.divide(base[..., :3], a, out=np.zeros_like(base[..., :3]), where=a > 0), 0, 1)
    s = np.clip(np.asarray(col, np.float64), 0, 1)
    if mode == "overlay":
        out = np.where(b <= 0.5, 2 * b * s, 1 - 2 * (1 - b) * (1 - s))
    elif mode == "soft_light":
        d = np.where(b <= 0.25, ((16 * b - 12) * b + 4) * b, np.sqrt(b))
        out = np.where(s <= 0.5, b - (1 - 2 * s) * b * (1 - b), b + (2 * s - 1) * (d - b))
    else:                                         # color: the paint's hue and saturation, the lightness under it
        c = s + (_lum(b) - _lum(s))
        L, n, x = _lum(c), c.min(axis=-1, keepdims=True), c.max(axis=-1, keepdims=True)
        with np.errstate(divide="ignore", invalid="ignore"):
            c = np.where(n < 0, L + (c - L) * L / (L - n), c)
            out = np.where(x > 1, L + (c - L) * (1 - L) / (x - L), c)
    return out * a


def apply_paint(region, c0, c1, col, mode, k=1.0, base=None):
    """The one place paint meets a layer. region: hxwx4 premultiplied view; c0 -> c1: the stroke's coverage there
    before and after this dab (hxw 0..1, c1 >= c0); k: the share of it that is paint (1 - wetness); col: straight
    sRGB (3,) or hxwx3. normal = paint over, multiply = glaze, erase = remove, screen / add = light (glows and haze
    stack instead of replacing each other).

    A stroke is one mark, not a pile of dabs: each mode lays the step c0 -> c1 so that all of a stroke's dabs
    together equal laying its final coverage once (dabs overlap many times along a stroke, so a per-dab error shows
    as ridges at dab spacing). Strokes do stack: two light strokes give twice the light.

    overlay / soft_light / color blend the paint with `base`, a copy of what was under the stroke before it began
    (default: the region now, right for one-shot laying), and lay that like normal paint, alpha unchanged: dabs
    re-blending the stroke's own paint would stack."""
    inc = (k * (c1 - c0) / (1.0001 - c0))[..., None]          # the over-step: 1 - (1-c0)(1-inc) = c1
    lo, hi = (k * c0)[..., None], (k * c1)[..., None]
    if mode == "normal":
        region[..., :3] += inc * (col - region[..., :3])
        region[..., 3:] += inc * (1 - region[..., 3:])
    elif mode == "multiply":                                  # times 1 - c(1-col), once per stroke; where there is
        bare = 1 - region[..., 3:]                            # no paint yet (a new layer) it lays its colour, so a
        region[..., :3] = region[..., :3] * ((1 - hi * (1 - col)) / (1 - lo * (1 - col))) + inc * col * bare  # glaze shows
        region[..., 3:] += inc * bare
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
    elif mode in UNDER:
        t = blend_under(region if base is None else base, col, mode)
        region[..., :3] += inc * (t - region[..., :3])
    else:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
