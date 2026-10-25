"""The Timeline's edits as operation calls (no Qt): moving a note / hit / clip / marker in time (and a note in
pitch), adding a note, deleting the selection, a track's quick mute / solo. Times are written in the form the
item used (timing.write_time). A drag snaps (DESIGN.md §5) unless free (Ctrl): to a marker or the playhead when
the grabbed item's start is within the kit's 6 px of one, else to the grid. Several selected items move together
(`grab_many` / `many_calls`): each by the same amount, the one grabbed decides the snap.
"""
from __future__ import annotations

from rostrum_core import RostrumError, codes
from rostrum_gui import snap

from . import key_lock, song_edit, timing
from .moves_add import add_hit_call, add_note_call, add_note_calls  # noqa: F401  (the Timeline's adds; moves.* stays the one door)
from .timeline import kind_of, roll_drums

MANY = ("note", "hit", "clip", "line")          # what moves together when several are selected
MOVABLE = ("note", "hit", "clip", "line", "marker", "section", "tempo", "meter", "key")
REMOVABLE = ("note", "hit", "clip", "line", "marker", "track", "effect", "automation", "bus", "send", "duck",
             "tempo", "meter", "key", "section")
LABELS = {"note": "Move note", "hit": "Move drum hit", "clip": "Move clip", "line": "Move line", "marker": "Move marker",
          "section": "Move section", "tempo": "Move tempo change", "meter": "Move time signature change", "key": "Move key change",
          "edge": "Resize section"}


def grab(doc, item_id) -> dict:
    """What a drag starts from: the item's id, type, time (seconds) and pitch."""
    it = doc.item(item_id)
    if it["type"] not in MOVABLE:
        raise RostrumError(codes.BAD_ARGUMENT, "timeline drag", f'"{item_id}"', "can't be moved in time",
                           list(MOVABLE))
    return {"id": item_id, "type": it["type"], "at": it["at"], "t": timing.sec(it["at"], doc.data, item_id),
            "pitch": it.get("pitch"), "drum": it.get("drum")}


def drag_calls(doc, g: dict, dt: float, dsemi: int = 0, free: bool = False, grid=None, lock: bool = False) -> list[dict]:
    """The calls for a drag `dt` seconds (and `dsemi` semitones, notes only) from where it started."""
    root = doc.data
    if g["type"] == "section":
        return section_calls(doc, g, dt, free, grid)
    if g["type"] in song_edit.TYPES:
        return song_edit.drag_calls(doc, g, dt, free, grid)
    to = timing.snap(g["t"] + dt, root, free, grid)
    args = {"at": timing.write_time(g["at"], to, root)}
    if g["type"] == "note" and dsemi:
        args["pitch"] = key_lock.shifted(root, to, g["pitch"], int(dsemi), lock and not free)
    return [{"op": f"{g['type']}.set", "target": [g["id"]], "args": args}]


def grab_many(doc, ids, primary) -> dict:
    """A drag of every selected note / hit / clip / line, held by `primary` (the one under the pointer)."""
    return {"primary": grab(doc, primary), "items": [grab(doc, i) for i in ids if doc.item(i)["type"] in MANY]}


def snap_to(t: float, root: dict, free: bool, targets: list[snap.Target], scale: float, grid=None) -> tuple[float, dict]:
    """(where `t` lands, what it caught: {"t", "name"}; {} when free). Markers and the playhead catch within the kit's
    6 px (`scale` = screen px per second; 0 = catch nothing), strongest first; otherwise the grid."""
    if free:
        return max(0.0, round(t, 4)), {}
    caught = snap.snap(t, targets, scale) if scale > 0 else None
    if caught is not None and caught.target is not None:
        return caught.value, {"t": caught.value, "name": caught.name}
    if not (grid or timing.DEFAULT).on:
        return max(0.0, round(t, 4)), {}
    g = timing.snap(t, root, False, grid)
    return g, {"t": g, "name": ""}


def many_calls(doc, g: dict, dt: float, dsemi: int, free: bool, only_time: bool, targets: list[snap.Target], scale: float,
               grid=None, end=None, lock=False):
    """(calls, what it snapped to) for moving every grabbed item by the same amount: the grabbed one snaps, the rest
    follow; never before the song's start, and with `end` (a song of a set length, seconds) none starts later than one
    grid step before its end (a note dragged past it would vanish from the screen and never play). `dsemi`: semitones for notes, drum rows for hits (down is +). Shift
    (`only_time`): no pitch or drum change."""
    root, p = doc.data, g["primary"]
    to, caught = snap_to(p["t"] + dt, root, free, targets, scale, grid)
    d = max(to - p["t"], -min(x["t"] for x in g["items"]))
    if end is not None:
        last = timing.lines_around(max(0.0, end - 1e-6), root, grid)[0]      # the grid line before the end
        d = min(d, last - max(x["t"] for x in g["items"]))
    calls = []
    for x in g["items"]:
        args = {"at": timing.write_time(x["at"], max(0.0, x["t"] + d), root)}
        if x["type"] == "note" and dsemi and not only_time:
            args["pitch"] = key_lock.shifted(root, max(0.0, x["t"] + d), x["pitch"], int(dsemi), lock and not free)
        if x["type"] == "hit" and dsemi and not only_time and x["drum"]:     # up or down the drum rows the roll shows
            rows = roll_drums(doc.item(doc.parent_of(x["id"])[0]))
            if x["drum"] in rows:
                args["drum"] = rows[max(0, min(len(rows) - 1, rows.index(x["drum"]) + int(dsemi)))]
        calls.append({"op": f"{x['type']}.set", "target": [x["id"]], "args": args})
    return calls, caught


def track_calls(doc, g: dict, dest: str) -> list[dict]:
    """Clips dragged onto another row: one `clip.to_track` when that track can hold them (an
    audio or empty track, not a voice track) for the clips not on it already; none otherwise (they stay on their
    own tracks: a move along its own row stays a plain move)."""
    movers = [x["id"] for x in g["items"] if x["type"] == "clip" and doc.parent_of(x["id"])[0] != dest]
    if not movers or not dest or not doc.has(dest) or doc.item(dest)["type"] != "track":
        return []
    if kind_of(doc.item(dest)) not in ("audio", "empty") or doc.item(dest).get("instrument") == "voice":
        return []
    return [{"op": "clip.to_track", "target": movers, "args": {"track": dest}}]


def track_refusal(doc, g: dict, dest: str) -> str:
    """Why clips let go over another track did not go there ("" when they did, or stayed on their own row)."""
    movers = [x for x in g.get("items", []) if x["type"] == "clip" and doc.parent_of(x["id"])[0] != dest]
    if not movers or not dest or not doc.has(dest) or doc.item(dest)["type"] != "track" or track_calls(doc, g, dest):
        return ""
    t = doc.item(dest)
    what = "a voice track" if t.get("instrument") == "voice" else "a notes track" if kind_of(t) == "notes" else "a drum track"         if kind_of(t) == "drums" else "that track"
    return f"A clip can't go on {t.get('name') or dest}: it is {what}. Drop it on an audio track or an empty one."


def copy_calls(g: dict) -> list[dict]:
    """Alt-drag: copies left where the items were (each kind's `.duplicate` by 0), the originals move on."""
    by: dict[str, list[str]] = {}
    for x in g["items"]:
        if x["type"] != "line":
            by.setdefault(x["type"], []).append(x["id"])
    return [{"op": f"{k}.duplicate", "target": ids, "args": {"by": 0}} for k, ids in by.items()]


def section_calls(doc, g: dict, dt: float, free: bool = False, grid=None) -> list[dict]:
    """A section dragged: one `section.move` (it and everything inside), by what is left to go from where it is
    now (a drag previews on top of itself), in beats when the section is written in beats."""
    root = doc.data
    at = doc.item(g["id"])["at"]
    now, to = timing.sec(at, root, g["id"]), timing.snap(g["t"] + dt, root, free, grid)
    by = {"beats": round(timing.beat(to, root) - timing.beat(now, root), 4)} if isinstance(at, dict)         else round(to - now, 4)
    if abs(by["beats"] if isinstance(by, dict) else by) < 1e-6:
        return []
    return [{"op": "section.move", "target": [g["id"]], "args": {"by": by}}]


def remove_calls(doc, kind, ids) -> list[dict]:
    """The calls that delete items of one kind (the one place, for the Delete key and the Delete action). A group
    that tracks play to or send to goes the way Ungroup does: its tracks keep playing where the group played to and
    the sends into it go with it, never a refusal."""
    if kind not in REMOVABLE:
        raise RostrumError(codes.BAD_ARGUMENT, "delete", f'"{ids[0]}"', "can't be deleted", list(REMOVABLE))
    if kind != "bus":
        return [{"op": f"{kind}.remove", "target": list(ids), "args": {}}]
    sends = [s["id"] for t in doc.data.get("tracks", []) for s in t.get("sends", []) if s.get("bus") in ids]
    return ([{"op": "send.remove", "target": sends, "args": {}}] if sends else []) +            [{"op": "bus.ungroup", "target": list(ids), "args": {}}]


def toggle_call(doc, item_id, field: str) -> tuple[dict, str]:
    """A quick mute / solo on a track, bus or the master: one call, one set of History words ("Mute pad")."""
    if field not in ("mute", "solo"):
        raise RostrumError(codes.BAD_ARGUMENT, "quick toggle", f'"{field}"', "is not a quick toggle",
                           ["mute", "solo"])
    from rostrum_gui.edits import field_call
    from .inspect import name_of
    item = doc.item(item_id)
    on = not item.get(field)
    word = {"mute": "Mute" if on else "Unmute", "solo": "Solo" if on else "Unsolo"}[field]
    return field_call(doc, item_id, field, on), f"{word} {name_of(item)}"
