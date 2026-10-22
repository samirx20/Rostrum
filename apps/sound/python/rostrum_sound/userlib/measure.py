"""Measuring one sound (mono samples): how long, how it starts, where its loudest moment is, how bright, how loud.
And the plain-word scales search uses (short / medium / long, dark / mid / bright, sharp / medium / soft), so an
agent can ask for "a short bright whoosh" or give numbers.

  seconds      its length
  onset_s      where it first reaches 30 dB under its peak (its start, as the ear hears it)
  peak_s       its loudest moment (10 ms smoothing), from the sound's start: a whoosh is placed by this
  attack_ms    onset to peak: 3 ms is a click, 300 ms a slow swell
  peak_frac    where the peak sits in the sound, 0 = at once … 1 = at the end (a riser)
  centroid_hz  brightness as a frequency (the spectrum's centre of mass over the sounding part)
  brightness   the same on 0 … 1 (250 Hz = 0, 8 kHz = 1, on a log scale)
  peak_db, lufs  sample peak (dBFS) and loudness (LUFS; a sound shorter than 0.4 s is measured repeated to
               0.4 s, so it says how loud it is while it sounds)
  crest_db     peak over average level: low for a steady bed, high for a click
"""
from __future__ import annotations

import math

import numpy as np

SCALES = {
    "length": (("short", 0.0, 0.5), ("medium", 0.5, 1.5), ("long", 1.5, math.inf)),
    "brightness": (("dark", 0.0, 0.4), ("mid", 0.4, 0.65), ("bright", 0.65, 1.01)),
    "attack": (("sharp", 0.0, 15.0), ("medium", 15.0, 60.0), ("soft", 60.0, math.inf)),
}
FIELD = {"length": "seconds", "brightness": "brightness", "attack": "attack_ms"}
LOW_HZ, HIGH_HZ = 250.0, 8000.0


def word(scale: str, value: float) -> str:
    return next(w for w, lo, hi in SCALES[scale] if lo <= value < hi)


def span(scale: str, w: str) -> tuple[float, float]:
    for name, lo, hi in SCALES[scale]:
        if name == w:
            return lo, hi
    raise ValueError(f"{scale}: '{w}' is not one of {[n for n, _, _ in SCALES[scale]]}")


def _db(v: float) -> float:
    return 20 * math.log10(max(float(v), 1e-9))


def envelope(x: np.ndarray, sr: int, ms: float = 10.0) -> np.ndarray:
    n = max(1, int(sr * ms / 1000))
    return np.convolve(np.abs(x), np.ones(n) / n, mode="same")


def sounding(x: np.ndarray, sr: int, below_db: float = 45.0) -> tuple[int, int]:
    """(first, last) sample of the part above `below_db` under the peak: the sound without silence around it."""
    env = envelope(x, sr, 5.0)
    loud = np.nonzero(env >= env.max() * 10 ** (-below_db / 20))[0]
    if loud.size == 0:
        return 0, x.size
    return int(loud[0]), int(loud[-1]) + 1


def regions(x: np.ndarray, sr: int, gap_s: float = 0.25, below_db: float = 45.0) -> list[tuple[int, int]]:
    """The separate sounds in a file: stretches above `below_db` under the peak, split by silences ≥ `gap_s`."""
    env = envelope(x, sr, 5.0)
    on = env >= env.max() * 10 ** (-below_db / 20)
    idx = np.nonzero(on)[0]
    if idx.size == 0:
        return []
    breaks = np.nonzero(np.diff(idx) > gap_s * sr)[0]
    starts = np.concatenate([[idx[0]], idx[breaks + 1]])
    ends = np.concatenate([idx[breaks], [idx[-1]]]) + 1
    return [(int(a), int(b)) for a, b in zip(starts, ends)]


def _centroid(x: np.ndarray, sr: int) -> float:
    n = 2048
    if x.size < n:
        x = np.pad(x, (0, n - x.size))
    hop = max(n // 2, (x.size - n) // 200)          # at most ~200 frames, however long the sound
    frames = np.lib.stride_tricks.sliding_window_view(x, n)[::hop] * np.hanning(n)
    spec = np.abs(np.fft.rfft(frames, axis=1))
    freqs = np.fft.rfftfreq(n, 1 / sr)
    energy = spec.sum(axis=1)
    keep = energy >= energy.max() * 0.01                # frames within 40 dB of the loudest
    s = spec[keep].sum(axis=0)
    return float((s * freqs).sum() / max(s.sum(), 1e-12))


def _lufs(x: np.ndarray, sr: int) -> float:
    from ..listen.bs1770 import integrated
    if x.size < int(0.4 * sr):                          # a click: its level while it sounds, not diluted by silence
        x = np.tile(x, int(np.ceil(0.4 * sr / x.size)))
    v = integrated(x, sr)
    return round(v, 1) if math.isfinite(v) else -99.0


def measure(x: np.ndarray, sr: int) -> dict:
    """The measurements of one sound (see the module text). `x` mono, already cut to the sound."""
    if x.size < int(0.005 * sr):
        raise ValueError("a sound shorter than 5 ms can't be measured")
    env = envelope(x, sr, 10.0)
    peak_i = int(np.argmax(env))
    onset_i = int(np.argmax(envelope(x, sr, 2.0) >= env[peak_i] * 10 ** (-30 / 20)))
    onset_i = min(onset_i, peak_i)
    seconds = x.size / sr
    centroid = _centroid(x, sr)
    peak = float(np.abs(x).max())
    rms = float(np.sqrt(np.mean(x[x.size // 50:] ** 2))) if x.size > 50 else peak
    bright = (math.log(max(centroid, LOW_HZ)) - math.log(LOW_HZ)) / (math.log(HIGH_HZ) - math.log(LOW_HZ))
    return {"seconds": round(seconds, 4), "onset_s": round(onset_i / sr, 4), "peak_s": round(peak_i / sr, 4),
            "attack_ms": round((peak_i - onset_i) / sr * 1000, 1), "peak_frac": round(peak_i / x.size, 3),
            "centroid_hz": round(centroid), "brightness": round(min(1.0, bright), 3),
            "peak_db": round(_db(peak), 1), "lufs": _lufs(x, sr), "crest_db": round(_db(peak) - _db(rms), 1)}


def words_of(m: dict) -> dict:
    """The plain words for a measured sound: {"length": "short", "brightness": "bright", "attack": "sharp"}."""
    return {s: word(s, m[f]) for s, f in FIELD.items()}
