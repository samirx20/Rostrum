"""The Timeline's edits as operation calls (no Qt): moving a note / hit / clip / marker in time (and a note in
pitch), adding a note, deleting the selection, a track's quick mute / solo. Times are written in the form the
item used (timing.write_time); a drag snaps to a quarter beat unless free.
"""
from __future__ import annotations

from rostrum_core import RostrumError, codes

from . import timing

MOVABLE = ("note", "hit", "clip", "line", "marker")
REMOVABLE = ("note", "hit", "clip", "line", "marker", "track", "effect", "automation", "bus", "send", "duck")
LABELS = {"note": "Move note", "hit": "Move drum hit", "clip": "Move clip", "line": "Move line", "marker": "Move marker"}


def grab(doc, item_id) -> dict:
    """What a drag starts from: the item's id, type, time (seconds) and pitch."""
    it = doc.item(item_id)
    if it["type"] not in MOVABLE:
        raise RostrumError(codes.BAD_ARGUMENT, "timeline drag", f'"{item_id}"', "can't be moved in time",
                           list(MOVABLE))
    return {"id": item_id, "type": it["type"], "at": it["at"], "t": timing.sec(it["at"], doc.data, item_id),
            "pitch": it.get("pitch")}


def drag_calls(doc, g: dict, dt: float, dsemi: int = 0, free: bool = False) -> list[dict]:
    """The calls for a drag `dt` seconds (and `dsemi` semitones, notes only) from where it started."""
    root = doc.data
    args = {"at": timing.write_time(g["at"], timing.snap(g["t"] + dt, root, free), root)}
    if g["type"] == "note" and dsemi:
        args["pitch"] = timing.shift_pitch(g["pitch"], int(dsemi))
    return [{"op": f"{g['type']}.set", "target": [g["id"]], "args": args}]


def add_note_call(doc, track_id, t: float, key: int, free: bool = False) -> dict:
    """A one-beat note at `t` on `key`, written in the form the track's notes already use (beats by default)."""
    root, track = doc.data, doc.item(track_id)
    first = next(iter(track.get("notes", [])), None)
    secs = first is not None and isinstance(first["at"], (int, float))
    at = timing.snap(t, root, free)
    pitch = key if first is not None and isinstance(first["pitch"], int) else timing.name(key)
    if secs:
        args = {"at": round(at, 4), "dur": round(timing.spb(root), 4)}
    else:
        args = {"at": {"beat": round(at / timing.spb(root), 4)}, "dur": {"beats": 1}}
    return {"op": "note.add", "target": [track_id], "args": {"pitch": pitch, **args}}


def remove_call(doc, item_id) -> dict:
    kind = doc.item(item_id)["type"]
    if kind not in REMOVABLE:
        raise RostrumError(codes.BAD_ARGUMENT, "delete", f'"{item_id}"', "can't be deleted", list(REMOVABLE))
    return {"op": f"{kind}.remove", "target": [item_id], "args": {}}


def toggle_call(doc, track_id, field: str) -> tuple[dict, str]:
    if field not in ("mute", "solo"):
        raise RostrumError(codes.BAD_ARGUMENT, "track header", f'"{field}"', "is not a quick toggle",
                           ["mute", "solo"])
    on = not doc.item(track_id).get(field)
    name = doc.item(track_id).get("name") or track_id
    return ({"op": "track.set", "target": [track_id], "args": {field: on}},
            f"{'Turn on' if on else 'Turn off'} {field} on {name}")
