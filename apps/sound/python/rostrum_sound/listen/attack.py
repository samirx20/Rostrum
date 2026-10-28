"""attack: how hard a moment strikes, as a listener hears it in the finished (limited) file.

The ear hears a hit as the whole spectrum jumping within a few milliseconds, the bright crack most of all: a low boom
that swells in over 40 ms, or a hit the bed before it is as loud as, reads as "a normal note" however loud its meter
reads. The old mel check (40 ms frames, most bands under 1 kHz) called a low timpani-and-brass hit 2.9x a normal note
while listeners and the blind benchmark's analyser heard 1.0x (sound-gaps brief 2). So this measures the rise per
frequency in dB over ~21 ms frames, every Hz counted alike (so the bright attack weighs as the ear weighs it), and
gives the hit against the piece's typical onset, against the onsets of the 2 s before it, its bright part (2 kHz up)
alone and the loudness jump from the bed into the hit."""
from __future__ import annotations

import numpy as np

from .bs1770 import integrated
from .core import load, mono, num
from .dsp import fft_frequencies, stft
from .dsp_events import find_peaks
from .memo import remembered

FRAME_S = 0.021            # ~21 ms frames: short enough that a sharp attack is one big step, not smeared over two
FLOOR_DB = 80.0            # rises from under 80 dB below the loudest moment are noise, not notes
BRIGHT_HZ = 2000.0         # the crack of an attack: snare, crash, a hard piano or brass stab
NEAR_S = 0.08              # the moment's own onset: the strongest within this of the asked time
BED_S = 2.0                # "the bed around it": the onsets of the 2 s before
JUMP_BEFORE_S = 1.5        # loudness jump: the 0.4 s from the hit against the 1.5 s before it
BUILD_S = 3.0              # headroom: the build's peak in the 3 s before against the file's loudest peak


def _flux(S, keep):
    d = 10 * np.log10(S[keep] + 1e-20)
    d = np.maximum(d, d.max() - FLOOR_DB)
    return np.concatenate([[0.0], np.maximum(0.0, np.diff(d, axis=1)).mean(axis=0)])


def _near_max(x, p, k=2):
    return float(x[max(0, p - k):p + k + 1].max())


@remembered
def curves(wav) -> dict:
    """The file's attack curves (whole spectrum and bright part), frame times, onset frames and their typical strengths."""
    y, sr = load(wav)
    m = mono(y)
    n = 1 << int(round(np.log2(FRAME_S * sr)))
    hop = n // 8
    S = np.abs(stft(m, n, hop)) ** 2
    f = fft_frequencies(sr, n)
    env, bright = _flux(S, f > 0), _flux(S, f >= BRIGHT_HZ)
    t = np.arange(len(env)) * hop / sr
    k = max(3, int(sr / hop) | 1)
    run = np.median(np.lib.stride_tricks.sliding_window_view(np.pad(env, k // 2, mode="edge"), k), axis=1)[:len(env)]
    pk = find_peaks(env, distance=max(1, int(0.05 * sr / hop)))
    pk = pk[env[pk] > run[pk] + 0.5 * env.std()]
    typ = float(np.median(env[pk])) if len(pk) else float(env.max() or 1.0)
    btyp = float(np.median([_near_max(bright, q) for q in pk])) if len(pk) else float(bright.max() or 1.0)
    return {"env": env, "bright": bright, "t": t, "pk": pk, "typ": max(typ, 1e-9), "btyp": max(btyp, 1e-9)}


def strike(wav, at, near=NEAR_S) -> dict | None:
    """How the moment at `at` strikes: None when no onset starts within `near`, else {at_s, times_typical (against the
    piece's typical onset), rank (1 = the strongest in the file), onsets, times_bed (against the typical onset of the
    2 s before), bright_x (its 2 kHz-up rise against the bright part of the piece's typical onset), jump_lu (the 0.4 s from it
    against the 1.5 s before), build_peak_db (the highest sample of the 3 s before, dBFS), file_peak_db (the file's),
    headroom_db (how far the build's peak sits under the file's: near 0 = the build already reaches the ceiling)}."""
    c = curves(wav)
    env, t, pk, typ = c["env"], c["t"], c["pk"], c["typ"]
    mine = [p for p in pk if abs(t[p] - at) <= near]
    if not mine:
        return None
    p = max(mine, key=lambda q: env[q])
    h = float(env[p])
    bed = [q for q in pk if at - BED_S <= t[q] < t[p] - 0.05]
    bed_typ = float(np.median(env[bed])) if bed else 0.0
    y, sr = load(wav)
    cut = lambda s0, s1: integrated(y[max(0, int(s0 * sr)):max(1, int(s1 * sr))], sr)
    hit_lu, bed_lu = cut(t[p], t[p] + 0.4), cut(t[p] - JUMP_BEFORE_S, t[p] - 0.05)
    return {"at_s": num(t[p], 2), "times_typical": num(h / typ, 1), "rank": int((env[pk] > h).sum()) + 1, "onsets": len(pk),
            "times_bed": num(h / bed_typ, 1) if bed_typ > 0 else None, "bright_x": num(_near_max(c["bright"], p) / c["btyp"], 1),
            "jump_lu": num(hit_lu - bed_lu, 1) if bed_lu > -70 else None, **_headroom(y, sr, float(t[p]))}


def _peak_db(seg) -> float:
    return 20 * float(np.log10(float(np.max(np.abs(seg))) + 1e-12)) if seg.size else -120.0


def _headroom(y, sr, at) -> dict:
    build = _peak_db(y[max(0, int((at - BUILD_S) * sr)):max(1, int((at - 0.05) * sr))])
    top = _peak_db(y)
    return {"build_peak_db": num(build, 1), "file_peak_db": num(top, 1), "headroom_db": num(top - build, 1)}
