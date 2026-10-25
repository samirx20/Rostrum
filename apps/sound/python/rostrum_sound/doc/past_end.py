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


RINGING_S = 0.5      # a sound still held (or just struck) this close to the end is cut off audibly


def hard_end(data: dict) -> str:
    """The song stops dead on sound: its soft end (`endFade`) is off and a note is still held, or a hit or clip still
    sounds, in its last half second. "" when not (or when it ends after the last sound: no `length`)."""
    if data.get("length") is None or data.get("endFade", True):
        return ""
    try:
        end = times.seconds(data["length"], data, "length")
        for t in data.get("tracks", []):
            for n in t.get("notes", []):
                at = times.seconds(n["at"], data, n["id"])
                if at < end and at + times.length_seconds(n["dur"], data, at, n, n["id"]) > end - RINGING_S:
                    return n["id"]
            for h in t.get("hits", []):
                if end - RINGING_S < times.seconds(h["at"], data, h["id"]) < end:
                    return h["id"]
            for c in t.get("clips", []):          # a clip with no length plays to its file's end: taken as still playing
                at = times.seconds(c["at"], data, c["id"])
                if at < end and (c.get("length") is None or at + times.length_seconds(c["length"], data, at) > end - RINGING_S):
                    return c["id"]
    except RostrumError:
        return ""                                    # a broken time is the check's to report
    return ""


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
