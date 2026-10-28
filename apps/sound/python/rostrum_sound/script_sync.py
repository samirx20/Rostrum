"""Landing a beat on a time without bending the music: the script's `downbeat`, `land` and `seconds_of`.

    downbeat(bar(21), at=36.0)                     # moves the whole grid: bar 1 starts later (gridStart), the tempo stays
    land(bar(21), at=36.0, ramp_from=bar(17))      # a tempo glide over bars 17-21 (out and back), so bar 21 lands at 36.0
    s.note("G4", at=seconds_of(bar(1) - beats(1)), dur=beats(1))     # a pickup note before bar 1, in seconds

Each works on the tempo map as the script has written it so far, and is exact (within a microsecond): write `tempo(...)`,
the tempo changes and the time signature first, then these. Every landing asked is checked again when the script ends
(`check`): a tempo change written after it that moves the landed time is a loud error, never a quiet miss.
"""
from __future__ import annotations

import math

from rostrum_core import RostrumError, codes

from .doc import meter, tempo
from .script_scope import say
from .script_time import Beat

QUIET_START = 0.25          # a grid start past this needs pickup music (a song never starts silent)
MOST_CHANGE = 0.08          # land's glide stays within 8 % of the tempo, so it is felt as a push, not a new tempo
EXACT = 1e-6


def _beat(t, name: str, where: str) -> float:
    if isinstance(t, Beat):
        return float(t["beat"])
    raise RostrumError(codes.BAD_ARGUMENT, where, f"{name}={t!r}", "is not a time on the beat grid",
                       ["bar(21)", "bar(21) + beats(2)", "beat(80)"],
                       "It lands a beat or bar; a sound at a time in seconds is written at that time (at=36.0).")


def _seconds(at, where: str) -> float:
    if isinstance(at, bool) or not isinstance(at, (int, float)) or at < 0:
        raise RostrumError(codes.BAD_ARGUMENT, where, f"at={at!r}", "is not a time in seconds (≥ 0)", ["at=36.0"])
    return float(at)


def name(root: dict, beat: float) -> str:
    """'bar 21' or 'bar 21 beat 3' (as the ruler counts)."""
    bars = meter.bar_at(root, beat)
    whole = math.floor(bars + 1e-9)
    rest = (beat - meter.bar_start(root, whole + 1)) if whole >= 0 else 0.0
    return f"bar {whole + 1}" + (f" beat {rest + 1:g}" if abs(rest) > 1e-9 else "")


def _grid_for(root: dict, beat: float, at: float) -> float:
    """The gridStart that puts `beat` at `at` seconds (a tempo change in seconds stays at its moment, so the map
    under the grid can change with it: found by repeating until it holds)."""
    g = 0.0
    for _ in range(50):
        err = at - tempo.seconds_at({**root, "gridStart": g}, beat)
        if abs(err) < 1e-10:
            return g
        g += err
    raise RostrumError(codes.CHECK_FAILED, "downbeat", f"{name(root, beat)} at {at:g} s",
                       "could not be landed exactly: the tempo changes in seconds move with it",
                       hint="Write those tempo changes on beats (tempo_change(bar(9), 140)), or use land(...).")


def downbeat(song, time, at) -> None:
    """Sets the song's gridStart so `time` (a beat or bar) lands exactly at `at` seconds, at the tempo map written so far;
    the music before bar 1 is a pickup (seconds_of(bar(1) - beats(n))). Refused when bar 1 would start before 0 s."""
    where = "downbeat"
    beat, at = _beat(time, "time", where), _seconds(at, where)
    root = {k: v for k, v in song.root.items() if k != "gridStart"}
    g = _grid_for(root, beat, at)
    if g < -EXACT:
        raise RostrumError(codes.BAD_ARGUMENT, where, f"{name(root, beat)} at {at:g} s",
                           f"would need bar 1 to start {-g:.3f} s before the song starts", _fits(root, beat, at),
                           f"Or keep the bar and glide the tempo: land({_show(root, beat)}, at={at:g}, "
                           f"ramp_from={_show(root, max(0.0, beat - 4 * meter.per_bar_at(root, beat)))}).")
    g = max(0.0, g)
    song.set(gridStart=round(g, 9))
    song.landings.append((where, beat, at))
    if g > QUIET_START:
        say(f"downbeat: {name(root, beat)} lands at {at:g} s; bar 1 starts at {g:.3f} s, so write pickup music in "
            f"the first {g:.2f} s (at=seconds_of(bar(1) - beats(n))): the song should not start silent.")


def _fits(root: dict, beat: float, at: float) -> list[str]:
    """The latest bars before `beat` that can land on `at` with a pickup (bars ≥ 1, counting down)."""
    out, bar = [], math.floor(meter.bar_at(root, beat) + 1e-9) + 1
    while bar >= 1 and len(out) < 2:
        b = meter.bar_start(root, bar)
        if b < beat - 1e-9 and (g := _grid_for(root, b, at)) >= 0:
            out.append(f"bar {bar} lands at {at:g} s with a {g:.2f} s pickup: downbeat(bar({bar}), at={at:g})")
        bar -= 1
    return out or ["no bar of this song reaches that time: write the hit in seconds (at=" + f"{at:g})"]


def _show(root: dict, beat: float) -> str:
    whole = math.floor(meter.bar_at(root, beat) + 1e-9) + 1
    rest = beat - meter.bar_start(root, whole)
    return f"bar({whole})" + (f" + beats({rest:g})" if abs(rest) > 1e-9 else "")


def _ramp_secs(a: float, c: float, n: float) -> float:
    """Seconds a glide from a to c bpm over n beats lasts (even per beat: 60·n·ln(c/a)/(c−a))."""
    return n * 60.0 / a if abs(c - a) < 1e-12 else 60.0 * n * math.log(c / a) / (c - a)


def land(song, time, at, ramp_from) -> None:
    """Lands `time` exactly at `at` seconds by a tempo glide from `ramp_from`: the tempo glides from where it is to a
    peak halfway and back, so the tempo held before `ramp_from` plays again at `time` (or the change already written
    there). The two halves last the same: 60·(n/2)·(ln(p/a)/(p−a) + ln(c/p)/(c−p)) seconds over n beats, p solved
    exactly. Refused past an 8 % change, naming a ramp long enough."""
    where = "land"
    b1, b0, at = _beat(time, "time", where), _beat(ramp_from, "ramp_from", where), _seconds(at, where)
    root = song.root
    if b0 >= b1 - 1e-9:
        raise RostrumError(codes.BAD_ARGUMENT, where, f"ramp_from={_show(root, b0)}", f"is not before {_show(root, b1)}",
                           [f"ramp_from={_show(root, max(0.0, b1 - 4 * meter.per_bar_at(root, b1)))}"])
    seg = next(s for s in reversed(tempo.segments(root)) if s[0] <= b0 + 1e-9)
    if seg[3] != seg[1] or seg[4] < b1 - 1e-9:
        raise RostrumError(codes.BAD_ARGUMENT, where, f"{_show(root, b0)} … {_show(root, b1)}",
                           "already has a tempo change or a glide inside it", hint="Start the ramp after that change "
                           "(ramp_from= a later bar), or land through downbeat(...).")
    a, s0, n = seg[1], tempo.seconds_at(root, b0), b1 - b0
    c = next((float(x["bpm"]) for x in root.get("tempos", []) if isinstance(x.get("at"), dict)
              and abs(float(x["at"]["beat"]) - b1) < 1e-9), a)
    want = at - s0
    if want <= 0:
        raise RostrumError(codes.BAD_ARGUMENT, where, f"at={at:g}", f"is before {name(root, b0)} ({s0:.3f} s), where the ramp starts")
    span = lambda p: _ramp_secs(a, p, n / 2) + _ramp_secs(p, c, n / 2)
    lo, hi = a * (1 - 2 * MOST_CHANGE), a * (1 + 2 * MOST_CHANGE)
    if not span(hi) <= want <= span(lo):
        return _too_far(root, b0, b1, a, at, want - n * 60.0 / a)
    for _ in range(200):                        # the span shortens as the peak rises: bisection to a nanosecond
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if span(mid) > want else (lo, mid)
    p = (lo + hi) / 2
    if abs(p / a - 1) > MOST_CHANGE:
        return _too_far(root, b0, b1, a, at, want - n * 60.0 / a)
    song.tempo_change(Beat(b0), a, ramp=True)
    song.tempo_change(Beat((b0 + b1) / 2), round(p, 9), ramp=True)
    if c == a:
        song.tempo_change(Beat(b1), a)
    got = tempo.seconds_at(song.root, b1)
    if abs(got - at) > EXACT:
        raise RostrumError(codes.CHECK_FAILED, where, f"{name(root, b1)}", f"landed at {got:.6f} s, not {at:g} s")
    song.landings.append((where, b1, at))
    say(f"land: {name(root, b1)} lands at {at:g} s: tempo {a:g} -> {p:.1f} -> {c:g} bpm over "
        f"{name(root, b0)} - {name(root, b1)}.")


def _too_far(root, b0, b1, a, at, shift):
    """Refuse: name about how many beats a ramp within 8 % needs (a glide out and back moves time by about half
    its largest change, per beat; asked with a little room)."""
    need = abs(shift) * a / 60.0 / (0.45 * MOST_CHANGE)
    per = meter.per_bar_at(root, b1)
    start = b1 - math.ceil(need / per) * per
    fix = (f"ramp_from={_show(root, start)} (about {math.ceil(need / per)} bars)" if start >= 0 else
           f"downbeat({_show(root, b1)}, at={at:g}) (a pickup), or the hit in seconds (at={at:g})")
    raise RostrumError(codes.BAD_ARGUMENT, "land", f"{name(root, b1)} at {at:g} s",
                       f"needs more than an 8 % tempo change over {name(root, b0)} - {name(root, b1)}", [fix],
                       "A longer ramp moves the time with a smaller change.")


def seconds_of(song, time) -> float:
    """The file time of a beat on the tempo map written so far, a beat before bar 1 included (a pickup):
    seconds_of(bar(1) - beats(1)). Write tempo, tempo changes and downbeat(...) before it."""
    return round(tempo.seconds_at(song.root, _beat(time, "time", "seconds_of")), 9)


def check(song) -> None:
    """Every landing asked still holds on the finished tempo map (a later tempo change could have moved it)."""
    for what, beat, at in song.landings:
        got = tempo.seconds_at(song.root, beat)
        if abs(got - at) > EXACT:
            raise RostrumError(codes.BAD_ARGUMENT, what, f"{name(song.root, beat)} at {at:g} s",
                               f"now lands at {got:.3f} s: a tempo or grid change written after {what}(...) moved it",
                               hint=f"Write the tempo changes first, then {what}(...).")


API = ["downbeat(time, at)", "land(time, at, ramp_from)", "seconds_of(time)"]


def scope(song) -> dict:
    song.landings = []
    return {"downbeat": lambda time, at: downbeat(song, time, at),
            "land": lambda time, at, ramp_from: land(song, time, at, ramp_from),
            "seconds_of": lambda time: seconds_of(song, time)}
