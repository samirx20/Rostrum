"""Clash finder: where one stem buries another in a frequency band, both loud there at the same time.

Each stem is cut into 1/3-octave bands over time (level in dB, a full-scale sine reads about -3). A cell is a clash for a
pair when both stems stand above the floor and within `within_db` of each other (the quieter one is then hard to hear
under the louder). Touching cells merge into spans: when, which band range, which two tracks, how much each stands over
the other. Only spans where one stands at least `min_over_db` (3) over the other are kept: two parts at the same level
share a band without a problem (a balanced keys, pad and bass loop has no real clash), and the worst is the one burying
the other by the most. Spans come back ranked by that gap.

The floor follows the mix: FLOOR_UNDER dB under the loudest band level of all stems (its 99th percentile), so making
the whole mix louder or quieter changes no clash; a fixed `floor_db` (absolute) can still be given."""
from __future__ import annotations

from itertools import combinations

import numpy as np

from ..listen.core import load, mono, num
from ..listen.dsp import fft_frequencies, resample, stft
from ..listen.dsp_events import closing_1x3, label
from ..listen.memo import remembered

N_FFT, HOP = 4096, 2048
CENTRES = [1000.0 * 2 ** (k / 3) for k in range(-13, 13)]          # 50 Hz … 16 kHz
EDGES = [(c * 2 ** (-1 / 6), c * 2 ** (1 / 6)) for c in CENTRES]
MAX_STEMS = 12
FLOOR_UNDER = 40.0
MIN_OVER_DB = 3.0


def floor_for(levels: dict) -> float:
    """The default floor: FLOOR_UNDER dB under the loudest band level (99th percentile over every stem's cells)."""
    top = max(float(np.percentile(v, 99)) for v in levels.values()) if levels else 0.0
    return top - FLOOR_UNDER


@remembered
def band_levels(wav, sr_to: int | None = None):
    """(levels dB [bands, frames], sample rate): the stem's 1/3-octave band levels over time."""
    y, sr = load(wav)
    m = mono(y)
    if sr_to and sr != sr_to:
        m, sr = resample(m, sr, sr_to), sr_to
    win = np.hanning(N_FFT)
    amp = np.abs(stft(m, N_FFT, HOP, window=win)) * 2 / win.sum()
    f = fft_frequencies(sr, N_FFT)
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


def find_clashes(levels: dict, within_db: float = 6.0, floor_db: float = -45.0, min_len: float = 0.3,
                 hop_s: float = HOP / 48000, min_over_db: float = MIN_OVER_DB):
    """-> (spans, maps): spans (most serious first) as dicts and maps {(a, b): bool [bands, frames]} of the cells kept."""
    spans, maps = [], {}
    for a, b in combinations(levels, 2):
        la, lb = levels[a], levels[b]
        cells = (la >= floor_db) & (lb >= floor_db) & (np.abs(la - lb) <= within_db)
        cells = closing_1x3(np.pad(cells, ((0, 0), (1, 1))))[:, 1:-1]
        lab, count = label(cells)
        keep = np.zeros_like(cells)
        for i in range(1, count + 1):
            rows, cols = np.nonzero(lab == i)
            dur = (cols.max() - cols.min() + 1) * hop_s
            if dur < min_len:
                continue
            d = (la - lb)[rows, cols]
            if abs(float(d.mean())) < min_over_db:
                continue
            keep[lab == i] = True
            spans.append({
                "start_s": num(cols.min() * hop_s, 2), "end_s": num((cols.max() + 1) * hop_s, 2),
                "band_hz": [num(EDGES[rows.min()][0], 0), num(EDGES[rows.max()][1], 0)], "tracks": [a, b],
                f"{a}_over_{b}_db": num(d.mean(), 1), f"{b}_over_{a}_db": num(-d.mean(), 1),
                "buried_track": b if d.mean() > 0 else a, "buried_by_db": num(abs(d.mean()), 1),
                "level_db": {a: num(la[rows, cols].mean(), 1), b: num(lb[rows, cols].mean(), 1)},
                "severity": num(float(np.sum(np.minimum(la, lb)[rows, cols] - floor_db)) * hop_s, 1)})
        maps[(a, b)] = keep
    spans.sort(key=lambda s: (-s["buried_by_db"], -s["severity"]))
    return spans, maps


def line(span: dict) -> str:
    a, b = span["tracks"]
    d = span[f"{a}_over_{b}_db"]
    who = f"{a if d > 0 else b} {abs(d):.1f} dB over {b if d > 0 else a}"
    return f"{span['start_s']:g}–{span['end_s']:g} s, {span['band_hz'][0]:.0f}–{span['band_hz'][1]:.0f} Hz: {who}"
