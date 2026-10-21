"""Shared helpers: load audio, band split, sections, JSON-safe numbers."""
import math

import librosa
import numpy as np
import soundfile as sf

BANDS = [("sub", 0, 60), ("low", 60, 250), ("low_mid", 250, 2000),
         ("high_mid", 2000, 6000), ("air", 6000, None)]
BAND_NAMES = [b[0] for b in BANDS]
N_FFT, HOP = 4096, 2048


def load(path):
    """Return (samples [n, channels] float32, sample rate). Fails loudly."""
    y, sr = sf.read(path, dtype="float32", always_2d=True)
    if y.shape[0] == 0:
        raise ValueError(f"{path}: file has no audio")
    return y, sr


def mono(y):
    return y.mean(axis=1)


def db(x, floor=-120.0):
    """Linear power -> dB, clamped (silence reads as the floor, not -inf)."""
    return float(max(floor, 10 * math.log10(max(float(x), 1e-30))))


def num(x, nd=2):
    """JSON-safe number: -inf/nan -> None."""
    x = float(x)
    return None if (math.isnan(x) or math.isinf(x)) else round(x, nd)


def band_power(y, sr):
    """Per-band power over time. Returns (times [T], power [5, T]); a full-scale
    sine reads about 0 dBFS (power 0.5) in its band."""
    chans = [y[:, c] for c in range(y.shape[1])] if y.ndim == 2 else [y]
    scale = 2.0 / np.hanning(N_FFT).sum()
    # power per channel, then averaged: a phase-flipped channel must not cancel
    pw = np.mean([(np.abs(librosa.stft(c, n_fft=N_FFT, hop_length=HOP)) * scale) ** 2 / 2.0
                  for c in chans], axis=0)
    f = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)
    out = np.zeros((len(BANDS), pw.shape[1]))
    for i, (_, lo, hi) in enumerate(BANDS):
        sel = (f >= lo) & ((f < hi) if hi else True)
        out[i] = pw[sel].sum(axis=0)
    return librosa.frames_to_time(np.arange(pw.shape[1]), sr=sr, hop_length=HOP), out


def sections(duration, length):
    """[(t0, t1)] covering the file in `length`-second pieces (last may be short)."""
    n = max(1, math.ceil(duration / length - 1e-9))
    return [(i * length, min(duration, (i + 1) * length)) for i in range(n)]


def section_power(times, power, secs):
    """Mean band power per section -> [len(secs), 5]."""
    rows = []
    for t0, t1 in secs:
        sel = (times >= t0) & (times < t1)
        if not sel.any():
            sel = np.abs(times - (t0 + t1) / 2) == np.abs(times - (t0 + t1) / 2).min()
        rows.append(power[:, sel].mean(axis=1))
    return np.array(rows)


def duration(y, sr):
    return y.shape[0] / sr
