"""A push that keeps its subject in the picture: the frame's centre eased to match its zoom.

The frame's x, y and zoom are keyed apart. With the same ease on all three, a deep push from the wide shot onto a small
part swings off it mid-move: the centre is half way when the zoom is only half way up, and at that zoom the half-way
centre throws the subject out to the side (a 10x push carries it ~2.75x as far from the centre as where it started,
past the edge; both Tally runs of the 2026-10-30 bench got a blank frame at 3 s).

A real camera push zooms about one point that holds still on screen: the point q where (q - c0)·z0 = (q - c1)·z1.
Keeping it still while the zoom runs as keyed puts the centre at c(t) = q - (q - c0)·z0 / z(t): a straight line from c0
to c1 whose progress is h(e) = (1 - z0 / z) · z1 / (z1 - z0), where e is the zoom's own progress. Every point of the
picture then travels straight towards or away from q, so what is framed at either end stays on its way, never past it.
`ease_for` writes that progress as the x and y keys' own curve (a `custom` cubic, fitted): ordinary keys a person can
still drag, no extra keys."""
from __future__ import annotations

import math

import numpy as np

from rostrum_core.keys import easing

SAMPLES = 64
STILL = 0.02            # a zoom change under 2 %: a pan, eased as keyed


def progress(zoom_key: dict, z0: float, z1: float, x: np.ndarray) -> np.ndarray:
    """The centre's progress at time fractions `x` for a zoom from z0 to z1 eased by `zoom_key`'s ease."""
    e = np.array([easing.ease(zoom_key, float(v)) for v in x])
    z = z0 + e * (z1 - z0)
    return (1 - z0 / z) * z1 / (z1 - z0)


def _curve(x1, y1, x2, y2, xs):
    u = np.linspace(0.0, 1.0, 257)
    v = 1 - u
    bx = 3 * v * v * u * x1 + 3 * v * u * u * x2 + u ** 3
    by = 3 * v * v * u * y1 + 3 * v * u * u * y2 + u ** 3
    return np.interp(xs, bx, by)


def ease_for(zoom_key: dict, z0: float, z1: float) -> dict | None:
    """The x / y keys' ease ({"ease": "custom", x1, y1, x2, y2}) that holds the push's still point still, or None when
    the zoom barely changes (a pan) or its ease isn't a curve (spring, bounce, hold: left as keyed)."""
    name = zoom_key.get("ease", "smooth")
    if name not in ("linear", "custom", *easing.BEZIERS) or z0 <= 0 or z1 <= 0 or abs(z1 / z0 - 1) < STILL:
        return None
    xs = np.linspace(0.0, 1.0, SAMPLES)
    want = progress(zoom_key, z0, z1, xs)
    d = 1e-4
    m0 = float(progress(zoom_key, z0, z1, np.array([d]))[0]) / d
    m1 = (1 - float(progress(zoom_key, z0, z1, np.array([1 - d]))[0])) / d
    t0, t1 = math.atan(max(m0, 0.0)), math.atan(max(m1, 0.0))
    best = None
    for a in np.linspace(0.05, 1.2, 24):            # handle lengths, along the curve's own slopes at its ends
        x1, y1 = min(1.0, a * math.cos(t0)), min(1.0, a * math.sin(t0))
        for b in np.linspace(0.05, 1.2, 24):
            x2, y2 = max(0.0, 1 - b * math.cos(t1)), max(0.0, 1 - b * math.sin(t1))
            err = float(np.max(np.abs(_curve(x1, y1, x2, y2, xs) - want)))
            if best is None or err < best[0]:
                best = (err, x1, y1, x2, y2)
    _, x1, y1, x2, y2 = best
    return {"ease": "custom", "x1": round(x1, 4), "y1": round(y1, 4), "x2": round(x2, 4), "y2": round(y2, 4)}
