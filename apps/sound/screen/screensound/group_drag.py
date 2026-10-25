"""What dragging a track header and the group's M / S do, as calls of the existing operations (no Qt; DESIGN.md §3.15).

Drop a track header on a row of the arrangement: on a group header or on a track inside a group it plays into that
group (`bus.add_track`); on a track that is in no group it leaves its group (`bus.remove_track`). The selected
tracks go together when the dragged one is selected. A group's M is `bus.set mute`; its S solos (or un-solos)
every track in it with the ordinary `track.set solo`. Each gesture is a list of calls: one undo step.
"""
from __future__ import annotations

from rostrum_sound import names


def _tracks(root: dict) -> dict[str, dict]:
    return {t["id"]: t for t in root.get("tracks", [])}


def drop_target(rows: list[dict], over: str) -> tuple[str, str] | None:
    """(what, bus) for a drop on row `over`: ("join", group id) or ("leave", "") — None where a drop means nothing
    (the compact bus and master rows)."""
    row = next((r for r in rows if r["id"] == over), None)
    if row is None or (row.get("mix") and not row.get("group")):
        return None
    if row.get("group"):
        return "join", row["id"]
    return ("join", row["bus"]) if row.get("bus") else ("leave", "")


def _place(root: dict, mine: list[str], over: str, below: bool) -> list[dict]:
    """The `track.move` that puts `mine` just above (or, `below`, just under) the track `over` in the track list ([] when
    they already sit there)."""
    order = [t["id"] for t in root.get("tracks", [])]
    rest = [t for t in order if t not in mine]
    if over not in rest:
        return []
    at = rest.index(over) + (1 if below else 0)
    if order == rest[:at] + [t for t in order if t in mine] + rest[at:]:
        return []
    return [{"op": "track.move", "target": mine, "args": {"after": rest[at - 1] if at else "top"}}]


def drop_calls(root: dict, rows: list[dict], dragged: list[str], over: str, below: bool = False) -> list[dict]:
    """The calls for dropping `dragged` track ids on row `over` ([] when nothing would change). On a group's header: they
    join the group. On a track: they move to sit above it (`below`: under it) and take its group, or leave theirs when it
    has none: so a drop between two rows is where they go, and joining or leaving a group is the same drop."""
    target, tracks = drop_target(rows, over), _tracks(root)
    mine = [t for t in dragged if t in tracks and t != over]
    if target is None or not mine:
        return []
    what, bus = target
    calls: list[dict] = []
    if what == "join":
        moving = [t for t in mine if tracks[t].get("output", names.MASTER_OUT) != bus]
        calls = [{"op": "bus.add_track", "target": [bus], "args": {"tracks": moving}}] if moving else []
    else:
        out: dict[str, list[str]] = {}
        for t in mine:
            here = tracks[t].get("output", names.MASTER_OUT)
            if here in {b["id"] for b in root.get("buses", [])}:
                out.setdefault(here, []).append(t)
        calls = [{"op": "bus.remove_track", "target": [b], "args": {"tracks": ts}} for b, ts in out.items()]
    if over in tracks:
        calls += _place(root, mine, over, below)
    return calls


def members(root: dict, bus: str) -> list[str]:
    """Every track playing into `bus`, down through groups inside it."""
    kids = [x for x in [*root.get("tracks", []), *root.get("buses", [])] if x.get("output") == bus]
    return [k["id"] for k in kids if k.get("type") != "bus"] + [m for k in kids if k.get("type") == "bus" for m in members(root, k["id"])]


def toggle_calls(root: dict, bus: str, field: str) -> tuple[list[dict], str]:
    """The calls and the step's name for the group's M or S."""
    item = next(b for b in root["buses"] if b["id"] == bus)
    name = item.get("name") or bus
    if field == "mute":
        on = not item.get("mute")
        return [{"op": "bus.set", "target": [bus], "args": {"mute": on}}], f"{'Mute' if on else 'Unmute'} {name}"
    tracks = _tracks(root)
    ids = members(root, bus)
    on = not all(tracks[t].get("solo") for t in ids)
    return ([{"op": "track.set", "target": [t], "args": {"solo": on}} for t in ids if bool(tracks[t].get("solo")) != on],
            f"{'Solo' if on else 'Un-solo'} {name}")
