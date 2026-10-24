"""Steady tones in a spectrogram, and which of them are hum. A held note and hum both draw a steady narrow
line; what makes a line *unwanted* is what a note never does: its level hardly moves over the whole file
(a note swells, decays, follows the dynamics), it is still there in the quietest moments (a note stops when
the music does), and mains hum is a series: lines on several multiples of 50 or 60 Hz together. A line is hum
only when its level is flat and it belongs to such a series (at least two multiples of the same mains frequency
among the steady lines); a lone steady line, however flat or long-lived (a held sub-bass note), is a held tone,
reported with its note name, so an agent can tell a cello's held D from a buzz.
"""
from __future__ import annotations

import numpy as np

from .core import num
from .dsp import fft_frequencies, hz_to_note

N_FFT = 4096
LO_HZ, HI_HZ = 40.0, 1200.0
PROMINENCE_DB = 12.0     # a line stands this far over the bins around it...
STEADY = 0.8             # ...in at least this share of the frames
FLAT_DB = 3.0            # hum: its level spreads less than this (10th to 90th percentile)
QUIET_SHARE = 0.15       # the quietest frames, where the music has stopped or is softest
MAINS_TOLERANCE = 0.01   # within 1 % (and at least 3.5 Hz) of a multiple of 50 or 60 Hz
MAINS_LINES = 2          # a hum series: at least this many different multiples of one mains frequency


def _mains(f: float) -> tuple[int, int] | None:
    """(mains Hz, which multiple) when `f` sits on a multiple of 50 or 60 Hz."""
    for base in (50, 60):
        k = round(f / base)
        if 1 <= k <= 24 and abs(f - k * base) <= max(3.5, MAINS_TOLERANCE * f):
            return base, k
    return None


def _refine(D, present, ff, i) -> float:
    """The line's frequency between bins: a parabola through its mean level and its neighbours' (bins are ~12 Hz)."""
    if i == 0 or i == len(ff) - 1:
        return float(ff[i])
    on = present[i]
    a, b, c = (float(D[j][on].mean()) if on.any() else float(D[j].mean()) for j in (i - 1, i, i + 1))
    shift = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) < 0 else 0.0
    return float(ff[i] + max(-0.5, min(0.5, shift)) * (ff[1] - ff[0]))


def steady_tones(S, sr, max_lines=8) -> list[dict]:
    """[{freq_hz, note, strength_db, steady_pct, level_spread_db, in_quiet, mains_hz, is_hum, why}], strongest first.
    `S` is a power spectrogram (n_fft 4096)."""
    f = fft_frequencies(sr, N_FFT)
    full = 10 * np.log10(np.maximum(S, 1e-20))
    # Neighbours: 3 to 10 bins each side, outside the window's own main lobe (±2 bins), on the whole spectrum.
    near = [d for d in range(-10, 11) if abs(d) >= 3]
    pad = np.pad(full, ((10, 10), (0, 0)), mode="edge")
    around = np.median(np.stack([pad[10 + d:10 + d + full.shape[0]] for d in near]), axis=0)
    sel = (f >= LO_HZ) & (f <= HI_HZ)
    D, ff, lift = full[sel], f[sel], (full - around)[sel]
    present = lift >= PROMINENCE_DB
    steady = present.mean(axis=1)
    strength = np.median(lift, axis=1)
    level = D.mean(axis=1)
    frame_db = 10 * np.log10(np.maximum(S.sum(axis=0), 1e-20))
    quiet = frame_db <= np.quantile(frame_db, QUIET_SHARE)
    cand = [i for i in range(len(ff)) if steady[i] >= STEADY                      # the loudest bin of its line
            and (i == 0 or level[i] >= level[i - 1]) and (i == len(ff) - 1 or level[i] >= level[i + 1])]
    cand.sort(key=lambda i: -strength[i])
    freqs = {i: _refine(D, present, ff, i) for i in cand}
    series: dict = {}                                    # mains Hz -> the multiples found among all the steady lines
    for fr in freqs.values():
        m = _mains(fr)
        if m:
            series.setdefault(m[0], set()).add(m[1])
    out = []
    for i in cand[:max_lines]:
        on = D[i][present[i]]
        spread = float(np.percentile(on, 90) - np.percentile(on, 10)) if on.size else 0.0
        in_quiet = bool(present[i][quiet].mean() >= STEADY) if quiet.any() else False
        freq = freqs[i]
        m = _mains(freq)
        mains = m[0] if m and len(series[m[0]]) >= MAINS_LINES else None
        flat = spread < FLAT_DB
        is_hum = flat and mains is not None
        why = ("flat level" if flat else f"level moves {spread:.0f} dB (played)") + \
              (f", on the {mains} Hz mains series" if mains else "") + \
              (", still there in the quietest moments" if in_quiet else ", gone in the quietest moments")
        out.append({"freq_hz": num(freq, 1), "note": hz_to_note(freq), "strength_db": num(strength[i], 1),
                    "steady_pct": num(100 * steady[i], 0), "level_spread_db": num(spread, 1), "in_quiet": in_quiet,
                    "mains_hz": mains, "is_hum": is_hum, "why": why})
    return out
