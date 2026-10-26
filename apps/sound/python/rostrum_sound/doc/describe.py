"""One item as a short phrase for an edit's reply (DocKind.describe): "harp.n8438 at 8.44 s E2 1/8", a hit with its drum
and time, a clip with its range. Other types: None (the id alone). Times through the song's own helpers (times, musical)."""
from __future__ import annotations

from rostrum_core import RostrumError

from . import item_times, musical, times


def _start(root: dict, item: dict) -> float | None:
    got = item_times.span(root, item)
    if got is not None:
        return got[0]
    try:
        return times.seconds(item["at"], root, item.get("id", "item"))
    except (RostrumError, KeyError, TypeError, ValueError):
        return None


def describe(item: dict, root: dict) -> str | None:
    kind = item.get("type")
    if kind not in ("note", "hit", "clip"):
        return None
    s = _start(root, item)
    where = f" at {s:.2f} s" if s is not None else ""
    if kind == "hit":
        return f"{item['id']}{where} {item.get('drum')}"
    if kind == "clip":
        try:
            end = s + times.length_seconds(item["length"], root, s) if "length" in item else None
        except (RostrumError, TypeError, ValueError):
            end = None
        return f"{item['id']}{where}" + (f"-{end:.2f} s" if end is not None else "") + f" {item.get('media', '')}".rstrip()
    out = f"{item['id']}{where} {musical.note_name(item.get('pitch'))}"
    try:
        span = item_times.span(root, item)
        if span is not None:
            out += " " + musical.note_length(span[1] - span[0], root, span[0])
    except (RostrumError, ValueError):
        pass
    return out
