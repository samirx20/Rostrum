"""How far onsets sit from a beat grid: the one the audio itself has (its beats from the engine: ears/engine_ears.py
`beats`), or the document's tempo map. Offsets are in ms: + means the sound lands after the grid point."""
from __future__ import annotations

import math

import numpy as np

from ..doc import tempo
from ..listen.core import num
from ..listen.onsets import file_onsets
from . import swing as SW


def audio_grid(beats):
    """(to_position, to_time) for the audio's own beats: a time -> fractional beat number, and back; None outside."""
    b = np.asarray(beats, dtype=float)
    idx = np.arange(len(b), dtype=float)
    pos = lambda t: float(np.interp(t, b, idx)) if b[0] <= t <= b[-1] else None  # noqa: E731
    return pos, lambda p: float(np.interp(p, idx, b))


def grid_offsets(onsets, to_position, to_time, div: int = 4, limit_ms: float = 40.0, swing=None) -> dict:
    """Each onset's fractional beat and its distance (ms) to the nearest 1/`div`-beat grid point, plus a summary.
    `swing` (swing, grid): the grid points the document swings are where it plays them (ears/swing.py), so a swung
    off-beat reads on time, never late."""
    rows = []
    for t in onsets:
        p = to_position(t)
        if p is None:
            continue
        near = [(math.floor(p * div) + k) / div for k in (-1, 0, 1, 2)]
        g = min((SW.swung(b, *swing[:2]) if swing else b for b in near), key=lambda b: abs(p - b))
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


def written_bpm(root: dict, seconds: float) -> float:
    """The document's tempo to check the audio against: its tempo, or with tempo changes the one it keeps longest
    (the commonest whole bpm, read every half second; a ritardando's passing tempos don't count against it)."""
    if len(tempo.segments(root)) == 1:
        return tempo.start_bpm(root)
    held, counts = np.unique([round(tempo.bpm_at(root, t)) for t in np.arange(0.0, max(seconds, 0.5), 0.5)], return_counts=True)
    return float(held[np.argmax(counts)])


def relation(heard, written: float) -> str:
    """How a tempo heard relates to the written one: matches, double, half, two thirds, one and a half, or differs."""
    ratio = (heard or 0) / written
    named = [(1.0, "matches"), (2.0, "double"), (0.5, "half"), (2 / 3, "two thirds"), (1.5, "one and a half times")]
    return next((w for k, w in named if abs(ratio / k - 1) < 0.03), "differs")


def fits(r: dict, written: float) -> bool:
    """Whether the audio's beats fit the written tempo: the engine's answer, or (an engine without `--expect-bpm`)
    its own reading matching it."""
    e = r.get("expected")
    return bool(e["fits"]) if e else relation(r["bpm"], written) == "matches"


def tempo_line(r: dict, written: float | None, changes: bool) -> str:
    """The tempo in plain words: the document's, checked against the audio's beats when there is a document."""
    drift = f" ({r['bpm_start']} → {r['bpm_end']})" if r.get("steadiness") == "drifting" else ""
    if written is None:
        close = f" (or {r['tempo_unsure']:g} BPM: a close call, the same groove counted another way)" if r.get("tempo_unsure") else ""
        return f"{r['bpm']} BPM, {r['steadiness']}{drift}{close}"
    doc = f"{written:g} BPM, the document's" + (" (the tempo it keeps longest; it changes tempo)" if changes else "")
    heard, rel = r["heard_bpm"], relation(r["heard_bpm"], written)
    if fits(r, written):
        alone = "" if rel == "matches" else (f"; the sound alone also reads {heard:g} BPM ({rel} the document's): rolls, fast figures and "
                                              "repeated hits add beats, so the grid and the offsets below use the document's tempo, which fits")
        return f"{doc}; the audio's beats fit it{alone}; {r['steadiness']}{drift}"
    return f"{doc}; the audio's beats do NOT fit it: they read {r['bpm']} BPM ({rel}), {r['steadiness']}{drift}"
