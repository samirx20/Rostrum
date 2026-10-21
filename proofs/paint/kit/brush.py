"""Brush engine for the P-PAINT kit: stamps one stroke into one RGBA layer.

Started from Team Hem's `proofs/3d-painterly/paint/brush.py` (same tips, same look), refactored
for layers. A layer is HxWx4 float32: sRGB-encoded colour 0..1, **premultiplied by alpha**
(rgb <= a). `stamp_stroke` changes the layer in place and returns the stroke's `Coverage`
(the most alpha any stamp laid on each pixel, before wet / mode, inside its bbox), so the
document can track which stroke last touched each pixel. Same inputs + seed = same pixels.
"""
import colorsys, math
from typing import NamedTuple
import numpy as np
from PIL import Image

TIPS = ("round", "bristle", "chalk", "flat", "block", "line")
MODES = ("normal", "multiply", "erase")
K = 64  # samples across the tip for per-bristle profiles (upsampled for wide tips)
ALONG = {"round": 1.0, "chalk": 1.0, "line": 1.0, "bristle": 0.4, "flat": 0.3, "block": 0.5}
PARAMS = dict(opacity=1.0, hardness=0.5, spacing=0.1, jitter=0.0, seed=0, angle=None, wet=0.0,
              sample_all=False, grain=0.0, mode="normal", color_jitter=0.04, hue_jitter=0.0,
              size_pressure=0.8, opacity_pressure=0.3)


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
    """Paper / canvas tooth shared by every stroke of a document (lazy, deterministic)."""
    def __init__(self, h, w, seed=0, size=3.0):
        self.h, self.w, self.seed, self.size, self._g = h, w, seed, size, None

    def fields(self):
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


def apply_paint(region, inc, col, mode):
    """The one place paint meets a layer. region: hxwx4 premultiplied view; inc: hxw 0..1;
    col: straight sRGB (3,) or hxwx3. normal = paint over, multiply = glaze, erase = remove."""
    inc = inc[..., None]
    if mode == "normal":
        region[..., :3] += inc * (col - region[..., :3])
        region[..., 3:] += inc * (1 - region[..., 3:])
    elif mode == "multiply":
        region[..., :3] *= 1 - inc * (1 - col)
    elif mode == "erase":
        region *= 1 - inc
    else:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")


def check(brush, params):
    bad = set(params) - set(PARAMS)
    if bad:
        raise ValueError(f"unknown brush settings {sorted(bad)}; known: {sorted(PARAMS)}")
    if brush not in TIPS:
        raise ValueError(f"brush must be one of {TIPS}, got {brush!r}")
    if params.get("mode", "normal") not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {params['mode']!r}")


def stamp_stroke(layer, points, color, size, brush="round", *, mask=None, under=None, paper=None, **params):
    """Paint one stroke into `layer` (HxWx4 premultiplied float32, changed in place).

    points: (x, y[, pressure[, tilt]]) in layer pixels. mask: HxW 0..1 or None. under: HxWx3
    composite below this layer, needed for `sample_all=True`. Returns Coverage (or None if the
    stroke is entirely off the layer)."""
    check(brush, params)
    p = {**PARAMS, **params}
    wet, cj, sp, tip = float(p["wet"]), p["color_jitter"], p["size_pressure"], brush
    if p["sample_all"] and under is None:
        raise ValueError("sample_all=True needs the composite below the layer (under=...)")
    H, W = layer.shape[:2]
    rng = np.random.default_rng(p["seed"])
    pts = np.array([(q[0], q[1], q[2] if len(q) > 2 else 1.0) for q in points], float)
    if not len(pts):
        raise ValueError("a stroke needs at least one point")
    # resample the path: one stamp every spacing * (local tip length) pixels
    seg = np.hypot(*np.diff(pts[:, :2], axis=0).T) if len(pts) > 1 else np.zeros(0)
    L = np.concatenate([[0], np.cumsum(seg)])
    step = max(0.3 if tip == "line" else 0.5, p["spacing"] * size * ALONG[tip] * (0.6 if wet > 0 else 2))
    t = [0.0]
    while t[-1] < L[-1]:
        pr = np.interp(t[-1], L, pts[:, 2])
        t.append(t[-1] + max(0.3, step * (1 - sp * (1 - pr))))
    t = np.minimum(np.array(t), L[-1])
    X, Y, Pr = (np.interp(t, L, pts[:, k]) if L[-1] > 0 else pts[:1, k] for k in range(3))
    S = t / L[-1] if L[-1] > 0 else np.zeros(1)
    n = len(t)
    th = (np.arctan2(np.gradient(Y), np.gradient(X)) if n > 1 else np.zeros(1)) if p["angle"] is None \
        else np.full(n, math.radians(p["angle"]))
    X = X + rng.normal(0, p["jitter"] * size, n)
    Y = Y + rng.normal(0, p["jitter"] * size, n)
    R = (size / 2) * (1 - sp * (1 - Pr))
    A = p["opacity"] * (1 - p["opacity_pressure"] * (1 - Pr))
    A, R = A * np.minimum(1, R / 0.5), np.maximum(R, 0.5)  # thinner than a pixel fades, never breaks
    Kr = max(K, int(2 * R.max()) + 1)
    # per-stroke tip profile across the brush: bristles, ragged start/end, colour streaks
    v = np.linspace(-1, 1, Kr)
    if tip == "bristle":
        nb = int(np.clip(size / 2, 10, 60))
        prof = np.zeros(Kr)
        for c, w_, s_ in zip(rng.uniform(-.95, .95, nb), rng.uniform(.04, .1, nb), rng.uniform(.4, 1, nb)):
            prof = np.maximum(prof, s_ * np.exp(-((v - c) / w_) ** 2))
        prof = 0.7 * prof + 0.3 * _up(_noise1(K, 8, rng), Kr)
    elif tip == "flat":
        prof = 0.75 + 0.25 * _up(_noise1(K, 4, rng), Kr)
    elif tip == "block":
        prof = 0.88 + 0.12 * _up(_noise1(K, 6, rng), Kr)
    else:
        prof = np.ones(Kr)
    rag = {"bristle": (0.12, 0.35, 1.5), "flat": (0.08, 0.2, 5), "block": (0.25, 0.25, 5)}.get(tip, (0, 0, 8))
    start = rag[0] * _up(_noise1(K, rag[2], rng), Kr)
    end = rag[1] * _up(_noise1(K, rag[2], rng), Kr)
    streak = (_up(_noise1(K, 2 if tip == "bristle" else 6, rng), Kr) - 0.5) * 2
    hn, sn, vn = ((_noise1(n, max(2, size / step), rng) - 0.5) * 2 for _ in range(3))
    wv = 1 - 0.05 * _noise1(n, max(2, size / step), rng) if tip == "block" else None
    h0, s0, v0 = colorsys.rgb_to_hsv(*np.clip(color, 0, 1))
    cols = np.array([colorsys.hsv_to_rgb((h0 + p["hue_jitter"] / 360 * a) % 1, np.clip(s0 * (1 + cj * b), 0, 1),
                                         np.clip(v0 * (1 + cj * c), 0, 1)) for a, b, c in zip(hn, sn, vn)], np.float32)
    G, F = (paper or Paper(H, W)).fields() if p["grain"] > 0 or tip == "chalk" else (None, None)
    soft = max(1 - p["hardness"], 0.03)
    bx0 = int(max(0, np.floor((X - R).min()) - 1)); bx1 = int(min(W, np.ceil((X + R).max()) + 2))
    by0 = int(max(0, np.floor((Y - R).min()) - 1)); by1 = int(min(H, np.ceil((Y + R).max()) + 2))
    if bx1 <= bx0 or by1 <= by0:
        return None
    cov = np.zeros((by1 - by0, bx1 - bx0), np.float32)  # max coverage so far in this stroke
    D, res = int(2 * R.max()) + 6, None
    for i in range(n):
        r = R[i]
        x0, x1 = max(bx0, int(X[i] - r) - 1), min(bx1, int(X[i] + r) + 2)
        y0, y1 = max(by0, int(Y[i] - r) - 1), min(by1, int(Y[i] + r) + 2)
        if x1 <= x0 or y1 <= y0:
            continue
        dx = (np.arange(x0, x1, dtype=np.float32) - np.float32(X[i]))[None, :]
        dy = (np.arange(y0, y1, dtype=np.float32) - np.float32(Y[i]))[:, None]
        c, s = math.cos(th[i]), math.sin(th[i])
        u, vv = (dx * c + dy * s) / r, (dy * c - dx * s) / r
        idx = ((np.clip(vv, -1, 1) + 1) * (Kr - 1) / 2).astype(np.int32)
        if tip in ("round", "chalk"):
            a = _ss((r - np.sqrt(dx * dx + dy * dy)) / max(1.0, soft * r))
            if tip == "chalk":
                a = _ss((a - 0.85 * (1 - F[y0:y1, x0:x1])) / 0.3)
        elif tip == "line":
            a = np.clip(r + 0.5 - np.sqrt(dx * dx + dy * dy), 0, 1)
        elif tip == "bristle":
            a = _ss((1 - (u / ALONG[tip]) ** 2 - vv * vv) / soft)
        elif tip == "flat":
            a = _ss((1 - np.abs(u) / ALONG[tip]) / soft) * _ss((1 - np.abs(vv)) / (soft * 0.3))
        else:  # block: crisp rectangle, square ends with slight raggedness
            ew = max(1.0, soft * r * 0.15)
            al = t[i] + u * r  # distance along the stroke
            a = (_ss((wv[i] - np.abs(vv)) * r / ew) * _ss((ALONG[tip] - np.abs(u)) * r / ew)
                 * _ss((al + ALONG[tip] * R[0] - start[idx] * R[0]) / ew)
                 * _ss((L[-1] + ALONG[tip] * R[-1] - end[idx] * R[-1] - al) / ew) * prof[idx])
        if tip in ("bristle", "flat"):
            a = a * (prof * _ss((S[i] - start) / 0.06) * _ss((1 - end - S[i]) / 0.06))[idx]
        a = a * A[i]
        if G is not None and p["grain"] > 0:
            tg = p["grain"] * (1 - G[y0:y1, x0:x1])
            a = np.clip((a - tg) / (1.001 - tg), 0, 1)
        if mask is not None:
            a = a * mask[y0:y1, x0:x1]
        cv = cov[y0 - by0:y1 - by0, x0 - bx0:x1 - bx0]
        c1 = np.maximum(cv, a)
        inc = (c1 - cv) / (1.0001 - cv)
        cv[...] = c1
        col = cols[i] * (1 + cj * 0.6 * streak[idx])[..., None]
        region = layer[y0:y1, x0:x1]
        if wet > 0:  # smudge: the brush carries a reservoir of the paint it passed over
            oy, ox = int(round(Y[i])) - D // 2, int(round(X[i])) - D // 2
            win = (slice(y0 - oy, y1 - oy), slice(x0 - ox, x1 - ox))
            if 0 <= oy and oy + D <= H and 0 <= ox and ox + D <= W:
                ix = (slice(oy, oy + D), slice(ox, ox + D))
            else:  # near the edge: clamp, the canvas edge repeats
                ix = np.ix_(np.clip(np.arange(oy, oy + D), 0, H - 1), np.clip(np.arange(ox, ox + D), 0, W - 1))
            pick = layer[ix].copy()
            if p["sample_all"]:  # what the eye sees: this layer over the composite below
                pick[..., :3] += (1 - pick[..., 3:]) * under[ix]
                pick[..., 3] = 1
            if res is None:
                res = pick
            lt = math.hypot(X[i] - X[i - 1], Y[i] - Y[i - 1]) / (2 * r * ALONG[tip]) if i else 0
            region += (a * (1 - (1 - 0.97 * wet) ** max(lt, 0.05)))[..., None] * (res[win] - region)
            res += (1 - (0.6 * wet) ** max(lt, 0.05)) * (pick - res)
        apply_paint(region, inc * (1 - wet), col, p["mode"])
    return Coverage(cov, (bx0, by0, bx1, by1))


def hatch_paths(mask, size, angle=0.0, gap=0.7, length=4.0, bend=0.15, pressure=(0.5, 1.0, 0.3), seed=0):
    """Hem's block-in: (points, seed) for many strokes running at `angle` degrees across a mask."""
    rng = np.random.default_rng(seed)
    ys, xs = np.nonzero(mask > 0.5)
    if not len(xs):
        raise ValueError("fill_region: the mask is empty")
    H, W = mask.shape
    cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
    rad = math.hypot(xs.max() - xs.min(), ys.max() - ys.min()) / 2 + size
    d = np.array([math.cos(math.radians(angle)), math.sin(math.radians(angle))])
    nrm = np.array([-d[1], d[0]])
    out = []
    for off in np.arange(-rad, rad, gap * size):
        t = -rad - rng.uniform(0, length * size)
        while t < rad:
            ln = length * size * rng.uniform(0.7, 1.3)
            o = off + rng.normal(0, 0.15 * gap * size)
            p0, p2 = np.array([cx, cy]) + d * t + nrm * o, np.array([cx, cy]) + d * (t + ln) + nrm * o
            p1 = (p0 + p2) / 2 + nrm * ln * bend * rng.normal()
            mx, my = int(p1[0]), int(p1[1])
            if 0 <= mx < W and 0 <= my < H and mask[my, mx] > 0.5:
                out.append((curve(p0, p1, p2, n=12, pressure=pressure), int(rng.integers(1 << 30))))
            t += ln * rng.uniform(0.6, 0.9)
    return out
