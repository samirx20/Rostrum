"""What one step of a drag changed, so the screen re-makes only that (no Qt).

A drag's step (a gesture preview) carries no list of edits, but the document is never changed in place: an edited
item is a new dict and its parents are new too, while everything it did not touch stays the very same object
(rostrum_core.edits.fork). So comparing the song before and after the step by identity tells which tracks it
changed, at the cost of one pass over the top of the song.
"""
from __future__ import annotations

MIX = ("buses", "master")       # their rows (timeline.rows' compact mix rows) are made again on every step anyway


def changed_tracks(before: dict | None, now: dict) -> set[str] | None:
    """The ids of the tracks the step changed (an empty set: no track), or None when it changed something else
    too (the tempo, a marker, a section …) or tracks came, went or moved: then everything is made again. A bus or
    the master may change: only the mix rows show them, and those are always made again."""
    if before is None:
        return None
    if before is now:
        return set()
    if before.keys() != now.keys():
        return None
    for key, value in now.items():
        if key != "tracks" and key not in MIX and value is not before[key] and value != before[key]:
            return None
    old, new = before.get("tracks", []), now.get("tracks", [])
    if len(old) != len(new) or any(a["id"] != b["id"] for a, b in zip(old, new)):
        return None
    return {b["id"] for a, b in zip(old, new) if a is not b}
