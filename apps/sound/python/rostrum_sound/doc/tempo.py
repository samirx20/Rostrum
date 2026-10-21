"""The tempo map: the one place beats and seconds turn into each other.

The song starts at the document's `tempo` (bpm); each tempo change (`tempos[]`, type "tempo": {at, bpm}) sets a
new tempo from its time on, held until the next change (no ramps: a ramp is several changes). A change sits at
a beat (`{"beat": 32}`, the usual way: it stays on its beat when earlier tempos change) or at seconds (it stays
at that moment, so its beat moves). Not on a marker: a marker in beats needs the map to be placed, so a change
on one would place itself. The engine gets the same map as segments (`contract`), so the screen, ids, checks
and the render all read one map.
"""
from __future__ import annotations


def start_bpm(root: dict) -> float:
    return float(root.get("tempo", 120))


def _beat_in(segs, sec: float) -> float:
    b0, bpm, s0 = next(s for s in reversed(segs) if s[2] <= sec + 1e-12)
    return b0 + (sec - s0) * bpm / 60.0


def segments(root: dict) -> list[tuple[float, float, float]]:
    """(start beat, bpm, start seconds) per stretch of constant tempo, the first at beat 0. A change in seconds
    is placed after every change before it (the earliest still unplaced goes next), so mixed forms agree."""
    segs = [(0.0, start_bpm(root), 0.0)]
    todo = [c for c in root.get("tempos", []) if "at" in c and "bpm" in c]
    while todo:
        def beat_of(c):
            at = c["at"]
            return float(at["beat"]) if isinstance(at, dict) else _beat_in(segs, float(at))
        c = min(todo, key=beat_of)
        todo.remove(c)
        b = beat_of(c)
        lb, lbpm, ls = segs[-1]
        if b <= lb + 1e-9:                 # on the same beat as the one before (or beat 0): it replaces it
            segs[-1] = (lb, float(c["bpm"]), ls)
            continue
        segs.append((b, float(c["bpm"]), ls + (b - lb) * 60.0 / lbpm))
    return segs


def seconds_at(root: dict, beat: float) -> float:
    b0, bpm, s0 = next(s for s in reversed(segments(root)) if s[0] <= beat + 1e-12)
    return s0 + (beat - b0) * 60.0 / bpm


def beat_at(root: dict, sec: float) -> float:
    return _beat_in(segments(root), sec)


def bpm_at(root: dict, sec: float) -> float:
    """The tempo playing at `sec` seconds."""
    return next(s for s in reversed(segments(root)) if s[2] <= sec + 1e-12)[1]


def beat_seconds(root: dict, sec: float) -> float:
    """How long one beat lasts at `sec`."""
    return 60.0 / bpm_at(root, sec)


def contract(root: dict):
    """The engine's `tempo`: a number while the tempo never changes, else the segments (ENGINE_CONTRACT.md)."""
    segs = segments(root)
    if len(segs) == 1:
        return segs[0][1]
    return [{"beat": round(b, 6), "bpm": bpm} for b, bpm, _ in segs]


def beats(root: dict, end: float) -> list[float]:
    """The time of every beat from 0 to `end` seconds (the ruler and the grid draw these)."""
    out, segs = [], segments(root)
    for i, (b0, bpm, s0) in enumerate(segs):
        stop = segs[i + 1][0] if i + 1 < len(segs) else float("inf")
        k = int(-(-b0 // 1))               # the first whole beat in this stretch
        while k < stop - 1e-9:
            t = s0 + (k - b0) * 60.0 / bpm
            if t > end + 1e-9:
                return out
            out.append(round(t, 6))
            k += 1
    return out
