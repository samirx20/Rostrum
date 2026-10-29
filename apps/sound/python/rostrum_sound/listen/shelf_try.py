"""shelf_try: what a master high shelf would do to dull_top's measure, measured on the render itself.

Canary 3E r8: dull_top promised "a +8 dB shelf over 4 kHz, measured to clear it" from a bench-average slope, and on a
dark solo piano it moved the brightest tenth from -33.8 only to -29.1 dB (the pass line is -20). So the shelf is tried
on this file: the engine's own filter (an RBJ high shelf, engine/src/fx/eq.rs; the same formula as bs1770's) applied as
its |H|^2 to each frame's spectrum, then the brightest tenth read again exactly as brightness.brightest reads it.

    reach(wav, gain) -> the brightest tenth with that shelf on (dB)
    clearing(wav, need, most) -> {"gain", "reaches_db", "clears"}: the smallest gain (0.5 dB steps, at most `most`)
        whose reading reaches `need`, else `most` and what it reaches
"""
from __future__ import annotations

import numpy as np

from .bs1770 import _biquad
from .brightness import BRIGHT_PCT, _ratios
from .core import load, mono, num
from .memo import remembered

FREQ, Q = 4000.0, 0.7       # the shelf dull_top's fix writes: master.effect("eq", bands=[{"shape": "highshelf", ...}])


def response(gain_db: float, sr: float):
    """f -> the shelf's power gain |H(f)|^2 (the engine's biquad at `sr`)."""
    b, a = _biquad("shelf", gain_db, Q, min(FREQ, 0.49 * sr), sr)

    def power(f):
        z = np.exp(-2j * np.pi * np.asarray(f, np.float64) / sr)
        h = (b[0] + b[1] * z + b[2] * z * z) / (a[0] + a[1] * z + a[2] * z * z)
        return np.abs(h) ** 2
    return power


@remembered
def reach(wav, gain_db: float) -> float | None:
    y, sr = load(wav)
    _, r = _ratios(mono(y), sr, response(gain_db, sr))
    return num(float(np.percentile(r, BRIGHT_PCT)), 1) if r.size else None


def clearing(wav, need: float, most: float) -> dict | None:
    """The smallest shelf (0.5 dB steps up to `most`) whose reading reaches `need`; when none does, `most` and what it
    reaches (clears False)."""
    top = reach(wav, most)
    if top is None:
        return None
    if top < need:
        return {"gain": most, "reaches_db": top, "clears": False}
    lo, hi = 0, int(round(2 * most))           # the measure only grows with the gain: halve the steps
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if (reach(wav, mid / 2) or -1e9) >= need:
            hi = mid
        else:
            lo = mid
    return {"gain": hi / 2, "reaches_db": reach(wav, hi / 2), "clears": True}
