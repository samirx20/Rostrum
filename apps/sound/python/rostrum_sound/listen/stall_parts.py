"""stall_parts: which parts to lift when a build stalls (stall.py): the tracks playing across the stalled bars whose own
level and density do not rise from the first of those bars to the last.

A part's level is its stem's loudness in each bar (the render's per-track files, as squash.py and the duck check read
them) when the render has one, else the level the document asks for (part_read.played: velocity x lanes x the note's
own dynamics; recorded instruments get about 40 x log10 of a velocity ratio in dB). Density: its notes and hits
starting in the bar.

    flat(data, rows, stems=None) -> [{"track", "rise_db", "from": "stem" | "document", "first", "last"}]
"""
from __future__ import annotations

import math

from .bs1770 import integrated
from .core import load, num
from .part_read import played

QUIET_LUFS = -70.0


def _stem_lufs(path, a, b) -> float:
    y, sr = load(path)
    return max(QUIET_LUFS, integrated(y[int(a * sr):int(b * sr)], sr))


def _doc_level(rows_of, a, b) -> float | None:
    """The mean asked level of the notes sounding in [a, b)."""
    lv = [r["level"] for r in rows_of if r["at"] < b and r["end"] > a]
    return sum(lv) / len(lv) if lv else None


def _count(rows_of, a, b) -> int:
    return sum(1 for r in rows_of if a - 1e-3 <= r["at"] < b - 1e-3)


def flat(data, rows, stems=None, stall_lu=1.5, denser=1.25) -> list[dict]:
    if len(rows) < 2:
        return []
    (a0, b0), (a1, b1) = (rows[0]["from_s"], rows[0]["to_s"]), (rows[-1]["from_s"], rows[-1]["to_s"])
    out = []
    for t in data.get("tracks") or []:
        if t.get("mute"):
            continue
        mine = played(t, data)
        if not any(r["at"] < b1 and r["end"] > a1 for r in mine):
            continue                               # not playing in the last bar: nothing there to lift
        n0, n1 = _count(mine, a0, a0 + (b1 - a1)), _count(mine, a1, b1)   # the same stretch of each bar (the last is cut)
        if n0 and n1 / n0 >= denser:
            continue                               # it gets busier: it builds
        path = (stems or {}).get(t["id"])
        if path:
            try:
                first, last = _stem_lufs(path, a0, b0), _stem_lufs(path, a1, b1)
                rise, src = last - first, "stem"
            except Exception:  # noqa: BLE001  a stem the ears cannot read: fall back to the document
                path = None
        if not path:
            first, last = _doc_level(mine, a0, b0), _doc_level(mine, a1, b1)
            if first is None or last is None or first <= 0:
                continue                           # it enters inside the stretch: an added part, a build
            rise, src = 40 * math.log10(max(last, 1e-6) / first), "document"
        if rise < stall_lu:
            out.append({"track": t["id"], "rise_db": num(rise, 1), "from": src, "first": num(first, 2), "last": num(last, 2)})
    return out
