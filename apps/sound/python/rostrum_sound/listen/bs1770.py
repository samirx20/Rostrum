"""ITU-R BS.1770-4 loudness in numpy (replaces pyloudnorm, which needs SciPy): K-weighting, 400 ms gating blocks
with 75 % overlap, the -70 LUFS absolute gate and the -10 LU relative gate, and the 4x oversampled true peak.

The two K-weighting biquads (a +4 dB shelf at 1.5 kHz, a 38 Hz high-pass; the same coefficients pyloudnorm makes)
are applied exactly through the FFT: the signal is zero padded by a second (the filters' response has died out long
before), multiplied by the filters' complex response and transformed back, which equals running them sample by sample.
"""
from __future__ import annotations

import math

import numpy as np

from .dsp import resample_poly

BLOCK_S, OVERLAP = 0.4, 0.75
ABS_GATE, REL_GATE = -70.0, -10.0
GAINS = [1.0, 1.0, 1.0, 1.41, 1.41]          # L, R, C, Ls, Rs


def _biquad(kind: str, gain_db: float, q: float, fc: float, sr: float):
    a_ = 10 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * fc / sr
    c, alpha = math.cos(w0), math.sin(w0) / (2.0 * q)
    if kind == "shelf":
        s = 2 * math.sqrt(a_) * alpha
        b = [a_ * ((a_ + 1) + (a_ - 1) * c + s), -2 * a_ * ((a_ - 1) + (a_ + 1) * c), a_ * ((a_ + 1) + (a_ - 1) * c - s)]
        a = [(a_ + 1) - (a_ - 1) * c + s, 2 * ((a_ - 1) - (a_ + 1) * c), (a_ + 1) - (a_ - 1) * c - s]
    else:
        b = [(1 + c) / 2, -(1 + c), (1 + c) / 2]
        a = [1 + alpha, -2 * c, 1 - alpha]
    return np.array(b) / a[0], np.array(a) / a[0]


def _good_size(n: int) -> int:
    """The smallest 2^i·3^j·5^k >= n (a fast FFT length)."""
    best, p2 = 1 << max(0, (n - 1).bit_length()), 1
    while p2 < best:
        p3 = p2
        while p3 < best:
            p5 = p3
            while p5 < n:
                p5 *= 5
            best = min(best, p5)
            p3 *= 3
        p2 *= 2
    return best


def k_response(freqs, sr: float) -> np.ndarray:
    """The K-weighting filters' complex response at `freqs` (Hz): the one place both biquads are evaluated."""
    z = np.exp(-2j * np.pi * np.asarray(freqs, np.float64) / sr)          # e^{-jw}
    h = np.ones_like(z)
    for b, a in (_biquad("shelf", 4.0, 1 / math.sqrt(2), 1500.0, sr), _biquad("pass", 0.0, 0.5, 38.0, sr)):
        h *= (b[0] + b[1] * z + b[2] * z * z) / (a[0] + a[1] * z + a[2] * z * z)
    return h


def k_weight(y: np.ndarray, sr: float) -> np.ndarray:
    """[n, channels] -> the K-weighted signal (float64), as if both filters ran from silence."""
    y = np.asarray(y, np.float64).reshape(len(y), -1)
    n = y.shape[0]
    size = _good_size(n + int(sr))
    h = k_response(np.fft.rfftfreq(size, 1 / sr), sr)
    return np.stack([np.fft.irfft(np.fft.rfft(y[:, c], size) * h, size)[:n] for c in range(y.shape[1])], axis=1)


def block_powers(kw: np.ndarray, sr: float) -> np.ndarray:
    """Mean square per channel per 400 ms block, blocks every 100 ms -> [channels, blocks] (pyloudnorm's grid)."""
    n = kw.shape[0]
    step = 1.0 - OVERLAP
    count = int(np.round((n / sr - BLOCK_S) / (BLOCK_S * step))) + 1
    j = np.arange(max(count, 0))
    lo = (BLOCK_S * (j * step) * sr).astype(int)
    hi = np.minimum((BLOCK_S * (j * step + 1) * sr).astype(int), n)
    cs = np.vstack([np.zeros((1, kw.shape[1])), np.cumsum(kw * kw, axis=0)])
    return ((cs[hi] - cs[lo]) / (BLOCK_S * sr)).T


def gated_lufs(kw: np.ndarray, sr: float) -> float:
    """Integrated loudness of an already K-weighted [n, channels] signal; -inf when shorter than one block or silent."""
    if kw.shape[0] < int(BLOCK_S * sr):
        return float("-inf")
    z = block_powers(kw, sr)
    g = np.array(GAINS[:z.shape[0]])[:, None]
    with np.errstate(divide="ignore", invalid="ignore"):
        lj = -0.691 + 10 * np.log10((g * z).sum(axis=0))
        keep = lj >= ABS_GATE
        if not keep.any():
            return float("-inf")
        rel = -0.691 + 10 * np.log10((g[:, 0] * z[:, keep].mean(axis=1)).sum()) + REL_GATE
        keep = (lj > rel) & (lj > ABS_GATE)
        return float(-0.691 + 10 * np.log10((g[:, 0] * z[:, keep].mean(axis=1)).sum())) if keep.any() else float("-inf")


def integrated(y: np.ndarray, sr: float) -> float:
    """Integrated loudness (LUFS) of [n, channels] samples."""
    y = np.asarray(y).reshape(len(y), -1)
    return gated_lufs(k_weight(y, sr), sr) if y.shape[0] >= int(BLOCK_S * sr) else float("-inf")


def true_peak(y: np.ndarray, chunk: int = 1 << 20, margin: int = 16) -> float:
    """The highest |sample| after 4x oversampling (linear), worked in overlapping chunks to keep memory small."""
    y = np.asarray(y).reshape(len(y), -1)
    top = 0.0
    for s in range(0, len(y), chunk):
        e = min(len(y), s + chunk)
        a = max(0, s - margin)
        up = resample_poly(y[a:min(len(y), e + margin)], 4, 1, axis=0)
        top = max(top, float(np.max(np.abs(up[(s - a) * 4:(e - a) * 4]))))
    return top
