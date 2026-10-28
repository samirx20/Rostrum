"""A build into a moment, written from a script as plain notes: `build_to(target, over, parts)`.

    build_to("#impact", over=beats(8), parts=[
        cymbal_roll(drums),                         # cymbal hits that get denser and louder up to the target
        crescendo(strings, ["D3", "A3", "F4"]),     # held notes tied to the target, each note's dynamics rising
        reverse_swell(pad, "D5"),                   # one note swelling from silence to its peak, ending exactly there
        sub_hit(low, "D1"),                         # a note (or, on a kit, a drum) struck on the target
    ])

`target` is any time: a marker ("#impact", "#impact-2beats"), bar(n) or seconds. `over` is how long before it the build
starts: beats(n) on a marker or a bar (the notes stay on the beat grid), seconds on a marker or seconds. Every note is
written relative to the target in the target's own form ("#impact-3.5beats", bar(9) - beats(3.5)), so moving the
marker moves the whole build. The tracks, pitches and drum are the caller's; the defaults are only neutral shapes
(velocities and dynamics rising from `low` to `peak`, a roll from `rate=(2, 8)` hits per beat (per second when `over` is
seconds)). Nothing is hidden: the notes are ordinary notes and hits, and the reply says what each part wrote.
"""
from __future__ import annotations

from rostrum_core import RostrumError, codes

from .builder import Track
from .doc import markers
from .script_scope import say
from .script_time import Beat, Beats

API = ["build_to(target, over, parts)", "cymbal_roll(track, drum='cymbal', rate=(2, 8), low=0.3, peak=0.95)",
       "crescendo(track, pitches, low=0.3, peak=1.0, vel=0.8)", "reverse_swell(track, pitch, peak=1.0, vel=0.8)",
       "sub_hit(track, pitch_or_drum, vel=1.0, dur=beats(2))"]
FORMS = ['build_to("#impact", over=beats(8), parts=[...])', "build_to(bar(9), over=beats(8), parts=[...])",
         'build_to("#impact", over=3.0, parts=[...]) (seconds)']


def _refuse(where, what, why, accepted=FORMS, hint=None):
    raise RostrumError(codes.BAD_ARGUMENT, where, what, why, accepted, hint)


def _number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _before(target, over, where):
    """(length, unit, f): f(d) is the time d units (beats or seconds, as `over`) before `target`, in its own form."""
    if isinstance(over, Beats) and over["beats"] > 0:
        size, unit = float(over["beats"]), "beats"
    elif _number(over) and over > 0:
        size, unit = float(over), "s"
    else:
        _refuse(where, f"over={over!r}", "is not a length before the target (beats(n), or seconds > 0)")
    if isinstance(target, Beat):
        if unit != "beats":
            _refuse(where, f"over={over!r}", "is seconds, but the target is on the beat grid: say how many beats",
                    hint="On a bar the build stays on the grid: over=beats(8).")
        return size, unit, lambda d: Beat(round(target["beat"] - d, 9))
    if _number(target):
        if unit != "s":
            _refuse(where, f"over={over!r}", "is beats, but the target is a time in seconds",
                    hint='Put a marker on the time (marker("impact", at=12.0)) and build to "#impact" over beats(8).')
        return size, unit, lambda d: round(target - d, 6)
    got = markers.parts(target)
    if got is None:
        _refuse(where, f"target={target!r}", "is not a time (a marker, bar(n) or seconds)")
    name, off, had = got
    if off and had != unit:
        _refuse(where, f"target={target!r} over={over!r}", "mixes seconds and beats (the marker's offset and `over`)",
                [f'build_to("#{name}", over=...)'])
    tail = "beats" if unit == "beats" else ""
    return size, unit, lambda d: f"#{name}{round(off - d, 6):+g}{tail}" if abs(off - d) > 1e-9 else f"#{name}"


class Part:
    def __init__(self, kind, track, **args):
        if not isinstance(track, Track):
            _refuse(kind, repr(track), "is not a track: pass the track itself (the variable track(...) gave)",
                    [f"{kind}(strings, ...)"])
        self.kind, self.track, self.args = kind, track, args


GRID = 0.125


def _show(t):
    return f"beat {t['beat']:g}" if isinstance(t, Beat) else repr(t)


def _rise(low, peak, u):
    return round(low + (peak - low) * u, 4)


def _roll(p, size, unit, at, target):
    a = p.args
    r0, r1 = a["rate"]
    grid = GRID if unit == "beats" else 0.001             # on the beat grid the roll sits on 1/8 beats
    t, n, last = 0.0, 0, None
    while t < size - 1e-6:
        d = round(round((size - t) / grid) * grid, 6)
        if d != last and d > 0:
            p.track.hit(a["drum"], at=at(d), vel=_rise(a["low"], a["peak"], t / size))
            n, last = n + 1, d
        t += 1.0 / (r0 + (r1 - r0) * t / size)
    return f"{n} {a['drum']} hits, {r0:g} → {r1:g} per {'beat' if unit == 'beats' else 'second'}, vel {a['low']:g} → {a['peak']:g}"


def _held(p, size, unit, at, target):
    a = p.args
    p.track.note(a["pitches"], at=at(size), end=target, vel=a["vel"], dynamics=[(0, a["low"]), (1, a["peak"])])
    shown = " ".join(a["pitches"]) if isinstance(a["pitches"], (list, tuple)) else a["pitches"]
    return f"{shown} held to the target, dynamics {a['low']:g} → {a['peak']:g}"


def _hit(p, size, unit, at, target):
    a = p.args
    if p.track.fields.get("instrument") == "kit":
        p.track.hit(a["what"], at=target, vel=a["vel"])
        return f"{a['what']} on the target"
    p.track.note(a["what"], at=target, dur=a["dur"], vel=a["vel"])
    return f"{a['what']} struck on the target"


WRITE = {"cymbal_roll": _roll, "crescendo": _held, "reverse_swell": _held, "sub_hit": _hit}


def build_to(song, target, over=None, parts=()):
    where = "build_to"
    if not parts or not all(isinstance(p, Part) for p in parts):
        _refuse(where, "parts", "is not a list of parts", ["parts=[cymbal_roll(drums), crescendo(strings, ['D3', 'A3'])]"],
                "The parts: cymbal_roll, crescendo, reverse_swell, sub_hit; each takes your own track.")
    size, unit, at = _before(target, over, where)
    said = [f"{p.kind} on {p.track.id}: {WRITE[p.kind](p, size, unit, at, target)}" for p in parts]
    say(f"build_to {_show(target)} over {size:g} {'beats' if unit == 'beats' else 's'}, from {_show(at(size))}: " + "; ".join(said)
        + ". Plain notes: edit them like any other.")


def _shares(low, peak, kind):
    for k, v in (("low", low), ("peak", peak)):
        if not _number(v) or not 0 <= v <= 2:
            _refuse(kind, f"{k}={v!r}", "is not a level 0 … 2", [f"{kind}(..., low=0.3, peak=1.0)"])


def cymbal_roll(track, drum="cymbal", rate=(2, 8), low=0.3, peak=0.95):
    _shares(low, peak, "cymbal_roll")
    if not (isinstance(rate, (list, tuple)) and len(rate) == 2 and all(_number(r) and r > 0 for r in rate)):
        _refuse("cymbal_roll", f"rate={rate!r}", "is not (hits per beat at the start, at the end)", ["rate=(2, 8)"])
    return Part("cymbal_roll", track, drum=drum, rate=tuple(float(r) for r in rate), low=low, peak=peak)


def crescendo(track, pitches, low=0.3, peak=1.0, vel=0.8):
    _shares(low, peak, "crescendo")
    return Part("crescendo", track, pitches=list(pitches) if isinstance(pitches, (list, tuple)) else pitches, low=low, peak=peak, vel=vel)


def reverse_swell(track, pitch, peak=1.0, vel=0.8):
    _shares(0, peak, "reverse_swell")
    return Part("reverse_swell", track, pitches=pitch, low=0, peak=peak, vel=vel)


def sub_hit(track, what, vel=1.0, dur=Beats(2)):
    return Part("sub_hit", track, what=what, vel=vel, dur=dur)


def scope(song) -> dict:
    return {"build_to": lambda target, over=None, parts=(): build_to(song, target, over, parts),
            "cymbal_roll": cymbal_roll, "crescendo": crescendo, "reverse_swell": reverse_swell, "sub_hit": sub_hit}
