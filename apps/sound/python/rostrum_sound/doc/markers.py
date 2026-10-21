"""Markers: the one place Sound READS them (their list, a marker's time, `"#drop+0.5"` made seconds).

    markers.items(doc)             # [(name, item)] the marker items, in document order
    markers.all(doc)               # [(name, seconds)] by time
    markers.time_of(doc, "drop")   # seconds; raises a not-found error naming the marker (and the ones that exist)
    markers.resolve(doc, "#drop+0.5", where)   # seconds; any other time is returned as written
    markers.ref("#drop+0.5")       # "drop" (the marker a time names) or None

`doc` is a document's root dict. Writes stay operations (`marker.add / set / remove`, doc/ops_mix.py).

Today the markers are the document's own (`doc["markers"]`). When the project service gains shared markers, only
`items()` changes: project markers plus the document's own, and which wins on a clashing name. Every reader
above (the screen's marker band, checks, shifts, the MIDI export, a render's time resolution) follows for free.
"""
from __future__ import annotations

import re

from rostrum_core.errors import RostrumError, codes

from . import tempo

REF = re.compile(r"^#([A-Za-z0-9_.\-]+?)\s*(?:([+-])\s*(\d+(?:\.\d+)?))?$")


def ref(value) -> str | None:
    """The marker a time names ("#drop+0.5" -> "drop"), or None."""
    m = REF.match(value) if isinstance(value, str) else None
    return m.group(1) if m else None


def items(doc: dict) -> list[tuple[str, dict]]:
    """[(name, marker item)] in document order. The one place that decides which markers exist."""
    return [(m.get("name", m["id"]), m) for m in doc.get("markers", [])]


def by_name(doc: dict) -> dict:
    return dict(items(doc))


def _at(marker: dict, name: str, doc: dict, seen) -> float:
    at = resolve(doc, marker.get("at", 0), f"marker {name}", seen)
    return tempo.seconds_at(doc, float(at["beat"])) if isinstance(at, dict) else float(at)


def all(doc: dict) -> list[tuple[str, float]]:  # noqa: A001  reads as `markers.all(doc)`
    """[(name, seconds)] by time."""
    return sorted(((n, _at(m, n, doc, ())) for n, m in items(doc)), key=lambda p: p[1])


def time_of(doc: dict, name: str, where: str = "marker", seen=()) -> float:
    """The marker's time in seconds. A missing marker is a loud error that names it."""
    marks = by_name(doc)
    if name not in marks:
        raise RostrumError.not_found(where, "marker", name, marks)
    if name in seen:
        raise RostrumError(codes.CHECK_FAILED, where, f'marker "{name}"', "refers to itself through other markers")
    return _at(marks[name], name, doc, (*seen, name))


def resolve(doc: dict, value, where: str, seen=()):
    """The time with a marker reference made seconds; seconds and beats are kept as written."""
    name = ref(value)
    if name is None:
        return value
    m = REF.match(value)
    offset = float(m.group(3) or 0) * (-1 if m.group(2) == "-" else 1)
    at = time_of(doc, name, where, seen)
    if at + offset < 0:
        raise RostrumError(codes.BAD_ARGUMENT, where, value, "lands before the start of the mix")
    return round(at + offset, 6)
