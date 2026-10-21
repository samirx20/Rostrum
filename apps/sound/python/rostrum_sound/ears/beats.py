"""Tempo and beats from audio (librosa), and how far onsets sit from a beat grid: the one the audio itself has, or the
document's tempo map. Offsets are in ms: + means the sound lands after the grid point."""
from __future__ import annotations

import librosa
import numpy as np

from ..listen.core import load, mono, num
from ..listen.onsets import detect

HOP = 512


def analyse_beats(wav, beats_per_bar: int = 4) -> dict:
    """Facts about the pulse: bpm (median), how steady (`steadiness`: steady / drifting / uneven), every beat
    time, a downbeat guess (the beat phase that is strongest, with how much stronger) and the loaded audio."""
    y, sr = load(wav)
    m = mono(y)
    env = librosa.onset.onset_strength(y=m, sr=sr, hop_length=HOP)
    tempo, frames = librosa.beat.beat_track(onset_envelope=env, sr=sr, hop_length=HOP, tightness=60)
    beats = librosa.frames_to_time(frames, sr=sr, hop_length=HOP)
    out = {"duration_s": num(len(m) / sr, 3), "beats_s": [num(b, 4) for b in beats], "bpm": num(float(np.ravel(tempo)[0]), 1)}
    if len(beats) < 4:
        return {**out, "steadiness": "unknown", "downbeats_s": [], "downbeat_confidence": None,
                "note": "fewer than 4 beats found: no steady pulse to follow"}
    ibi = np.diff(beats)
    bpm = 60.0 / ibi
    third = max(2, len(bpm) // 3)
    first, last = float(np.median(bpm[:third])), float(np.median(bpm[-third:]))
    cv = float(1.4826 * np.median(np.abs(ibi - np.median(ibi))) / np.median(ibi))     # robust: one missed beat is not unsteadiness
    change = (last - first) / first * 100
    steady = "steady" if cv < 0.05 and abs(change) < 3 else "drifting" if abs(change) >= 3 and cv < 0.15 else "uneven"
    out |= {"bpm": num(float(np.median(bpm)), 1), "bpm_start": num(first, 1), "bpm_end": num(last, 1),
            "bpm_change_pct": num(change, 1), "beat_spacing_variation": num(cv, 3), "steadiness": steady}
    down, conf = _downbeats(env, frames, beats, beats_per_bar)
    return {**out, "downbeats_s": [num(b, 4) for b in down], "downbeat_confidence": conf}


def _downbeats(env, frames, beats, bpb):
    strength = np.array([env[max(0, f - 2):f + 3].max() for f in frames])
    phase = [strength[k::bpb].mean() for k in range(bpb)]
    best = int(np.argmax(phase))
    return beats[best::bpb], num(phase[best] / max(float(np.mean(phase)), 1e-9), 2)


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
    y, sr = load(wav)
    return detect(mono(y), sr)
