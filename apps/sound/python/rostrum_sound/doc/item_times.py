"""Where a note or a drum hit starts and ends, in seconds, worked out once per item and kept: the whole-song readers
(the action list's chords and span, the past-the-end checks, the screen's rows) ask for every item's times after every
change and every selection, and most items are the very same objects as before (a change copies only what it edits).

Kept by the item's id and checked by identity: the item, its `at` and its `dur` are the same objects as when the times
were worked out (an edit writes a new item and a new value, never in place: rostrum_core/edits.py), and the tempo data
is the same (`tempo.key`, by value). Only times that need nothing else are kept: seconds or beats. A time on a marker
and a tied length (`{"to": …}`, `"next"`) read other items, so they are worked out each time (`span` gives None).
"""
from __future__ import annotations

from . import tempo, times

_KEPT: dict[str, tuple] = {}         # id -> (item, at, dur, tempo key, (start, end))
_MOST = 100_000                      # a few songs' worth; then started again


def _plain(v, length: bool) -> bool:
    t = type(v)
    return t is float or t is int or (t is dict and (("beats" in v) if length else ("beat" in v)))


def span(root: dict, item: dict) -> tuple[float, float] | None:
    """(start, end) seconds of a note or a hit (a hit ends where it starts), or None when its times read other items
    (a marker, a tie) or it is something else: the caller works those out itself."""
    kind = item.get("type")
    at, dur = item.get("at"), item.get("dur")
    k = tempo.key(root)
    kept = _KEPT.get(item.get("id"))
    if kept is not None and kept[0] is item and kept[1] is at and kept[2] is dur and kept[3] == k:
        return kept[4]
    if not ((kind == "note" and _plain(dur, True)) or kind == "hit") or not _plain(at, False):
        return None
    start = times.seconds(at, root, item["id"])
    out = (start, start + times.length_seconds(dur, root, start) if kind == "note" else start)
    if len(_KEPT) >= _MOST:
        _KEPT.clear()
    _KEPT[item["id"]] = (item, at, dur, k, out)
    return out
