"""end_level: the numbers of how a file ends, for end_check.py. Levels are 50 ms blocks of the louder channel, in dB
under the loudest 3 s (round sound-endings DIAGNOSIS.md: the judged dead air sat at -50 to -55 dBFS, above any absolute
-60 line), and the silences are counted up to the asked end (the song's length or end marker), not the file's end: a
ring may run up to 2 s past the length.

    measure(wav, end_s=None) -> {peak_db, file_s, end_s, dead_s, heard_until_s, quiet_s, quiet_from_s,
                                 last_max_db, last_db, loop_min_db, level_at(t)} | None
(the *_db under-the-loudest values are negative: -30 = 30 dB under it)
"""
from __future__ import annotations

import numpy as np

from .core import load

BLOCK_S = 0.05
PEAK_S = 3.0
LAST_S = 0.5           # the file's last stretch read for a chop or a loop's drop
DECLICK_S = 0.2        # a loop's own last 0.2 s may ramp down (a de-click): not a drop
DEAD_UNDER_DB = 50.0   # under the loudest by this: nothing is heard
QUIET_UNDER_DB = 30.0  # under the loudest by this: near-silence, the piece has ended for the ear


def _since(b, step, line) -> float:
    """The end (s) of the last block above `line`; 0 when none is."""
    over = np.nonzero(b > line)[0]
    return float((over[-1] + 1) * step) if over.size else 0.0


def measure(wav, end_s: float | None = None) -> dict | None:
    y, sr = load(wav)
    a = np.asarray(y, dtype=np.float64).reshape(len(y), -1)
    n = max(1, int(BLOCK_S * sr))
    k = len(a) // n
    last_n = int(LAST_S / BLOCK_S)
    if k < 2 * last_n:
        return None
    e = (a[:k * n].reshape(k, n, -1) ** 2).mean(axis=1).max(axis=1)
    step, total = n / sr, len(a) / sr
    w = min(k, int(PEAK_S / BLOCK_S))
    peak = 10 * np.log10(max(np.convolve(e, np.ones(w) / w, "valid").max(), 1e-20))
    b = 10 * np.log10(np.maximum(e, 1e-20)) - peak                     # every block under the loudest 3 s
    end = min(end_s, total) if end_s and end_s > 0 else total
    heard, qfrom = _since(b, step, -DEAD_UNDER_DB), _since(b, step, -QUIET_UNDER_DB)
    tail = b[-last_n:]

    def level_at(t: float) -> float:
        """The level of the 0.25 s before `t`, under the loudest (dB)."""
        i = int(t / step)
        seg = e[max(0, i - 5):max(1, i)]
        return float(10 * np.log10(max(seg.mean(), 1e-20)) - peak)

    return {"peak_db": float(peak), "file_s": total, "end_s": end, "dead_s": max(0.0, end - heard), "heard_until_s": heard,
            "quiet_s": max(0.0, end - qfrom), "quiet_from_s": qfrom, "last_max_db": float(tail.max()),
            "last_db": float(tail[-1]), "loop_min_db": float(tail[:last_n - int(DECLICK_S / BLOCK_S)].min()),
            "level_at": level_at}
