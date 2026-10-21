"""Pictures for the beats and pitch looks (matplotlib, text large enough to read at once)."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from ..doc.keys import NAMES
from ..listen.core import load, mono

OK, WARN, BAD, GRID, INK = "#2a9d4b", "#e08a00", "#d1362f", "#3b6fd4", "#222222"
STATUS_COLOUR = {"ok": OK, "late": WARN, "early": WARN, "out_of_tune": WARN, "wrong_octave": BAD, "wrong_note": BAD, "missing": BAD}


def _envelope(m, sr, n=2400):
    k = max(1, len(m) // n)
    seg = m[: len(m) // k * k].reshape(-1, k)
    return np.arange(seg.shape[0]) * k / sr, seg.min(axis=1), seg.max(axis=1)


def beats_picture(png, wav, beats, downbeats, onsets, doc_beats=None, title="", limit_ms=40.0):
    """Waveform with the beats (blue), downbeats (bold), the document's beats (a strip on top) and each onset as a
    triangle: green within `limit_ms` of the grid, orange within twice that, red beyond. `onsets` [(time, off_ms)]."""
    y, sr = load(wav)
    t, lo, hi = _envelope(mono(y), sr)
    fig, ax = plt.subplots(figsize=(16, 6), dpi=100)
    ax.fill_between(t, lo, hi, color="#9aa5b1", lw=0)
    for b in beats:
        ax.axvline(b, color=GRID, lw=1, alpha=0.5)
    for b in downbeats:
        ax.axvline(b, color=GRID, lw=3, alpha=0.9)
    if doc_beats is not None:
        ax.vlines(doc_beats, 0.92, 1.0, color=INK, lw=1.5, transform=ax.get_xaxis_transform(), label="document beats")
    for ts, off in onsets:
        c = OK if abs(off) <= limit_ms else WARN if abs(off) <= 2 * limit_ms else BAD
        ax.plot(ts, -0.97, marker="^", color=c, ms=8, clip_on=False)
    ax.set_ylim(-1.05, 1.05)
    ax.set_xlim(0, len(mono(y)) / sr)
    ax.set_xlabel("time (seconds)", fontsize=16)
    ax.set_ylabel("level", fontsize=16)
    ax.tick_params(labelsize=14)
    ax.set_title(title or "beats (blue; bold = downbeat guess), onsets: green on grid, orange close, red off", fontsize=17)
    fig.tight_layout()
    fig.savefig(png)
    plt.close(fig)
    return str(png)


def pitch_picture(png, times, midi, written=None, rows=None, title=""):
    """The pitch curve over a note grid, the written notes as bars, a coloured dot at each written note's start by status."""
    fig, ax = plt.subplots(figsize=(16, 8), dpi=100)
    ok = ~np.isnan(midi)
    span = (np.nanmin(midi), np.nanmax(midi)) if ok.any() else (48, 72)
    ks = [m["midis"] for m in (written or [])]
    lo = min([span[0]] + [min(k) for k in ks]) - 2
    hi = max([span[1]] + [max(k) for k in ks]) + 2
    for k in range(int(np.floor(lo)), int(np.ceil(hi)) + 1):
        ax.axhline(k, color="#f1f3f5" if "#" in NAMES[k % 12] else "#d9dde2", lw=1, zorder=0)
    for w in written or []:
        for k in w["midis"]:
            ax.broken_barh([(w["start"], w["end"] - w["start"])], (k - 0.4, 0.8), facecolors="#bcd0f2", edgecolors="#6f93d6", zorder=1)
    ax.plot(times, midi, color=INK, lw=2.2, zorder=3, label="heard pitch")
    for r in rows or []:
        ax.plot(r["start_s"], r["target"], "o", color=STATUS_COLOUR[r["status"]], ms=9, zorder=4)
    ax.set_ylim(lo, hi)
    ax.set_yticks(range(int(np.ceil(lo)), int(np.floor(hi)) + 1))
    ax.set_yticklabels([f"{NAMES[k % 12]}{k // 12 - 1}" for k in range(int(np.ceil(lo)), int(np.floor(hi)) + 1)], fontsize=11)
    ax.set_xlim(times[0], times[-1])
    ax.set_xlabel("time (seconds)", fontsize=16)
    ax.set_ylabel("note", fontsize=16)
    ax.tick_params(axis="x", labelsize=14)
    ax.set_title(title or ("pitch (line) over the written notes (bars); dots: green ok, orange timing / tuning, red wrong or missing" if written else "pitch (line) on a note grid"), fontsize=16)
    fig.tight_layout()
    fig.savefig(png)
    plt.close(fig)
    return str(png)
