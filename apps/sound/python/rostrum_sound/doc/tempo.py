"""The tempo map: the one place beats and seconds turn into each other.

The song starts at the document's `tempo` (bpm); each tempo change (`tempos[]`, type "tempo": {at, bpm, ramp})
sets a new tempo from its time on, held until the next change, or, with `ramp`, gliding to the next change's
tempo over its span (the tempo rises or falls evenly per beat; a ramp on the last change has nothing to glide to
and holds). A change sits at a beat (`{"beat": 32}`, the usual way: it stays on its beat when earlier tempos
change) or at seconds (it stays at that moment, so its beat moves). Not on a marker: a marker in beats needs the
map to be placed, so a change on one would place itself. The engine gets the same map as segments (`contract`),
so the screen, ids, checks and the render all read one map.

A ramp is exact, not stepped: with the tempo rising k bpm per beat from `bpm0`, a beat lasts 60/bpm seconds, so
seconds = 60/k·ln(bpm/bpm0) and back, beat = bpm0/k·(e^(k·seconds/60) − 1) (`engine/src/contract/time.rs` agrees).
"""
from __future__ import annotations

import math

INF = float("inf")


def start_bpm(root: dict) -> float:
    return float(root.get("tempo", 120))


def _slope(seg) -> float:
    """bpm per beat inside a segment (0 when it holds)."""
    b0, bpm0, _, bpm1, b1 = seg
    return 0.0 if bpm1 == bpm0 or b1 == INF else (bpm1 - bpm0) / (b1 - b0)


def _sec_in(seg, beat: float) -> float:
    b0, bpm0, s0, _, _ = seg
    k = _slope(seg)
    return s0 + ((beat - b0) * 60.0 / bpm0 if k == 0 else 60.0 / k * math.log1p(k * (beat - b0) / bpm0))


def _beat_in_seg(seg, sec: float) -> float:
    b0, bpm0, s0, _, _ = seg
    k = _slope(seg)
    return b0 + ((sec - s0) * bpm0 / 60.0 if k == 0 else bpm0 / k * math.expm1(k * (sec - s0) / 60.0))


def _span(bpm0: float, bpm1: float, secs: float) -> float:
    """Beats a ramp from bpm0 to bpm1 covers in `secs` (its beats-per-second, averaged in log)."""
    return secs * bpm0 / 60.0 if bpm1 == bpm0 else secs * (bpm1 - bpm0) / (60.0 * math.log(bpm1 / bpm0))


def segments(root: dict) -> list[tuple[float, float, float, float, float]]:
    """(start beat, bpm, start seconds, bpm at its end, end beat) per stretch, the first at beat 0, the last
    ending at infinity. A held stretch ends at its own bpm. A change in seconds is placed after every change before
    it (the earliest still unplaced goes next), so mixed forms agree."""
    open_ = [0.0, start_bpm(root), 0.0, False]           # the last placed stretch: beat, bpm, seconds, ramps
    done = []
    todo = [c for c in root.get("tempos", []) if "at" in c and "bpm" in c]
    while todo:
        b0, bpm0, s0, ramp = open_

        def beat_of(c):
            at = c["at"]
            if isinstance(at, dict):
                return float(at["beat"])
            return b0 + _span(bpm0, float(c["bpm"]) if ramp else bpm0, float(at) - s0)
        c = min(todo, key=beat_of)
        todo.remove(c)
        b, bpm = beat_of(c), float(c["bpm"])
        if b <= b0 + 1e-9:                 # on the same beat as the one before (or beat 0): it replaces it
            open_[1], open_[3] = bpm, bool(c.get("ramp"))
            continue
        seg = (b0, bpm0, s0, bpm if ramp else bpm0, b)
        done.append(seg)
        open_ = [b, bpm, _sec_in(seg, b), bool(c.get("ramp"))]
    b0, bpm0, s0, _ = open_
    return done + [(b0, bpm0, s0, bpm0, INF)]


def _by_beat(segs, beat: float):
    """The stretch `beat` is in; before the song's start, the first (its tempo reaches back, so "a beat before
    0" is a time a check can name instead of a crash)."""
    return next((s for s in reversed(segs) if s[0] <= beat + 1e-12), segs[0])


def _by_sec(segs, sec: float):
    return next((s for s in reversed(segs) if s[2] <= sec + 1e-12), segs[0])


def seconds_at(root: dict, beat: float) -> float:
    return _sec_in(_by_beat(segments(root), beat), beat)


def beat_at(root: dict, sec: float) -> float:
    return _beat_in_seg(_by_sec(segments(root), sec), sec)


def bpm_at(root: dict, sec: float) -> float:
    """The tempo playing at `sec` seconds (inside a ramp, the tempo at that instant)."""
    seg = _by_sec(segments(root), sec)
    return seg[1] + _slope(seg) * (_beat_in_seg(seg, sec) - seg[0])


def beat_seconds(root: dict, sec: float) -> float:
    """How long one beat lasts at `sec`."""
    return 60.0 / bpm_at(root, sec)


def ramps(root: dict) -> bool:
    return any(_slope(s) for s in segments(root))


def contract(root: dict):
    """The engine's `tempo`: a number while the tempo never changes, else the segments, a ramping one with
    `"ramp": true` (it glides to the next segment's bpm: ENGINE_CONTRACT.md)."""
    segs = segments(root)
    if len(segs) == 1:
        return segs[0][1]
    return [{"beat": round(s[0], 6), "bpm": s[1], **({"ramp": True} if _slope(s) else {})} for s in segs]


def beats(root: dict, end: float) -> list[float]:
    """The time of every beat from 0 to `end` seconds (the ruler and the grid draw these)."""
    out = []
    for seg in segments(root):
        k = int(-(-seg[0] // 1))           # the first whole beat in this stretch
        while k < seg[4] - 1e-9:
            t = _sec_in(seg, k)
            if t > end + 1e-9:
                return out
            out.append(round(t, 6))
            k += 1
    return out
