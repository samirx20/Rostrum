"""The notes a document writes, as plain rows with seconds: what the pitch and harmony looks compare the sound to."""
from __future__ import annotations

from rostrum_core import RostrumError, codes

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
            rows.append({"track": tr["id"], "id": n.get("id"), "start": start, "end": start + _length(n, root, start, w),
                         "midis": sorted(keys.midis(n["pitch"])), "vel": n.get("vel")})
    return sorted(rows, key=lambda r: (r["start"], r["midis"]))


def _length(n: dict, root: dict, start: float, w: str) -> float:
    """A tie that ends before its note starts (a marker moved past it) is a named warning in every reply and the
    render refuses it (doc/past_end.py); here it reads as no length, as look_arrangement draws it, so a look, the
    diagnose list or a run's reply never fails on it after the change is in."""
    try:
        return times.length_seconds(n["dur"], root, start, n, w)
    except RostrumError as e:
        if e.code != codes.CHECK_FAILED:
            raise
        return 0.0


def instrument_spec(root: dict, track_id: str) -> dict | None:
    """The engine's instrument object for a track (what a `range` request takes), or None for a track with none."""
    from ..compile import _Compiler
    tr = next((t for t in root.get("tracks", []) if t["id"] == track_id), None)
    return _Compiler(root).instrument(tr).get("instrument") if tr else None
