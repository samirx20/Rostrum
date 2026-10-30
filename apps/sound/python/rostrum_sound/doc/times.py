"""Times in a Sound document: the one place they are read and turned into seconds.

A time is seconds (a number), `{"beat": n}` (beats from the start), or a marker reference `"#drop"`,
`"#drop+0.5"`, `"#drop-1"` (seconds after / before the marker named "drop"; a trailing "-<number>" is always
an offset, so "#big-hit-1" is one second before "big-hit"). A length is seconds or
`{"beats": n}` (beats from where the thing starts). A note's length can also be *tied*: `{"to": <time>}` ends it at
that time (`{"to": "#land"}` holds it until the marker, wherever the marker moves) and `"next"` holds it until the
next note on its track starts (the last one: until the mix's end). Ties are resolved here, in
`length_seconds`, the one place every reader (render, screen, ears, MIDI) turns a length into seconds. Marker references are resolved here (the engine never sees
them); beats are left to the engine, which gets the same tempo map (`tempo.py`, the one place beats become
seconds), except where seconds are needed here (ids, order checks, marker references, the screen).
"""
from __future__ import annotations

from rostrum_core import RostrumError, codes

from . import markers, meter, tempo


NEXT = "next"


def problem(value, length=False, tied=False) -> str | None:
    """Why `value` is not a time (or a length), or None when it is one. Shapes only: markers are checked later.
    `tied`: a note's length, which may also be `{"to": <time>}` or `"next"`."""
    if tied and value == NEXT:
        return None
    if tied and isinstance(value, dict) and set(value) == {"to"}:
        why = problem(value["to"])
        return None if why is None else f'"to" {why}'
    if isinstance(value, bool):
        return "is not a time"
    if isinstance(value, (int, float)):
        return None if value >= 0 else "can't be negative"
    key = "beats" if length else "beat"
    if isinstance(value, dict):
        other = "beat" if length else "beats"
        if other in value and key not in value:
            return (f'uses "{other}": a {"length" if length else "time"} in beats is {{"{key}": n}} '
                    f'({"a time takes singular" if not length else "a length takes plural"} "{key}")')
        n = value.get(key)
        if not length and set(value) == {key} and isinstance(n, (int, float)) and not isinstance(n, bool) and n < 0:
            return ("is before bar 1 (a negative beat): a pickup before the song's gridStart is written in seconds "
                    "(a script: at=seconds_of(bar(1) - beats(1)))")
        if set(value) != {key} or isinstance(n, bool) or not isinstance(n, (int, float)) or n < 0:
            return f'must be {{"{key}": n}} with n ≥ 0'
        return None
    if not length and isinstance(value, str) and markers.REF.match(value):
        return None
    return "is not a length" if length else "is not a time"


def forms(length=False, tied=False) -> list[str]:
    if tied:
        return ["seconds (2.5)", '{"beats": 2}', '{"to": "#land"}', '{"to": {"beat": 16}}', '"next"']
    return ["seconds (2.5)", '{"beats": 2}'] if length else ["seconds (2.5)", '{"beat": 8}', '"#drop"',
                                                              '"#drop+0.5"']


def seconds(value, root: dict, where: str, seen=()) -> float:
    """Any time as seconds (beats through the tempo map); marker references go through `markers.py`."""
    t = type(value)
    if t is dict:                                   # the usual note's time first (~100,000 reads per whole-song action)
        if "beat" in value:
            return tempo.seconds_at(root, float(value["beat"]))
        return bar_seconds(value, root, where)
    if t is float or t is int:
        return float(value)
    value = markers.resolve(root, value, where, seen)
    if isinstance(value, dict):
        return tempo.seconds_at(root, float(value["beat"]))
    return float(value)


def bar_seconds(value: dict, root: dict, where: str) -> float:
    """`{"bar": n}` (bars counted from 1, as the ruler shows them) as seconds: a tool's time may name a bar; a stored
    time never does (it is beats). Anything else in a dict is a loud error naming the forms."""
    bar = value.get("bar")
    if set(value) != {"bar"} or isinstance(bar, bool) or not isinstance(bar, int) or bar < 1:
        raise RostrumError(codes.BAD_ARGUMENT, where, f"{value}", 'must be {"bar": n} with n a whole number from 1, or {"beat": n}',
                           ["seconds (2.5)", '{"beat": 8}', '{"bar": 3}', '"#drop"'])
    return tempo.seconds_at(root, meter.bar_start(root, bar))


def length_seconds(value, root: dict, start: float = 0.0, note: dict | None = None, where: str = "length") -> float:
    """A length as seconds, for a thing starting at `start` seconds (beats through the tempo map from there).
    A tie ends where it points; `"next"` needs the `note` (to find its track). A tie that ends at or before its
    start is a loud error, never a silent zero-length note."""
    if value == NEXT or (isinstance(value, dict) and "to" in value):
        end = _next_start(root, note, start, where) if value == NEXT else seconds(value["to"], root, where)
        if end <= start + 1e-6:
            raise RostrumError(codes.CHECK_FAILED, where, f"length {value!r}",
                               f"ends at {end:.3f} s, not after its start at {start:.3f} s",
                               hint=_tie_fix(value, note, start, end))
        return end - start
    if isinstance(value, dict):
        b = tempo.beat_at(root, start)
        return tempo.seconds_at(root, b + float(value["beats"])) - start
    return float(value)



def _tie_fix(value, note, start: float, end: float) -> str:
    """What to write instead of a tie that ends before its note starts, said for the case at hand (a fixed end under a
    moved start, a marker moved past the start, a "next" with nothing after)."""
    to = value["to"] if isinstance(value, dict) else None
    on = markers.ref(note.get("at")) if note else None
    if value == NEXT:
        return 'The note has no later note to hold to: give it a length (dur=beats(2)) or end it on a marker (end="#end").'
    if markers.ref(to) is not None:
        return (f'The marker "{markers.ref(to)}" is now before the note starts ({start:.2f} s): move that marker later than '
                f'{start:.2f} s, or end the note on a marker that is after it (end="#other").')
    if on is not None:
        return (f'The note starts on the marker "{on}" but its end is fixed at {end:g} s, so moving the marker past it breaks '
                f'it. Put a marker on that end, marker("end", at={end:g}), and write end="#end" (until("#end")): a later '
                f'start then makes the note shorter, never refused.')
    return 'End it later (end=...), or give a length (dur=beats(2)).'

def _next_start(root: dict, note: dict | None, start: float, where: str) -> float:
    """Where the next note on `note`'s track starts (notes of the same chord or at the same moment don't count);
    the last note holds to the mix's end. No later note and no mix length: a loud error."""
    track = next((t for t in root.get("tracks", []) if note is not None and
                  any(n is note or (n.get("id") is not None and n.get("id") == note.get("id")) for n in t.get("notes", []))),
                 None)
    if track is None:
        raise RostrumError(codes.CHECK_FAILED, where, 'length "next"', "only a note on a track can hold to the next note")
    later = [s for s in (seconds(n["at"], root, where) for n in track["notes"]) if s > start + 1e-6]
    if later:
        return min(later)
    if root.get("length") is not None:
        return seconds(root["length"], root, where)
    raise RostrumError(codes.CHECK_FAILED, where, 'length "next"',
                       "has no later note on its track and the mix has no length to hold to",
                       ['{"to": "#end"}', "seconds (2.5)"])
