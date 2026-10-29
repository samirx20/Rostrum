"""rise_gap: a build must rise into its peak, not die before it.

Canary 3E r8 task 8 ("a riser that peaks on the marker"): a snare roll ended at 3.9 s, then 2.5 s near silence
(-57 dBFS), then one kick on the peak at 7.0 s. The climax checks read the kick (a strong hit from silence) and passed
it. Here the LOOK_S before a climax or lift is read in 50 ms blocks against the build's loudest block there: a stretch
of GAP_S or more QUIET_DB under it, after sound in that window and running to within END_S of the moment, is a build
that stops before its peak. A short breath before the peak (moment.rest(..., before=0.4)) stays under GAP_S.

    faults(y, sr, at) -> [{"kind": "gap_before", "at_s", "measured": {"gap_s", "from_s", "under_db", "gap_dbfs"}}]
    words(fault) -> the fault in words, with the fix
"""
from __future__ import annotations

import numpy as np

from .core import num

LOOK_S = 4.0         # how far before the moment the build is read
BLOCK_S = 0.05
QUIET_DB = 24.0      # a block this far under the build's loudest block is quiet (a rest, not a quieter bar)
GAP_S = 0.6          # quiet this long before the peak is a gap (a breath before it: 0.3–0.5 s)
END_S = 0.15         # ...ending within this of the moment (the peak's own attack starts there)
LOUD_DBFS = -50.0    # the window must hold a build at all (under this everywhere: nothing to rise)


def faults(y, sr, at: float) -> list[dict]:
    m = np.asarray(y, np.float64).reshape(len(y), -1).mean(axis=1)
    n = max(1, int(BLOCK_S * sr))
    a, b = max(0, int((at - LOOK_S) * sr)), int((at - END_S + BLOCK_S) * sr)
    seg = m[a:min(b, len(m))]
    k = len(seg) // n
    if k < 4:
        return []
    lv = 10 * np.log10((seg[:k * n].reshape(k, n) ** 2).mean(axis=1) + 1e-12)
    top = float(lv.max())
    if top < LOUD_DBFS:
        return []
    quiet = lv < top - QUIET_DB
    if not quiet[-1]:
        return []                                   # it is still sounding into the moment
    first = k - int(np.argmin(quiet[::-1])) if not quiet.all() else 0
    if first == 0:
        return []                                   # quiet for the whole window: no build before it to die
    gap = (k - first) * BLOCK_S + END_S - BLOCK_S
    if gap < GAP_S:
        return []
    return [{"kind": "gap_before", "at_s": at, "measured": {
        "gap_s": num(gap, 2), "from_s": num((a / sr) + first * BLOCK_S, 2), "under_db": num(top - float(lv[first:].mean()), 1),
        "gap_dbfs": num(float(lv[first:].mean()), 1)}}]


def words(f) -> str:
    d, t = f["measured"], f["at_s"]
    return (f"the build dies before its peak at {t:.2f} s: {d['gap_s']:g} s near silence from {d['from_s']:g} s "
            f"({d['gap_dbfs']:g} dBFS, {d['under_db']:g} dB under the build); fix: keep the riser playing up to the "
            "peak: the roll, swell or build ends on the marker, not before it (count its notes to reach it: "
            "build_to(\"#peak\", over=..., parts=[...]) does); a breath before the peak stays under "
            f"{GAP_S:g} s (moment(...).rest(<tracks>, before=0.4))")
