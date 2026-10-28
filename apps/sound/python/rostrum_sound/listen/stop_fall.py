"""stop_fall: how much of the band really stops at a stop, against the 2 s before it.

The blurred-stop check compares the second after a stop with the stop's own 0.25 s, which a ringing accent chord
answers either way. A listener compares with the groove before: is the 0.3–1.5 s after quieter than the 2 s before,
and does the bass and kick's pulse (onsets in 40–250 Hz) go on as before? Measured on the benchmark (brief 3, stop at
36 s): the band that kept walking keeps 107 % of its low pulse; the sound after an accent is louder than the 2 s
before in every version, the judged-best too (its piano tag), so these numbers name what keeps going, they do not by
themselves decide the fault."""
from __future__ import annotations

import numpy as np

from .core import num
from .dsp import fft_frequencies, stft
from .dsp_events import find_peaks

BEFORE_S = 2.0
AFTER = (0.3, 1.5)         # the level after: past the accent's own attack
PULSE_AFTER = (0.3, 2.5)   # the pulse after: long enough for a slow walk's notes
LOW_HZ = (40.0, 250.0)
_N, _HOP = 2048, 256


def _db(seg):
    return 10 * np.log10(float(np.mean(seg.astype(np.float64) ** 2)) + 1e-12)


def _low_pulse(m, sr, at) -> float | None:
    """The bass and kick's onset strength per second in PULSE_AFTER against the BEFORE_S before (1 = goes on as before)."""
    t0 = max(0.0, at - BEFORE_S - 0.2)
    seg = m[int(t0 * sr):int((at + PULSE_AFTER[1] + 0.2) * sr)].astype(np.float64)
    S = np.abs(stft(seg, _N, _HOP)) ** 2
    f = fft_frequencies(sr, _N)
    d = 10 * np.log10(S[(f >= LOW_HZ[0]) & (f < LOW_HZ[1])] + 1e-12)
    d = np.maximum(d, d.max() - 60)
    fl = np.concatenate([[0.0], np.maximum(0.0, np.diff(d, axis=1)).mean(axis=0)])
    t = t0 + np.arange(len(fl)) * _HOP / sr
    pk = find_peaks(fl, distance=max(1, int(0.1 * sr / _HOP)))
    pre = [p for p in pk if at - BEFORE_S <= t[p] < at - 0.05]
    if not pre:
        return None
    typ = float(np.median(fl[pre]))
    strong = lambda ps: sum(float(fl[p]) for p in ps if fl[p] >= 0.5 * typ)
    aft = [p for p in pk if at + PULSE_AFTER[0] <= t[p] < at + PULSE_AFTER[1]]
    rate_pre = strong(pre) / (BEFORE_S - 0.05)
    return strong(aft) / (PULSE_AFTER[1] - PULSE_AFTER[0]) / rate_pre if rate_pre > 0 else None


def measure(m, sr, at) -> dict:
    """{under_before_db: the 0.3–1.5 s after under the 2 s before (negative = louder after), low_pulse_kept: the bass
    and kick's pulse after as a share of before (None: no low pulse before)}."""
    cut = lambda s0, s1: m[max(0, int((at + s0) * sr)):max(1, int((at + s1) * sr))]
    kept = _low_pulse(m, sr, at)
    return {"under_before_db": num(_db(cut(-BEFORE_S, -0.05)) - _db(cut(*AFTER)), 1),
            "low_pulse_kept": num(kept, 2) if kept is not None else None}


def why(d) -> list[str]:
    """What keeps going after the stop, in words (from measure's numbers in a fault's `measured`)."""
    out = []
    if d.get("low_pulse_kept") is not None and d["low_pulse_kept"] >= 0.7:
        out.append(f"the bass and kick keep {100 * d['low_pulse_kept']:.0f} % of their pulse in the 2 s after")
    if d.get("under_before_db") is not None and d["under_before_db"] < 6:
        out.append(f"the 0.3–1.5 s after is {d['under_before_db']:+g} dB under the 2 s before")
    return out


def script_fix(t) -> str:
    return (f"in a script m = moment(\"stop\", at={t:g}); m.rest(piano, bass, drums, before=0.4); m.stop(bass, drums, "
            "until=<the tag's end>) ends every part but the tag")
