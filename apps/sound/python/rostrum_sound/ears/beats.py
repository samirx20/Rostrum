"""How far onsets sit from a beat grid: the one the audio itself has (its beats from the engine: ears/engine_ears.py
`beats`), or the document's tempo map. Offsets are in ms: + means the sound lands after the grid point."""
from __future__ import annotations

import numpy as np

from ..listen.core import num
from ..listen.onsets import file_onsets


def audio_grid(beats):
    """(to_position, to_time) for the audio's own beats: a time -> fractional beat number, and back; None outside."""
    b = np.asarray(beats, dtype=float)
    idx = np.arange(len(b), dtype=float)
    pos = lambda t: float(np.interp(t, b, idx)) if b[0] <= t <= b[-1] else None  # noqa: E731
    return pos, lambda p: float(np.interp(p, idx, b))


def grid_offsets(onsets, to_position, to_time, div: int = 4, limit_ms: float = 40.0) -> dict:
    """Each onset's fractional beat and its distance (ms) to the nearest 1/`div`-beat grid point, plus a summary."""
    rows = []
    for t in onsets:
        p = to_position(t)
        if p is None:
            continue
        g = round(p * div) / div
        rows.append({"t": num(t, 4), "beat": num(p, 2), "off_ms": num((t - to_time(g)) * 1000, 1)})
    if not rows:
        return {"items": [], "summary": None}
    off = np.array([r["off_ms"] for r in rows])
    return {"items": rows, "summary": {
        "grid": f"1/{div} beat", "onsets": len(rows), "mean_off_ms": num(off.mean(), 1), "median_abs_off_ms": num(np.median(np.abs(off)), 1),
        "within_limit_pct": num(100 * float(np.mean(np.abs(off) <= limit_ms)), 0), "limit_ms": limit_ms,
        "lean": "late" if off.mean() > 10 else "early" if off.mean() < -10 else "on the grid"}}


def stem_onsets(wav) -> list[float]:
    return file_onsets(wav)
