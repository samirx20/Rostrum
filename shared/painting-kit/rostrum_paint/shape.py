"""How a stroke's line and dabs are shaped before they are laid: steadiness (the line trails the pen), tilt (the pen's
lean turns and widens the tip), taper (thin start and end without pressure) and per-dab size / angle jitter.

All of it is brush settings stored with the stroke and applied in `brush.plan`, so a replay, the native stamper and
an export give the same pixels. Each piece does nothing at 0, so strokes made before it keep their pixels.

Points are [x, y, pressure, tilt x, tilt y]: the pen's lean in degrees each way (Qt's xTilt / yTilt, -60 … 60);
missing values are pressure 1 and no lean.
"""
from __future__ import annotations

import math

import numpy as np

KEYS = ("steady", "tilt_angle", "tilt_size", "taper_start", "taper_end", "size_jitter", "angle_jitter")   # all 0 = off
STEADY_PX = 40.0         # steadiness 100 % = the line trails the pen by up to this many canvas px
TILT_FULL = 60.0         # degrees of lean that count as "on its side"
TILT_WIDEN = 2.0         # tilt → size 100 %, on its side: the tip is this much wider again


def points(raw) -> np.ndarray:
    """The stroke's points as an n x 5 array, defaults filled in."""
    out = np.zeros((len(raw), 5))
    out[:, 2] = 1.0
    for i, q in enumerate(raw):
        out[i, :len(q)] = q[:5]
    return out


def steady(pts: np.ndarray, amount: float, by_dab: bool = False, open_: bool = False) -> np.ndarray:
    """The lazy brush: the line is pulled behind the pen on a string `amount * STEADY_PX` long, so wobbles shorter
    than the string never reach the line; at the end it catches up to where the pen lifted. Causal: what is drawn
    never changes as the pen goes on, so the live stroke and its replay agree. `by_dab` (the stroke's `by_dab`
    draws): the path is made denser a segment at a time, so the line so far stays as it was when more points come
    (the whole path at once spaces its samples by the whole length). `open_`: the pen is still down, no catch-up yet."""
    r = amount * STEADY_PX
    if r <= 0 or len(pts) < 2:
        return pts
    dense = _densify_each(pts, 1.0) if by_dab else _densify(pts, 1.0)
    cur, out = dense[0, :2].copy(), [dense[0]]
    for q in dense[1:]:
        d = q[:2] - cur
        dist = math.hypot(*d)
        if dist > r:
            cur = cur + d * ((dist - r) / dist)
            out.append(np.concatenate([cur, q[2:]]))
    if not open_:
        out.append(dense[-1])
    return np.array(out)


def _densify_each(pts, step):
    """`_densify` a segment at a time: each segment's samples depend on that segment alone."""
    out = [pts[:1]]
    for a, b in zip(pts[:-1], pts[1:]):
        k = max(1, int(math.hypot(*(b[:2] - a[:2])) / step))
        out.append(a + (b - a) * (np.arange(1, k + 1) / k)[:, None])
    return np.concatenate(out)


def _densify(pts, step):
    seg = np.hypot(*np.diff(pts[:, :2], axis=0).T)
    L = np.concatenate([[0], np.cumsum(seg)])
    if L[-1] <= 0:
        return pts
    t = np.linspace(0, L[-1], max(2, int(L[-1] / step) + 1))
    return np.stack([np.interp(t, L, pts[:, k]) for k in range(pts.shape[1])], 1)


def taper(t, L, size, start, end):
    """0..1 per point along the stroke (t in px of L): thin over `start` / `end` tip sizes at either end, at most
    half the stroke each. Ones when both are 0."""
    f = np.ones_like(np.asarray(t, float))
    for amount, d in ((start, t), (end, L - np.asarray(t))):
        if amount > 0:
            span = max(min(amount * size, L / 2), 1e-6)
            f = f * np.sin(np.clip(d / span, 0, 1) * math.pi / 2) ** 0.8
    return np.maximum(f, 0.04)


def lean(t, L, pts):
    """(azimuth radians, lean 0..1) along the stroke at t, from the points' tilt."""
    if L[-1] > 0:
        tx, ty = np.interp(t, L, pts[:, 3]), np.interp(t, L, pts[:, 4])
    else:
        tx, ty = np.full(len(t), pts[0, 3]), np.full(len(t), pts[0, 4])
    return np.arctan2(ty, tx), np.clip(np.hypot(tx, ty) / TILT_FULL, 0, 1)


def dabs(p, th, R, t, L, pts, size, seed, by_dab=False, length=None):
    """Each dab's turn and radius after tilt, taper and jitter (th, R arrays, same length). Jitter draws from its
    own stream of the seed, so turning it on never moves the bristles or drift the stroke already had. `by_dab`:
    the angle jitter has a stream of its own too, so dab i draws the same however many dabs follow. `length`: what
    the taper is sized by (an open stroke's is endless: its start tapers as the finished stroke's will)."""
    n = len(th)
    if p["tilt_angle"] > 0 or p["tilt_size"] > 0:
        az, amount = lean(t, L, pts)
        has = amount > 1e-3
        turn = (az - th + math.pi) % (2 * math.pi) - math.pi
        th = np.where(has, th + p["tilt_angle"] * turn, th)
        R = R * (1 + TILT_WIDEN * p["tilt_size"] * amount)
    if p["taper_start"] > 0 or p["taper_end"] > 0:
        R = R * taper(t, L[-1] if length is None else length, size, p["taper_start"], p["taper_end"])
    if p["size_jitter"] > 0 or p["angle_jitter"] > 0:
        rng = np.random.default_rng([int(seed), 1])
        R = R * (1 - p["size_jitter"] * rng.random(n))
        turn = np.random.default_rng([int(seed), 9]) if by_dab else rng
        th = th + math.radians(p["angle_jitter"]) * turn.uniform(-1, 1, n)
    return th, R


FRAY = (1.0, 1.0)       # by_dab strokes: a bristle or flat tip's ragged start and end reach at most this many brush sizes
EDGE = 0.06             # brush.plan's soft edge of each bristle's start and end, in the units of `along`


def fray(t, length, size, rag, open_=False):
    """by_dab strokes: where each dab lies for the ragged ends (brush.plan's S, its only use: a bristle starts where S
    passes its `start` and stops where 1 - S passes its `end`, with `rag` the most of each), measured in brush sizes
    from each end, not as a share of the stroke. So the start is the same whatever the stroke's length, and an open
    stroke (the pen still down, no end yet) lays it as the finished stroke will. A stroke too short for both ends
    shortens its end first (to a quarter), then both share it."""
    t = np.asarray(t, float)
    if length <= 0:
        return np.zeros_like(t)
    ks, ke = FRAY[0] * size / rag[0], FRAY[1] * size / rag[1]      # px a unit of S spans at each end
    cs, ce = rag[0] + EDGE, rag[1] + EDGE                          # where each end's raggedness is over
    if not open_:
        room = length - cs * ks                                    # what the start leaves the end
        if room < 0.25 * ce * ke:
            f = length / (cs * ks + 0.25 * ce * ke)
            ks, ke = ks * f, 0.25 * ke * f
        else:
            ke = min(ke, room / ce)
    s = np.minimum(t / ks, cs)                                     # past the start: cs, every bristle on
    if open_:
        return s
    e = (length - t) / ke
    return np.where(e < ce, 1 - e, s)                              # 1 - ce: every bristle still on, till the end's


def step_scale(t, L, size, p) -> float:
    """How much closer the next dab comes where the taper thins the tip (1 elsewhere). Asked once per dab, so it is
    `taper` worked out on one number with `math` (the same numbers: tests/test_kit.py checks them against `taper`)."""
    start, end = p["taper_start"], p["taper_end"]
    if start <= 0 and end <= 0:
        return 1.0
    t, L, f = float(t), float(L), 1.0
    for amount, d in ((start, t), (end, L - t)):
        if amount > 0:
            span = max(min(amount * size, L / 2), 1e-6)
            f = f * math.sin(min(max(d / span, 0.0), 1.0) * math.pi / 2) ** 0.8
    return max(f, 0.04)
