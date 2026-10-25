"""A line: what every writing helper returns and `write` puts on a track.

A line is a plain list of dicts, in beats from the line's own start, so it can be printed, filtered, joined and
edited like any list:

    {"pitch": "D4", "at": 0.0, "dur": 1.5, "vel": 0.7}         a note ("pitch" a list of names: a chord)
    {"drum": "kick", "at": 1.5, "vel": 0.9}                      a drum hit

`write(track, line, at=bar(5))` writes each one through the track's own note / chord / hit, so ids, checks and the
rule that a person's edit survives a re-run are the same as for notes written by hand.
"""
from __future__ import annotations

from ..script_time import Beat, Beats
from .pitch import refuse

GRID_CHARS = "xX-."


def line(notes, where="line") -> list[dict]:
    """A line from tuples: line([("D4", 0, 1), ("F4", 1, 0.5, 0.8), (["D3", "A3"], 2, 2)]) — (pitch, at, dur[, vel])
    in beats from the line's start; a list of pitches is a chord."""
    out = []
    for n in notes:
        if isinstance(n, dict):
            out.append(dict(n))
            continue
        if not isinstance(n, (tuple, list)) or len(n) not in (3, 4):
            refuse(where, repr(n), "is (pitch, at, dur) or (pitch, at, dur, vel), in beats", ['("D4", 0, 1)', '("F4", 1.5, 0.5, 0.8)'])
        out.append({"pitch": n[0], "at": float(n[1]), "dur": float(n[2]), "vel": n[3] if len(n) == 4 else None})
    return sorted(out, key=lambda x: x["at"])


def span(ln: list[dict], beats_per_bar: float, every=None) -> float:
    """The beats a line takes: `every` when given, else its end rounded up to whole bars."""
    if every is not None:
        return float(every)
    end = max((n["at"] + n.get("dur", 0.25) for n in ln), default=0.0)
    bars = max(1, -(-round(end, 6) // beats_per_bar))
    return bars * beats_per_bar


def shift(ln: list[dict], beats: float) -> list[dict]:
    """The line moved later by `beats` (earlier when negative)."""
    return [{**n, "at": n["at"] + beats} for n in ln]


def grid(pattern: str, total_steps: int, hits: str, where: str, step_beats: float = 0.25) -> list[tuple[float, float, str]]:
    """(at, length, char) in beats for a step pattern repeating over `total_steps`: a char of `hits` strikes, "-" holds
    the strike before, "." rests. Spaces and bar lines "|" are ignored."""
    p = pattern.replace(" ", "").replace("|", "")
    if not p or any(c not in hits + "-." for c in p) or not any(c in hits for c in p):
        refuse(where, f"pattern {pattern!r}", f"is one character per 16th: {', '.join(hits)} strike, - holds, . rests",
               ['"x..x..x.x-x-...."'])
    out: list[list] = []
    for s in range(total_steps):
        c = p[s % len(p)]
        if c == "-" and out and abs(out[-1][0] + out[-1][1] - s * step_beats) < 1e-9:
            out[-1][1] += step_beats
        elif c in hits:
            out.append([s * step_beats, step_beats, c])
    return [tuple(o) for o in out]


def write(track, ln: list[dict], at=0):
    """Every note and hit of the line onto `track`, starting at `at` (bar(5), beat(8), "#drop"). Returns the track."""
    where = f"write(track {getattr(track, 'id', '?')})"
    if not hasattr(track, "note"):
        refuse(where, repr(track), "is not a track", ['p = track("piano", builtIn="grandPiano"); write(p, line, bar(1))'])
    if isinstance(at, (int, float)) and not isinstance(at, bool):
        if at != 0:
            refuse(where, f"at={at!r}", "is seconds; a line is written in beats from a beat time or a marker",
                   ["bar(5)", "beat(16)", '"#drop"'])
        at = Beat(0)
    for n in ln:
        when = at + Beats(round(n["at"], 6))
        if "drum" in n:
            track.hit(n["drum"], at=when, vel=n.get("vel"))
            continue
        dur = Beats(round(max(n.get("dur", 0.25), 1 / 64), 6))
        vel = None if n.get("vel") is None else round(min(1.0, max(0.02, n["vel"])), 3)
        track.note(n["pitch"], at=when, dur=dur, vel=vel)
    return track
