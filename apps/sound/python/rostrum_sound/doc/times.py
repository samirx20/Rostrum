"""Times in a Sound document: the one place they are read and turned into seconds.

A time is seconds (a number), `{"beat": n}` (beats from the start), or a marker reference `"#drop"`,
`"#drop+0.5"`, `"#drop-1"` (seconds after / before the marker named "drop"; a trailing "-<number>" is always
an offset, so "#big-hit-1" is one second before "big-hit"). A length is seconds or
`{"beats": n}` (beats from where the thing starts). Marker references are resolved here (the engine never sees
them); beats are left to the engine, which gets the same tempo map (`tempo.py`, the one place beats become
seconds), except where seconds are needed here (ids, order checks, marker references, the screen).
"""
from __future__ import annotations

from . import markers, tempo


def problem(value, length=False) -> str | None:
    """Why `value` is not a time (or a length), or None when it is one. Shapes only: markers are checked later."""
    if isinstance(value, bool):
        return "is not a time"
    if isinstance(value, (int, float)):
        return None if value >= 0 else "can't be negative"
    key = "beats" if length else "beat"
    if isinstance(value, dict):
        n = value.get(key)
        if set(value) != {key} or isinstance(n, bool) or not isinstance(n, (int, float)) or n < 0:
            return f'must be {{"{key}": n}} with n ≥ 0'
        return None
    if not length and isinstance(value, str) and markers.REF.match(value):
        return None
    return "is not a length" if length else "is not a time"


def forms(length=False) -> list[str]:
    return ["seconds (2.5)", '{"beats": 2}'] if length else ["seconds (2.5)", '{"beat": 8}', '"#drop"',
                                                              '"#drop+0.5"']


def seconds(value, root: dict, where: str, seen=()) -> float:
    """Any time as seconds (beats through the tempo map); marker references go through `markers.py`."""
    value = markers.resolve(root, value, where, seen)
    if isinstance(value, dict):
        return tempo.seconds_at(root, float(value["beat"]))
    return float(value)


def length_seconds(value, root: dict, start: float = 0.0) -> float:
    """A length as seconds, for a thing starting at `start` seconds (beats through the tempo map from there)."""
    if isinstance(value, dict):
        b = tempo.beat_at(root, start)
        return tempo.seconds_at(root, b + float(value["beats"])) - start
    return float(value)

