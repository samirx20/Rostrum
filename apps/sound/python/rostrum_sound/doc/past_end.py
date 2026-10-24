"""Timing that single fields can't see, said in every reply (DocKind.warn) as soon as it happens, not first at render_mix.
Warnings, not refusals: a project marker moved in another app can cause either, and a song must still open.

- a tied note (`dur {"to": …}` / `"next"`) that ends at or before its start: the render refuses it;
- notes, hits and clips that start at or after the song's `length`: they are never heard.
"""
from __future__ import annotations

from rostrum_core import RostrumError

from . import times

SHOWN = 3


def ties(data: dict) -> list[str]:
    out = []
    for t in data.get("tracks", []):
        for n in t.get("notes", []):
            d = n.get("dur")
            if d == times.NEXT or (isinstance(d, dict) and "to" in d):
                try:
                    times.length_seconds(d, data, times.seconds(n["at"], data, n["id"]), n, n["id"])
                except RostrumError as e:
                    out.append(f"{n['id']}: {e.subject} {e.problem}: render_mix refuses it until the note ends after it starts." + (f" {e.hint}" if e.hint else ""))
    return out


def warn(data: dict) -> list[str]:
    return ties(data) + late(data)


def late(data: dict) -> list[str]:
    if data.get("length") is None:
        return []
    try:
        end = times.seconds(data["length"], data, "length")
        late = [(i["id"], s) for t in data.get("tracks", []) for k in ("notes", "hits", "clips")
                for i in t.get(k, []) if (s := times.seconds(i["at"], data, i["id"])) >= end - 1e-6]
    except RostrumError:
        return []                                    # a broken time is the check's to report
    if not late:
        return []
    shown = ", ".join(f"{i} at {s:.2f} s" for i, s in late[:SHOWN]) + (f" and {len(late) - SHOWN} more" if len(late) > SHOWN else "")
    return [f"{len(late)} note(s), hit(s) or clip(s) start at or after the song's end ({end:.2f} s) and are never heard: {shown}. "
            "Move them earlier or make the song longer (length)."]
