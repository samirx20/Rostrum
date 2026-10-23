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


def steady(pts: np.ndarray, amount: float) -> np.ndarray:
    """The lazy brush: the line is pulled behind the pen on a string `amount * STEADY_PX` long, so wobbles shorter
    than the string never reach the line; at the end it catches up to where the pen lifted. Causal: what is drawn
    never changes as the pen goes on, so the live stroke and its replay agree."""
    r = amount * STEADY_PX
    if r <= 0 or len(pts) < 2:
        return pts
    dense = _densify(pts, 1.0)
    cur, out = dense[0, :2].copy(), [dense[0]]
    for q in dense[1:]:
        d = q[:2] - cur
        dist = math.hypot(*d)
        if dist > r:
            cur = cur + d * ((dist - r) / dist)
            out.append(np.concatenate([cur, q[2:]]))
    out.append(dense[-1])
    return np.array(out)


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


def dabs(p, th, R, t, L, pts, size, seed):
    """Each dab's turn and radius after tilt, taper and jitter (th, R arrays, same length). Jitter draws from its
    own stream of the seed, so turning it on never moves the bristles or drift the stroke already had."""
    n = len(th)
    if p["tilt_angle"] > 0 or p["tilt_size"] > 0:
        az, amount = lean(t, L, pts)
        has = amount > 1e-3
        turn = (az - th + math.pi) % (2 * math.pi) - math.pi
        th = np.where(has, th + p["tilt_angle"] * turn, th)
        R = R * (1 + TILT_WIDEN * p["tilt_size"] * amount)
    if p["taper_start"] > 0 or p["taper_end"] > 0:
        R = R * taper(t, L[-1], size, p["taper_start"], p["taper_end"])
    if p["size_jitter"] > 0 or p["angle_jitter"] > 0:
        rng = np.random.default_rng([int(seed), 1])
        R = R * (1 - p["size_jitter"] * rng.random(n))
        th = th + math.radians(p["angle_jitter"]) * rng.uniform(-1, 1, n)
    return th, R


def step_scale(t, L, size, p) -> float:
    """How much closer the next dab comes where the taper thins the tip (1 elsewhere)."""
    if p["taper_start"] <= 0 and p["taper_end"] <= 0:
        return 1.0
    return float(taper(np.array([t]), L, size, p["taper_start"], p["taper_end"])[0])
