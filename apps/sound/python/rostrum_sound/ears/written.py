"""The notes a document writes, as plain rows with seconds: what the pitch and harmony looks compare the sound to."""
from __future__ import annotations

from ..doc import keys, times


def written_notes(root: dict, track_ids=None) -> list[dict]:
    """[{track, id, start, end, midis (a chord is several), vel}] sorted by start, from every pitched, unmuted track
    (or just `track_ids`). Times come through the tempo map and markers, as the render reads them."""
    rows = []
    for tr in root.get("tracks", []):
        if (track_ids is not None and tr["id"] not in track_ids) or tr.get("mute"):
            continue
        for n in tr.get("notes", []):
            w = f"tracks[{tr['id']}].notes[{n.get('id', '?')}]"
            start = times.seconds(n["at"], root, w)
            rows.append({"track": tr["id"], "id": n.get("id"), "start": start,
                         "end": start + times.length_seconds(n["dur"], root, start, n, w),
                         "midis": sorted(keys.midis(n["pitch"])), "vel": n.get("vel")})
    return sorted(rows, key=lambda r: (r["start"], r["midis"]))


def instrument_spec(root: dict, track_id: str) -> dict | None:
    """The engine's instrument object for a track (what a `range` request takes), or None for a track with none."""
    from ..compile import _Compiler
    tr = next((t for t in root.get("tracks", []) if t["id"] == track_id), None)
    return _Compiler(root).instrument(tr).get("instrument") if tr else None
