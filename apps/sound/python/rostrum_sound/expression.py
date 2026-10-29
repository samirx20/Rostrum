"""Seeded humanize and phrase-shaped velocity: tools that write plain values into notes and hits.

Both run when the script's tree is made (`builder.Track.item`), after each note's id is made from where it was
*written*, so the id never moves with the shaping. Humanize draws its offsets from (seed, the item's id): the
same script gives the same values every run, so the script merge sees no change and keeps a person's edit; a
new note gets its own draw and moves no other note.

    t.humanize(seed=7, timing=0.012, velocity=0.06)   # every note / hit on t, ±12 ms and ±0.06 velocity
    t.phrase(bar(5), bar(9), vel=[(0, 0.5), (1, 0.9)])  # velocity along the phrase, for notes that wrote none
    f = vel_curve([(0, 0.5), (1, 0.9)], bar(5), bar(9)); t.note("D3", at=x, dur=1, vel=f(x) + 0.1)
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from rostrum_core import RostrumError, codes

from .doc import times
from .doc.shift import write_like


def curve_at(points, x: float) -> float:
    """The value of [(x, y), …] at x: straight lines between points, held before the first and after the last."""
    pts = sorted((float(a), float(b)) for a, b in points)
    if not pts:
        raise ValueError("a curve needs at least one point")
    if x <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x <= x1:
            return y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return pts[-1][1]


def draw(seed, key: str, n: int = 2) -> list[float]:
    """n numbers in −1 … 1, fixed by (seed, key) on every machine and run."""
    h = hashlib.sha256(f"{seed}:{key}".encode()).digest()
    return [int.from_bytes(h[4 * i:4 * i + 4], "big") / 0xFFFFFFFF * 2 - 1 for i in range(n)]


def shift(at, dt: float, root: dict, where: str):
    """`at` moved by dt seconds, kept in its own form (seconds, beats or a marker reference); never before 0, nor
    before bar 1 when it is not written in seconds (a pickup's bar 1 starts later than 0 s)."""
    s = times.seconds(at, root, where)
    lo = 0.0 if isinstance(at, (int, float)) else min(s, times.seconds({"beat": 0}, root, where))
    return write_like(at, max(0.0, lo, s + dt), root)


@dataclass
class Humanize:
    seed: object
    timing: float = 0.012     # seconds, ± (uniform)
    velocity: float = 0.06    # velocity, ±, kept inside 0 … 1

    def apply(self, id_: str, fields: dict, root: dict, where: str) -> dict:
        dt, dv = draw(self.seed, id_)
        out = dict(fields, at=shift(fields["at"], dt * self.timing, root, where))
        if "vel" in out:
            out["vel"] = round(min(1.0, max(0.0, out["vel"] + dv * self.velocity)), 4)
        return out


def _check(what, value, lo, hi, where):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not lo <= value <= hi:
        raise RostrumError(codes.BAD_ARGUMENT, where, f"{what}={value!r}", "is out of range", [f"{lo} to {hi}"])


def humanize(seed, timing, velocity, where) -> Humanize:
    if isinstance(seed, bool) or not isinstance(seed, (int, str)):
        raise RostrumError(codes.BAD_ARGUMENT, where, f"seed={seed!r}", "must be a whole number or a word")
    _check("timing", timing, 0, 0.1, where)
    _check("velocity", velocity, 0, 0.5, where)
    return Humanize(seed, timing, velocity)


@dataclass
class Phrase:
    start: object
    end: object
    vel: list

    def velocity(self, at, root, where, hold=False) -> float | None:
        """The curve's velocity at `at`; outside the phrase None (hold=True: the nearest end's value)."""
        s, a, b = (times.seconds(t, root, where) for t in (at, self.start, self.end))
        if not a <= s <= b and not hold:
            return None
        s = min(max(s, a), b)
        return round(curve_at(self.vel, 0.0 if b == a else (s - a) / (b - a)), 4)


def phrase(start, end, vel, where) -> Phrase:
    for t in (start, end):
        if times.problem(t):
            raise RostrumError(codes.BAD_ARGUMENT, where, f"phrase time {t!r}", times.problem(t), times.forms())
    if not isinstance(vel, (list, tuple)) or not vel:
        raise RostrumError(codes.BAD_ARGUMENT, where, f"vel={vel!r}", "is not a curve", ["[(0, 0.5), (1, 0.9)]"])
    for pt in vel:
        if not (isinstance(pt, (list, tuple)) and len(pt) == 2):
            raise RostrumError(codes.BAD_ARGUMENT, where, f"vel={vel!r}", "is not a curve", ["[(0, 0.5), (1, 0.9)]"])
        _check("phrase position", pt[0], 0, 1, where)
        _check("velocity", pt[1], 0, 1, where)
    return Phrase(start, end, [list(p) for p in vel])
