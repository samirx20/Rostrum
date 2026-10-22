"""Numpy replacements for the event finders the ears used from librosa / SciPy: onset strength and onset picking
(librosa's mel spectral flux and greedy peak picker), peaks in a curve (scipy.signal.find_peaks: height and
distance), chroma from an STFT, and closing / labelling a 2-D mask (scipy.ndimage.binary_closing, label)."""
from __future__ import annotations

import numpy as np

from .dsp import fft_frequencies, frames_to_time, power_to_db, stft

ONSET_N_FFT, N_MELS = 2048, 128


def _hz_to_mel(f):
    """Slaney's mel scale: linear under 1 kHz, logarithmic above."""
    f = np.asarray(f, float)
    return np.where(f < 1000.0, 3.0 * f / 200.0, 15.0 + np.log(np.maximum(f, 1e-9) / 1000.0) / (np.log(6.4) / 27.0))


def _mel_to_hz(m):
    m = np.asarray(m, float)
    return np.where(m < 15.0, 200.0 * m / 3.0, 1000.0 * np.exp((np.log(6.4) / 27.0) * (m - 15.0)))


def mel_filters(sr: float, n_fft: int, n_mels: int = N_MELS) -> np.ndarray:
    """[n_mels, bins] triangles on the Slaney mel scale, area-normalised (librosa.filters.mel's defaults)."""
    f = fft_frequencies(sr, n_fft)
    edges = _mel_to_hz(np.linspace(_hz_to_mel(0.0), _hz_to_mel(sr / 2.0), n_mels + 2))
    lo, mid, hi = edges[:-2, None], edges[1:-1, None], edges[2:, None]
    tri = np.maximum(0.0, np.minimum((f - lo) / (mid - lo), (hi - f) / (hi - mid)))
    return (tri * (2.0 / (hi - lo))).astype(np.float32)


def onset_strength(y: np.ndarray, sr: float, hop: int) -> np.ndarray:
    """Spectral flux on a 128-band mel spectrogram in dB, averaged over bands, one value per frame."""
    S = power_to_db(mel_filters(sr, ONSET_N_FFT) @ (np.abs(stft(y, ONSET_N_FFT, hop)) ** 2))
    env = np.maximum(0.0, S[:, 1:] - S[:, :-1]).mean(axis=0)
    return np.pad(env, (1 + ONSET_N_FFT // (2 * hop), 0))[:S.shape[1]]


def _window_max(x, before: int, after: int):
    """max of x[n - before : n + after] for every n (the window cut at the ends)."""
    xp = np.pad(np.asarray(x, float), (before, after), constant_values=-np.inf)
    return np.lib.stride_tricks.sliding_window_view(xp, before + after)[:len(x)].max(axis=1)


def peak_pick(x, pre_max, post_max, pre_avg, post_avg, delta, wait) -> np.ndarray:
    """librosa's greedy peak picker: the local max of its window, `delta` over the window's mean, and at least
    `wait` frames after the previous pick."""
    pre_max, post_max, pre_avg, post_avg, wait = (int(np.ceil(v)) for v in (pre_max, post_max, pre_avg, post_avg, wait))
    c = np.concatenate([[0.0], np.cumsum(x, dtype=np.float64)])
    n = np.arange(len(x))
    a, b = np.maximum(0, n - pre_avg), np.minimum(len(x), n + post_avg)
    ok = (x == _window_max(x, pre_max, post_max)) & (x >= (c[b] - c[a]) / (b - a) + delta)
    out, last = [], -wait - 1
    for i in np.flatnonzero(ok):
        if i > last + wait:
            out.append(i)
            last = i
    return np.array(out, dtype=int)


def onset_detect(y: np.ndarray, sr: float, hop: int, backtrack: bool = False, delta: float = 0.07,
                 env: np.ndarray | None = None) -> np.ndarray:
    """Onset frames (librosa.onset.onset_detect's defaults). `backtrack` moves each to the energy dip before it."""
    env = onset_strength(y, sr, hop) if env is None else np.asarray(env, float)
    env = env - env.min()
    env = env / (env.max() + np.finfo(float).tiny)
    if not env.any() or not np.isfinite(env).all():
        return np.array([], dtype=int)
    on = peak_pick(env, 0.03 * sr // hop, 0.0 * sr // hop + 1, 0.10 * sr // hop, 0.10 * sr // hop + 1,
                   delta, 0.03 * sr // hop)
    if backtrack and on.size:
        dips = np.unique(np.concatenate([[0], 1 + np.flatnonzero((env[1:-1] <= env[:-2]) & (env[1:-1] < env[2:]))]))
        on = dips[np.searchsorted(dips, on, side="right") - 1]
    return on


def onset_times(y, sr, hop) -> np.ndarray:
    return frames_to_time(onset_detect(y, sr, hop), sr, hop)


def find_peaks(x, height: float | None = None, distance: int = 1) -> np.ndarray:
    """Indices of local maxima (a flat top counts once, at its middle), at least `height`, and no two closer than
    `distance` (the higher one is kept): scipy.signal.find_peaks with those two options."""
    x = np.asarray(x, float)
    peaks, i = [], 1
    while i < len(x) - 1:
        if x[i - 1] < x[i]:
            j = i
            while j + 1 < len(x) - 1 and x[j + 1] == x[i]:
                j += 1
            if x[j + 1] < x[i]:
                peaks.append((i + j) // 2)
            i = j
        i += 1
    p = np.array([k for k in peaks if height is None or x[k] >= height], dtype=int)
    keep = np.ones(len(p), bool)
    for k in np.argsort(x[p])[::-1] if distance > 1 else []:          # SciPy's order, ties included
        if keep[k]:
            keep[np.abs(p - p[k]) < distance] = False
            keep[k] = True
    return p[keep]


def _median(S: np.ndarray, k: int, axis: int, block: int = 256) -> np.ndarray:
    """Median of a k-wide window along `axis` (0 or 1) of a 2-D array, edges padded by reflection, in blocks."""
    S = S if axis == 1 else S.T
    pad = np.pad(S, ((0, 0), (k // 2, k // 2)), mode="reflect")
    out = np.concatenate([np.median(np.lib.stride_tricks.sliding_window_view(pad[i:i + block], k, axis=1), axis=2)
                          for i in range(0, S.shape[0], block)])
    return out if axis == 1 else out.T


def harmonic_part(S: np.ndarray, time_k: int, freq_k: int) -> np.ndarray:
    """The steady (harmonic) part of a magnitude spectrogram [bins, frames]: a soft mask from a median over time
    (held notes) against a median over frequency (drum hits), the median-filter split librosa.effects.harmonic uses."""
    H, P = _median(S, time_k, 1) ** 2, _median(S, freq_k, 0) ** 2
    return S * H / np.maximum(H + P, 1e-20)


def chroma(y: np.ndarray, sr: float, hop: int, fmin: float = 55.0, fmax: float = 4200.0) -> np.ndarray:
    """[12, frames every `hop`] pitch-class energy (C first) of the harmonic part, each frame scaled to its loudest
    class. Each STFT bin (n_fft 8192, step hop / 2) goes to the semitone it lies on, weighted down towards the edge
    between two semitones (where leakage sits); drums are taken out first (harmonic_part, ~0.4 s × ~80 Hz medians)."""
    n_fft, step = 8192, hop // 2
    f = fft_frequencies(sr, n_fft)
    sel = (f >= fmin) & (f <= fmax)
    rows = np.flatnonzero(sel)
    lo, hi = max(0, rows[0] - 15), rows[-1] + 16                         # room for the frequency median
    S = harmonic_part(np.abs(stft(y, n_fft, step))[lo:hi], time_k=int(0.4 * sr / step) | 1, freq_k=31)
    S = S[rows - lo]
    p = 12 * np.log2(f[sel] / 440.0) + 69
    near = np.round(p).astype(int)
    bank = np.zeros((12, sel.sum()))
    bank[near % 12, np.arange(sel.sum())] = np.maximum(0.0, 1.0 - 2.0 * np.abs(p - near))
    c = bank @ S
    cp = np.pad(c, ((0, 0), (1, 1)), mode="edge")                      # back to one frame per hop, smoothed
    c = (0.5 * cp[:, 1:-1] + 0.25 * cp[:, :-2] + 0.25 * cp[:, 2:])[:, ::2]
    return c / np.maximum(c.max(axis=0, keepdims=True), 1e-12)


def closing_1x3(mask: np.ndarray) -> np.ndarray:
    """Binary closing along the last axis with a 3-wide line (outside the array counts as empty)."""
    def shift(m, k):
        out = np.zeros_like(m)
        if k > 0:
            out[..., k:] = m[..., :-k]
        else:
            out[..., :k] = m[..., -k:]
        return out
    d = mask | shift(mask, 1) | shift(mask, -1)
    return d & shift(d, 1) & shift(d, -1)


def label(mask: np.ndarray) -> tuple[np.ndarray, int]:
    """Connected regions of a 2-D mask, touching sideways or diagonally -> (labels from 1 in raster order, count)."""
    runs = []                                                            # (row, start, end) of each horizontal run
    for r, row in enumerate(np.asarray(mask, bool)):
        e = np.diff(np.concatenate([[0], row.astype(np.int8), [0]]))
        runs += [(r, a, b) for a, b in zip(np.flatnonzero(e == 1), np.flatnonzero(e == -1))]
    parent = list(range(len(runs)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    by_row: dict = {}
    for i, (r, a, b) in enumerate(runs):
        for k in by_row.get(r - 1, []):
            if runs[k][1] <= b and a <= runs[k][2]:                      # overlap incl. diagonal touch
                parent[root(k)] = root(i)
        by_row.setdefault(r, []).append(i)
    out, ids = np.zeros(np.shape(mask), int), {}
    for i, (r, a, b) in enumerate(runs):
        out[r, a:b] = ids.setdefault(root(i), len(ids) + 1)
    return out, len(ids)
