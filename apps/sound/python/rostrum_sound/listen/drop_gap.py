"""drop_gap: are the drums really gone in a drop's gap, as a listener hears it?

The old drop check only asked whether the last beat came early; it never looked inside the gap, so a lo-fi drop whose
drums kept rattling through 24–26 s passed (sound-script-first brief 5: judged "drums keep playing", 5.6 dB down).
Chords keep sounding under a drop, so total level says little: this measures the drums' own part, the percussive part
of the spectrogram (median over frequency against median over time, the split librosa's HPSS uses) above 4 kHz, where
hats, snare crack and cymbals live and keys hardly reach. The gap against the 2 s before it: benchmark drops that read
measure 18–65 dB down, the one judged not to read 9 dB.

A kick left in the gap lives under the bass, which keeps playing, so the mix alone cannot hear it (the next round's lo-fi
run 1: a kick at 24.3 and 25.6 s, 26 dB down over 4 kHz and judged "drums keep playing"). When the render has the drum
tracks' own files (`drums`: their stems), the gap is read there, at every frequency: the drums' level in the gap against
the 2 s before, under STEM_GAP_DB is a fault. Only the drum tracks count, so a vinyl crackle on its own track never does."""
from __future__ import annotations

import numpy as np

from .core import num
from .dsp import fft_frequencies, stft
from .dsp_events import _median

STEM_GAP_DB = 20.0     # the drum tracks themselves: the gap's loudest 50 ms under this far below the 2 s before's: a hit is still there
TAIL_S = 0.25          # a hit on the drop itself (the last one) rings this long into the gap: read the drum tracks after it
GAP_DB = 14.0          # the drums' part in the gap under this far below the 2 s before: still heard
DEFAULT_GAP_S = 1.5    # no return given ("drums back" / end): the gap read is this long
RETURN_WITHIN_S = 16.0 # an entry this soon after a drop is its return
BEFORE_S = 2.0
DRUM_HZ = 4000.0
QUIET_DB = -60.0       # the 2 s before carry no drums worth measuring (their part under this): nothing to compare
_N, _HOP, _K = 1024, 256, 17


def _percussive(m, sr, t0, t1):
    """The percussive part above DRUM_HZ of m[t0:t1] (power per frame) and its frame times."""
    seg = m[max(0, int(t0 * sr)):int(t1 * sr)].astype(np.float64)
    S = np.abs(stft(seg, _N, _HOP))
    H, P = _median(S, _K, 1) ** 2, _median(S, _K, 0) ** 2
    perc = (S * P / np.maximum(H + P, 1e-20)) ** 2
    keep = fft_frequencies(sr, _N) >= DRUM_HZ
    return perc[keep].sum(axis=0), max(0.0, t0) + np.arange(S.shape[1]) * _HOP / sr


def measure(m, sr, at, end) -> dict | None:
    """{down_db: the drums' part in at..end against the 2 s before, before_db: its level before}; None when the file
    is too short or the 2 s before carry no drums (QUIET_DB)."""
    p, t = _percussive(m, sr, at - BEFORE_S - 0.5, end + 0.5)
    pre, gap = (t >= at - BEFORE_S) & (t < at - 0.03), (t >= at + 0.05) & (t < end - 0.05)
    if not pre.any() or not gap.any():
        return None
    db = lambda w: 10 * np.log10(float(p[w].mean()) + 1e-20)
    if db(pre) < QUIET_DB:
        return None
    return {"down_db": num(db(pre) - db(gap), 1), "before_db": num(db(pre), 1)}


def stem_measure(drums, at, end) -> dict | None:
    """{down_db, before_db} of the drum tracks' own files summed (every frequency), the gap against the 2 s before;
    None when they cannot be read or carry nothing before the drop."""
    from .core import load, mono
    total, sr = None, None
    for f in drums or []:
        y, sr = load(f)
        m = mono(y).astype(np.float64)
        total = m if total is None else total[:len(m)] + m[:len(total)]
    if total is None:
        return None
    seg = lambda a, b: total[max(0, int(a * sr)):max(0, int(b * sr))]
    lv = lambda x: 10 * np.log10(float(np.mean(x ** 2)) + 1e-20) if len(x) else None
    pre, gap = lv(seg(at - BEFORE_S, at - 0.03)), lv(seg(at + TAIL_S, end - 0.05))
    if pre is None or gap is None or pre < QUIET_DB:
        return None
    # a hit in the gap is heard by its loudest moment, not its average: the gap's loudest 50 ms against the 2 s before's
    n = max(1, int(0.05 * sr))
    peak = lambda x: max(lv(x[i:i + n]) for i in range(0, max(1, len(x) - n + 1), n))
    return {"down_db": num(peak(seg(at - BEFORE_S, at - 0.03)) - peak(seg(at + TAIL_S, end - 0.05)), 1), "before_db": num(pre, 1)}


def return_of(moments, at) -> float | None:
    """The drop's return: its own `end`, else the first entry ("drums back") after it within RETURN_WITHIN_S."""
    later = [float(mo["at"]) for mo in moments if mo.get("kind") == "entry" and at < float(mo["at"]) <= at + RETURN_WITHIN_S]
    return min(later) if later else None


def faults(m, sr, at, end, drums=None) -> list[dict]:
    """`drums_in_gap` when the drums in the gap (at..end, or DEFAULT_GAP_S when end is None) are under the threshold
    down: the drum tracks' own files when given (STEM_GAP_DB, every frequency), else the mix over 4 kHz (GAP_DB)."""
    assumed = end is None
    end = at + DEFAULT_GAP_S if assumed else end
    d = stem_measure(drums, at, end) if drums else None
    on, limit = ("tracks", STEM_GAP_DB) if d is not None else ("mix", GAP_DB)
    d = d if d is not None else measure(m, sr, at, end)
    if d is None or d["down_db"] >= limit:
        return []
    return [{"kind": "drums_in_gap", "at_s": at, "measured": {**d, "to_s": num(end, 2), "gap_assumed": assumed, "on": on}}]


def words(f) -> str:
    t, d = f["at_s"], f["measured"]
    span = (f"the {DEFAULT_GAP_S:g} s after it (no return given: pass end, or an entry / a \"drums back\" marker)"
            if d["gap_assumed"] else f"{t:g}–{d['to_s']:g} s")
    what = ("the drum tracks' own sound (every frequency, kick included, at its loudest moment)" if d.get("on") == "tracks" else
            "their part in the mix (hats, snare, cymbals: the percussive part over 4 kHz)")
    need = STEM_GAP_DB if d.get("on") == "tracks" else 18
    return (f"drums still heard in the drop at {t:.2f} s: {what} is only {d['down_db']:g} dB under the 2 s before in {span} "
            f"(drops that read: {need:g} dB or more); "
            "end every drum note, roll and cymbal ring before the drop and start none until the return; in a script "
            f"m = moment(\"drums out\", at={t:g}); m.stop(<every drum and percussion track>, until=<the return>) clears "
            "them, ghost notes and fills included")
