"""A part's volume, brightness or articulation following a curve over bars: one line per change.

    t.shape("vol", 0.5, 1.1, over=(bar(1), bar(13)), curve="late")   # velocity x the curve at each note's start; a held note
                                                                       # follows it as a ratio to that start (x2 at most; 0 stays 0)
    t.shape("bright", 0.2, 1, over=(bar(9), "#climax"))               # a lowpass opening: 0 ≈ 250 Hz … 1 = 20 kHz, or Hz
    t.shape("art", "", "trem", over=(bar(5), bar(9)))                  # notes switch where the curve passes its middle

Applied when the script's tree is made (`builder.Track.item`), after the note ids are made: phrase -> shape ->
humanize. Before a kind's first shape its value holds at that shape's from_, after the last at its to, between shapes
at the previous to. Pure functions of the script: a re-run writes the same values, so the merge keeps a person's edits.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from rostrum_core import RostrumError, codes, did_you_mean

from .builder_parts import checked
from .doc import ids, tempo, times

WHAT = ("vol", "bright", "art")
CURVES = {"linear": lambda p: p, "late": lambda p: p * p, "early": lambda p: 1 - (1 - p) * (1 - p),
          "smooth": lambda p: p * p * (3 - 2 * p)}
LOW_HZ, HIGH_HZ = 250.0, 20000.0
HELD_BEATS = 1.0          # a note longer than this swells inside itself (its own dynamics)
STEPS = 8                 # points written per shape where the curve bends (the EQ envelope, a held note's swell)


@dataclass
class Shape:
    what: str
    a: object             # from_
    b: object             # to
    start: object
    end: object
    curve: str


def make(what, from_, to, over, curve, track: dict, where: str) -> Shape:
    """Checks one t.shape(...) call; a wrong name or value is a loud BAD_ARGUMENT listing what is accepted."""
    if what not in WHAT:
        raise RostrumError(codes.BAD_ARGUMENT, where, f"what={what!r}", "is not something shape changes", list(WHAT),
                           did_you_mean(str(what), WHAT))
    if curve not in CURVES:
        raise RostrumError(codes.BAD_ARGUMENT, where, f"curve={curve!r}", "is not a curve", list(CURVES),
                           did_you_mean(str(curve), CURVES))
    if not (isinstance(over, (list, tuple)) and len(over) == 2):
        raise RostrumError(codes.BAD_ARGUMENT, where, f"over={over!r}", "is not a span", ["over=(bar(9), bar(13))",
                                                                                        'over=(bar(9), "#climax")'])
    for t in over:
        if times.problem(t):
            raise RostrumError(codes.BAD_ARGUMENT, where, f"shape time {t!r}", times.problem(t), times.forms())
    for v in (from_, to):
        if what == "art":
            arts = ["", *(track.get("articulations") or {})]
            if v not in arts:
                raise RostrumError(codes.BAD_ARGUMENT, where, f"articulation {v!r}", "is not one of this track's "
                                   'articulations ("" = its main sound)', arts, did_you_mean(str(v), arts))
        elif isinstance(v, bool) or not isinstance(v, (int, float)) or not (
                (0 <= v <= 2) if what == "vol" else (0 <= v <= 1 or 20 <= v <= HIGH_HZ)):
            raise RostrumError(codes.BAD_ARGUMENT, where, f"{what} {v!r}", "is out of range",
                               ["0 to 2 (1 = as written)"] if what == "vol" else ["0 to 1 (0 ≈ 250 Hz, 1 = 20 kHz)",
                                                                                   "20 to 20000 (Hz)"])
    return Shape(what, from_, to, over[0], over[1], curve)


class Curve:
    """Several shapes of one kind on a track, joined into one piecewise curve over song seconds."""

    def __init__(self, shapes: list[Shape], root: dict, where: str):
        spans = [(times.seconds(s.start, root, where), times.seconds(s.end, root, where), s) for s in shapes]
        for a, b, s in spans:
            if b <= a:
                raise RostrumError(codes.BAD_ARGUMENT, where, f"shape {s.what} over ({s.start!r}, {s.end!r})",
                                   f"ends at {b:.3f} s, not after its start at {a:.3f} s")
        self.spans = sorted(spans, key=lambda x: x[0])

    def at(self, sec: float) -> tuple[Shape, float]:
        """The shape that governs `sec` and how far along its (eased) curve it is, 0 … 1."""
        a, b, s = self.spans[0]
        if sec <= a:
            return s, 0.0
        for a, b, s in reversed(self.spans):
            if sec >= a:
                return s, CURVES[s.curve](min(1.0, (sec - a) / (b - a)))
        return s, 0.0

    def value(self, sec: float) -> float:
        s, p = self.at(sec)
        return s.a + (s.b - s.a) * p


def hz(v: float) -> float:
    return float(v) if v > 1 else LOW_HZ * (HIGH_HZ / LOW_HZ) ** v


def _vol(f: dict, kind: str, vol: Curve, root: dict, where: str) -> dict:
    s = times.seconds(f["at"], root, where)
    c0 = vol.value(s)
    out = {**f, "vel": round(min(1.0, max(0.0, f.get("vel", 0.8) * c0)), 4)}
    if kind != "note" or "dynamics" in f or c0 <= 0:
        return out
    try:
        length = times.length_seconds(f["dur"], root, s, f, where)
    except RostrumError:                       # "next" or a tie the tree can't read yet: no inner swell, never a guess
        return out
    if length <= HELD_BEATS * tempo.beat_seconds(root, s) + 1e-6:
        return out
    xs = [i / STEPS for i in range(STEPS + 1)]
    pts = [(x, round(min(2.0, max(0.0, vol.value(s + x * length) / c0)), 4)) for x in xs]
    pts = [p for i, p in enumerate(pts) if i in (0, STEPS) or not math.isclose(
        p[1], (pts[i - 1][1] + pts[i + 1][1]) / 2, abs_tol=0.002)]     # straight stretches need no inner points
    return out if all(math.isclose(y, 1.0, abs_tol=0.002) for _, y in pts) else {**out, "dynamics": [list(p) for p in pts]}


def _art(f: dict, art: Curve, root: dict) -> dict:
    s, p = art.at(times.seconds(f["at"], root, "shape art"))
    if f.get("art", "") not in (s.a, s.b):
        return f                               # a note written with another articulation keeps it
    pick = s.b if p >= 0.5 else s.a
    return {k: v for k, v in f.items() if k != "art"} if pick == "" else {**f, "art": pick}


def curves(shapes: list[Shape], root: dict, where: str) -> dict[str, Curve]:
    return {w: Curve([s for s in shapes if s.what == w], root, where) for w in WHAT if any(s.what == w for s in shapes)}


def apply(f: dict, kind: str, made: dict[str, Curve], root: dict, where: str) -> dict:
    """One note's or hit's fields with the track's vol and art shapes applied."""
    if "vol" in made:
        f = _vol(f, kind, made["vol"], root, where)
    if "art" in made and kind == "note":
        f = _art(f, made["art"], root)
    return f


def bright_envelope(bright: Curve) -> list[list[float]]:
    """The lowpass frequency as [[seconds, Hz], …]: log-spaced along each shape, a step where a shape starts
    away from the previous one's end."""
    out: list[list[float]] = []
    for a, b, s in bright.spans:
        lo, hi = math.log(hz(s.a)), math.log(hz(s.b))
        if out and a > out[-1][0] + 0.001:
            out.append([round(a, 4), out[-1][1]])          # held at the previous shape's end until this one starts
        for i in range(STEPS + 1):
            t = round(a + (b - a) * i / STEPS, 4)
            if out:
                t = max(t, round(out[-1][0] + 0.001, 4))
            out.append([t, round(math.exp(lo + (hi - lo) * CURVES[s.curve](i / STEPS)), 1)])
    return out


def bright_effect(track_id: str, bright: Curve, taken: set, where: str) -> dict:
    """The track's one lowpass EQ (`<track>.eq_bright`), its freq the bright shapes' envelope."""
    eq_id = ids.named(track_id, "eq_bright", taken)
    taken.add(eq_id)
    band = {"shape": "lowpass", "freq": bright_envelope(bright), "q": 0.707}
    return {"id": eq_id, "type": "effect", **checked("effect", {"effect": "eq", "bands": [band]}, f"{where} › shape bright",
                                                     {"bypass": False})}
