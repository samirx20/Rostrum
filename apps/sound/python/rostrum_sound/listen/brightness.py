"""brightness: how much top end a mix has against its low middle, and whether it grows into a climax or lift.

Sound-gaps round 2 (member C): Rostrum's mixes measured dull and stayed dull through a build (top end ~1.3x, Python's
~3x), from dark samples and strings that only get louder, not brighter, with velocity. Measured, not a taste rule:
the top end (4–16 kHz) against the low middle (250 Hz–1 kHz) in dB, per ~85 ms frame where the music is playing (within
30 dB of its loudest frame). On the 15 benchmark files the brightest tenth of the frames measures -2 to -9 dB on bright
pop and lo-fi, -13 to -19 dB on orchestral and dark cues, -20 dB and under on the dull ones."""
from __future__ import annotations

import numpy as np

from .core import load, mono, num
from .memo import remembered

TOP_HZ, LOW_MID_HZ = (4000.0, 16000.0), (250.0, 1000.0)
FRAME = 4096
PLAYING_DB = 30.0          # frames within this of the loudest are "the music playing" (not silence or a tail)
BRIGHT_PCT = 90            # the brightest tenth of the piece: a dull mix has no bright moments at all
SPAN_S = 5.0               # growth: the first 5 s that play against the 5 s from the climax or lift


def _ratios(m, sr) -> tuple[np.ndarray, np.ndarray]:
    """(frame start times, top-vs-low-mid dB) of the playing frames."""
    if len(m) < FRAME:
        return np.zeros(0), np.zeros(0)
    fr = np.lib.stride_tricks.sliding_window_view(m, FRAME)[::FRAME] * np.hanning(FRAME)
    P = np.abs(np.fft.rfft(fr, axis=1)) ** 2
    f = np.fft.rfftfreq(FRAME, 1.0 / sr)
    lv = 10 * np.log10(P.sum(axis=1) + 1e-20)
    keep = lv > lv.max() - PLAYING_DB
    band = lambda lo, hi: P[:, (f >= lo) & (f < hi)].sum(axis=1) + 1e-20
    r = 10 * np.log10(band(*TOP_HZ) / band(*LOW_MID_HZ))
    return (np.arange(len(fr)) * FRAME / sr)[keep], r[keep]


def _energy_db(m, sr, a, b) -> float | None:
    """Top end against low middle over a stretch, energy-weighted (what the stretch sounds like as a whole)."""
    seg = m[max(0, int(a * sr)):int(b * sr)]
    if len(seg) < FRAME:
        return None
    fr = np.lib.stride_tricks.sliding_window_view(seg, FRAME)[::FRAME // 2] * np.hanning(FRAME)
    P = np.abs(np.fft.rfft(fr, axis=1)) ** 2
    f = np.fft.rfftfreq(FRAME, 1.0 / sr)
    lv = P.sum(axis=1)
    P = P[lv > lv.max() * 1e-5].mean(axis=0)
    band = lambda lo, hi: P[(f >= lo) & (f < hi)].sum() + 1e-20
    return float(10 * np.log10(band(*TOP_HZ) / band(*LOW_MID_HZ)))


@remembered
def brightest(wav) -> float | None:
    """The brightest tenth of the playing frames: top end against low middle, dB (None: too short)."""
    y, sr = load(wav)
    _, r = _ratios(mono(y), sr)
    return num(float(np.percentile(r, BRIGHT_PCT)), 1) if r.size else None


def growth(wav, at) -> dict | None:
    """Top end against low middle over the first SPAN_S s that play and over SPAN_S s from `at`, and the change."""
    y, sr = load(wav)
    m = mono(y)
    t, _ = _ratios(m, sr)
    if not t.size or at < 2 * SPAN_S:
        return None
    start = float(t[0])
    a, b = _energy_db(m, sr, start, start + SPAN_S), _energy_db(m, sr, at, at + SPAN_S)
    if a is None or b is None:
        return None
    return {"start_db": num(a, 1), "at_db": num(b, 1), "grew_db": num(b - a, 1), "start_s": num(start, 1)}
