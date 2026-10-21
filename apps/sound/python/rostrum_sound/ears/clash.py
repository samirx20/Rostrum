"""Clash finder: where two stems are both loud in the same frequency band at the same time.

Each stem is cut into 1/3-octave bands over time (level in dB, a full-scale sine reads about -3). A cell is a clash for a
pair when both stems stand above `floor_db` and within `within_db` of each other (the quieter one is then hard to hear
under the louder). Touching cells merge into spans: when, which band range, which two tracks, how much each stands over
the other."""
from __future__ import annotations

from itertools import combinations

import librosa
import numpy as np
from scipy.ndimage import binary_closing, label

from ..listen.core import load, mono, num

N_FFT, HOP = 4096, 2048
CENTRES = [1000.0 * 2 ** (k / 3) for k in range(-13, 13)]          # 50 Hz … 16 kHz
EDGES = [(c * 2 ** (-1 / 6), c * 2 ** (1 / 6)) for c in CENTRES]
MAX_STEMS = 12


def band_levels(wav, sr_to: int | None = None):
    """(levels dB [bands, frames], sample rate): the stem's 1/3-octave band levels over time."""
    y, sr = load(wav)
    m = mono(y)
    if sr_to and sr != sr_to:
        m, sr = librosa.resample(m, orig_sr=sr, target_sr=sr_to), sr_to
    win = np.hanning(N_FFT)
    amp = np.abs(librosa.stft(m, n_fft=N_FFT, hop_length=HOP, window=win)) * 2 / win.sum()
    f = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)
    bank = np.array([(f >= lo) & (f < hi) for lo, hi in EDGES], dtype=float)
    return 10 * np.log10(bank @ (amp ** 2) / 2 + 1e-12), sr


def loudest(stems: dict, n: int = MAX_STEMS) -> list:
    """The `n` loudest stems' tracks (whole-file RMS), loudest first: what the clash finder reads when none are picked."""
    rms = {t: float(np.sqrt(np.mean(np.square(mono(load(w)[0]))))) for t, w in stems.items()}
    return sorted(rms, key=rms.get, reverse=True)[:n]


def stem_levels(stems: dict):
    """({track: band levels}, seconds per frame), every stem at the first one's sample rate and cut to the shortest length."""
    out, sr = {}, None
    for tid, wav in stems.items():
        out[tid], sr = band_levels(wav, sr)
    n = min(v.shape[1] for v in out.values())
    return {k: v[:, :n] for k, v in out.items()}, HOP / sr


def find_clashes(levels: dict, within_db: float = 6.0, floor_db: float = -45.0, min_len: float = 0.3, hop_s: float = HOP / 48000):
    """-> (spans, maps): spans (most serious first) as dicts and maps {(a, b): bool [bands, frames]} of the cells kept."""
    spans, maps = [], {}
    for a, b in combinations(levels, 2):
        la, lb = levels[a], levels[b]
        cells = (la >= floor_db) & (lb >= floor_db) & (np.abs(la - lb) <= within_db)
        cells = binary_closing(np.pad(cells, ((0, 0), (1, 1))), structure=np.ones((1, 3)))[:, 1:-1]
        lab, count = label(cells, structure=np.ones((3, 3)))
        keep = np.zeros_like(cells)
        for i in range(1, count + 1):
            rows, cols = np.nonzero(lab == i)
            dur = (cols.max() - cols.min() + 1) * hop_s
            if dur < min_len:
                continue
            keep[lab == i] = True
            d = (la - lb)[rows, cols]
            spans.append({
                "start_s": num(cols.min() * hop_s, 2), "end_s": num((cols.max() + 1) * hop_s, 2),
                "band_hz": [num(EDGES[rows.min()][0], 0), num(EDGES[rows.max()][1], 0)], "tracks": [a, b],
                f"{a}_over_{b}_db": num(d.mean(), 1), f"{b}_over_{a}_db": num(-d.mean(), 1),
                "level_db": {a: num(la[rows, cols].mean(), 1), b: num(lb[rows, cols].mean(), 1)},
                "severity": num(float(np.sum(np.minimum(la, lb)[rows, cols] - floor_db)) * hop_s, 1)})
        maps[(a, b)] = keep
    spans.sort(key=lambda s: -s["severity"])
    return spans, maps


def line(span: dict) -> str:
    a, b = span["tracks"]
    d = span[f"{a}_over_{b}_db"]
    who = f"{a} and {b} level" if abs(d) < 1 else f"{a if d > 0 else b} {abs(d):.0f} dB over {b if d > 0 else a}"
    return f"{span['start_s']:g}–{span['end_s']:g} s, {span['band_hz'][0]:.0f}–{span['band_hz'][1]:.0f} Hz: {who}"
