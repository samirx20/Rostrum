"""Times in a Sound document: the one place they are read and turned into seconds.

A time is seconds (a number), `{"beat": n}` (beats from the start), or a marker reference `"#drop"`,
`"#drop+0.5"`, `"#drop-1"` (seconds after / before the marker named "drop"). A length is seconds or
`{"beats": n}`. Marker references are resolved here (the engine never sees them); beats are left to the
engine's tempo map, except where seconds are needed (ids, order checks, marker references).
"""
from __future__ import annotations

import re

from rostrum_core.errors import RostrumError, codes

REF = re.compile(r"^#([A-Za-z0-9_.\-]+)\s*(?:([+-])\s*(\d+(?:\.\d+)?))?$")


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
    if not length and isinstance(value, str) and REF.match(value):
        return None
    return "is not a length" if length else "is not a time"


def forms(length=False) -> list[str]:
    return ["seconds (2.5)", '{"beats": 2}'] if length else ["seconds (2.5)", '{"beat": 8}', '"#drop"',
                                                              '"#drop+0.5"']


def marker_ref(value) -> str | None:
    """The marker a time names ("#drop+0.5" -> "drop"), or None."""
    m = REF.match(value) if isinstance(value, str) else None
    return m.group(1) if m else None


def markers(root: dict) -> dict:
    """name -> the marker item, from a document's root."""
    return {m.get("name", m["id"]): m for m in root.get("markers", [])}


def bpm(root: dict) -> float:
    return float(root.get("tempo", 120))


def resolve(value, root: dict, where: str, seen=()):
    """The time with marker references made seconds; seconds and beats are kept as written."""
    name = marker_ref(value)
    if name is None:
        return value
    marks = markers(root)
    if name not in marks:
        raise RostrumError.not_found(where, "marker", name, marks)
    if name in seen:
        raise RostrumError(codes.CHECK_FAILED, where, f'marker "{name}"', "refers to itself through other markers")
    m = REF.match(value)
    offset = float(m.group(3) or 0) * (-1 if m.group(2) == "-" else 1)
    at = seconds(marks[name].get("at", 0), root, f"marker {name}", (*seen, name))
    if at + offset < 0:
        raise RostrumError(codes.BAD_ARGUMENT, where, value, "lands before the start of the mix")
    return round(at + offset, 6)


def seconds(value, root: dict, where: str, seen=()) -> float:
    """Any time as seconds (beats through the document's tempo)."""
    value = resolve(value, root, where, seen)
    if isinstance(value, dict):
        return float(value["beat"]) * 60.0 / bpm(root)
    return float(value)


def length_seconds(value, root: dict) -> float:
    if isinstance(value, dict):
        return float(value["beats"]) * 60.0 / bpm(root)
    return float(value)
