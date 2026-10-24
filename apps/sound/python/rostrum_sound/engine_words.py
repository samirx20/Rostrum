"""The engine names a problem by its place in the schedule it was sent ("schedule.tracks[0].effects[0].path"). An agent
never sees a schedule, so the place is said in the song's own words: "effect 1 (plugin) on track fxt: path ..."."""
from __future__ import annotations

import re

_PLACE = re.compile(r"^schedule\.tracks\[(\d+)\](?:\.(effects|clips|notes|hits)\[(\d+)\])?(?:\.(.+))?$")
_ONE = {"effects": "effect", "clips": "clip", "notes": "note", "hits": "hit"}


def plain_where(where: str, request: dict) -> str:
    """`where` as words, using the request's schedule to name the track; anything else is returned as it is."""
    m = _PLACE.match(where or "")
    tracks = (request.get("schedule") or {}).get("tracks") or []
    if not m or int(m[1]) >= len(tracks):
        return where
    track = tracks[int(m[1])]
    what = f"track {track.get('id', int(m[1]) + 1)}"
    if m[2]:
        i, parts = int(m[3]), track.get(m[2]) or []
        kind = f" ({parts[i]['type']})" if m[2] == "effects" and i < len(parts) and parts[i].get("type") else ""
        what = f"{_ONE[m[2]]} {i + 1}{kind} on {what}"
    return what + (f", {m[4]}" if m[4] else "")
