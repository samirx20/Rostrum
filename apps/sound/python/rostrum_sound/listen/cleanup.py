"""Hearing a cleanup: before vs after (noise floor, speech level, their gap, the reverb tail) and stems (each one's
level, how much they leak into each other, and with reference stems the SDR). Facts only; pictures: cleanup_draw.py.

    clean_compare(before, after, png)            # {"before": {...}, "after": {...}, "change": {...}, "png"}
    stems_check({"vocals": wav, ...}, png, reference={"vocals": wav, ...})
"""
from __future__ import annotations

from itertools import combinations

import numpy as np

from .core import db, load, mono, name_of, num

FRAME_S = 0.05      # level frames
TAIL_FRAME_S = 0.01  # the reverb tail is read in finer frames
TAIL_S = 0.2
FLOOR_PCT, LEVEL_PCT = 10, 90
PRESENT_DB = 10     # a frame this far above the floor has sound in it; the level is read over those frames only


def frames_db(m, sr, frame_s=FRAME_S):
    """RMS level per frame (dB, silence at the floor of core.db)."""
    n = max(1, int(sr * frame_s))
    k = len(m) // n
    if k == 0:
        return np.array([db(np.mean(m.astype(np.float64) ** 2))])
    ms = np.mean(m[:k * n].astype(np.float64).reshape(k, n) ** 2, axis=1)
    return 10 * np.log10(np.maximum(ms, 1e-12))


def _tail(m, sr, floor, level):
    """Median fall in level over the 200 ms after the sound stops (dB; bigger = drier), and how many stops it read.
    A stop: a 10 ms frame above halfway between floor and level, followed by 200 ms that never get back above it."""
    f = frames_db(m, sr, TAIL_FRAME_S)
    on = f > (floor + level) / 2
    span = int(round(TAIL_S / TAIL_FRAME_S))
    drops = []
    for i in np.flatnonzero(on[:-1] & ~on[1:]):
        after = f[i + 1:i + 1 + span]
        if len(after) == span and not on[i + 1:i + 1 + span].any():
            drops.append(f[i] - after[-5:].mean())
    return (num(np.median(drops)) if drops else None), len(drops)


def measure(src) -> dict:
    """One file: noise floor (the quiet 10th percentile of 50 ms frames), speech / signal level (90th percentile of the
    frames with sound in them, 10 dB over the floor), their gap,
    and the reverb tail. dB are dBFS (RMS)."""
    y, sr = load(src)
    m = mono(y)
    f = frames_db(m, sr)
    floor = float(np.percentile(f, FLOOR_PCT))
    present = f[f > floor + PRESENT_DB]      # so a line that speaks for 5 s of 60 reads its own level, not silence's
    level = float(np.percentile(present if len(present) else f, LEVEL_PCT))
    tail, stops = _tail(m, sr, floor, level)
    return {"file": str(src), "seconds": num(len(m) / sr, 3), "floor_db": num(floor, 1), "level_db": num(level, 1),
            "gap_db": num(level - floor, 1), "tail_drop_db": tail, "tail_stops": stops}


def clean_compare(before, after, png=None) -> dict:
    """Before vs after, and what changed (after minus before): the floor should fall, the gap and the tail's drop
    grow, the level stay near where it was."""
    b, a = measure(before), measure(after)
    change = {k: num(a[k] - b[k], 1) if a[k] is not None and b[k] is not None else None
              for k in ("floor_db", "level_db", "gap_db", "tail_drop_db")}
    out = {"before": b, "after": a, "change": change,
           "note": "floor = quiet 10th percentile of 50 ms RMS frames; level = 90th percentile of the frames with sound (10 dB over the floor); gap = level - floor; "
                   "tail_drop = median fall in the 200 ms after the sound stops (bigger = less reverb)"}
    if png:
        from .cleanup_draw import draw_compare
        out["png"] = draw_compare(before, after, b, a, png)
    return out


def _envelope(src):
    """(mono samples, rate, linear RMS level per 50 ms frame)."""
    y, sr = load(src)
    m = mono(y)
    lin = np.sqrt(10 ** (frames_db(m, sr) / 10))
    return m, sr, lin


def sdr(estimate, reference) -> float | None:
    """Signal-to-distortion ratio (dB) of one stem against its reference: 10·log10(|ref|² / |ref - est|²)."""
    n = min(len(estimate), len(reference))
    e, r = estimate[:n].astype(np.float64), reference[:n].astype(np.float64)
    return num(10 * np.log10(max(np.sum(r ** 2), 1e-12) / max(np.sum((r - e) ** 2), 1e-12)), 1)


def stems_check(stems: dict, png=None, reference: dict | None = None, clip: str | None = None) -> dict:
    """Each stem's level (dB RMS over the whole file, and its 90th-percentile frame), leakage = the correlation of
    every pair's 50 ms level envelopes (near 1 = they rise and fall together: one leaks into the other), and per
    stem the SDR against `reference` stems when given."""
    if len(stems) < 2:
        raise ValueError(f"stems check: needs at least two stems, got {list(stems)}")
    read = {k: _envelope(v) for k, v in stems.items()}
    levels = {k: {"file": str(stems[k]), "level_db": num(db(np.mean(m.astype(np.float64) ** 2)), 1),
                  "loud_db": num(np.percentile(20 * np.log10(np.maximum(env, 1e-6)), LEVEL_PCT), 1)}
              for k, (m, _, env) in read.items()}
    leakage = []
    for a, b in combinations(read, 2):
        ea, eb = read[a][2], read[b][2]
        n = min(len(ea), len(eb))
        c = np.corrcoef(ea[:n], eb[:n])[0, 1] if n > 1 and ea[:n].std() > 0 and eb[:n].std() > 0 else float("nan")
        leakage.append({"pair": [a, b], "correlation": num(c, 3)})
    out = {"stems": levels, "leakage": leakage,
           "note": "leakage: correlation of 50 ms level envelopes per pair (near 0 = independent, near 1 = one is heard in the other)"}
    if reference:
        missing = [k for k in reference if k not in read]
        if missing:
            raise ValueError(f"stems check: reference names stems that are not given: {missing}")
        out["sdr_db"] = {k: sdr(read[k][0], mono(load(v)[0])) for k, v in reference.items()}
    if png:
        from .cleanup_draw import draw_stems
        out["png"] = draw_stems({k: (env, sr) for k, (_, sr, env) in read.items()}, png, name_of(next(iter(stems.values()))), clip)
    return out
