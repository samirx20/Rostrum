"""The shared marker tools every server has: inspect_markers, edit_markers (CONVENTIONS § 2).

Markers are the project's one list (`rostrum_core.markers`), not any one document's, so both tools work on the
server's project folder. Changes go through the marker document's own `apply`, so they are in its history.
"""
from __future__ import annotations

import json

from .. import markers as M
from .. import marker_times, song_markers
from ..errors import RostrumError, codes
from .reply import Reply
from .tools import Tools

_CALL = {"type": "object", "required": ["op"], "additionalProperties": False, "properties": {
    "op": {"enum": ["marker.add", "marker.move", "marker.rename", "marker.colour", "marker.remove", "marker.set"]},
    "target": {"type": "array", "items": {"type": "string"}, "description": "Markers by id (from inspect_markers) or by name (\"drop\")."},
    "args": {"type": "object", "description": 'marker.add {"name", "at", optional "owner", "colour"}; marker.move {"at"}; marker.rename {"name"}; marker.colour {"colour"}. marker.set {"at"/"name"/"colour"} is read as those.'}}}


def _folder(ctx):
    if not ctx.app.folder:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, "this server", "was started without a project folder",
                           hint="Markers belong to a project; start the server with one.")
    return ctx.app.folder


def _by_id(folder, calls: list) -> list:
    """The calls with each target written as a marker's name ("drop") turned into its id (mk_drop_1); ids, and words
    that are neither, pass as they are (an unknown one is refused by the operation, naming the markers)."""
    every = M.listing(folder)
    known, ids = {m["id"] for m in every}, {M._key(m["name"]): m["id"] for m in every}
    name = lambda t: t if t in known else ids.get(M._key(t), t)  # noqa: E731
    return [{**c, "target": [name(t) for t in c["target"]]} if c.get("target") else c for c in calls]


def _line(m: dict) -> str:
    return f'"{m["name"]}" at {m["at"]:g} s ({m["id"]})'


def register(tools: Tools):
    @tools.tool("inspect_markers", {"properties": {
        "name": {"type": "string", "description": "One marker by name or id; with an offset (\"drop+0.5\") gives its time."}}})
    def inspect_markers(ctx, args):
        """The project's named markers (every app reads the same list): id, name, time in seconds, who made it. Then
        the songs' own markers (`song_markers`: made in RostrumSound, e.g. marker() in its script): read-only here,
        found by name like any marker (look_frame, "#name" times); change them in RostrumSound."""
        folder = _folder(ctx)
        every = M.listing(folder)
        songs = song_markers.times(folder) if args.get("songs", True) else {}
        if args.get("name"):
            ref = marker_times.split(f'#{args["name"]}')
            if ref and M.lookup({m["name"]: m["at"] for m in every}, ref[0]) is None and M.lookup(songs, ref[0]) is not None:
                at = round(M.lookup(songs, ref[0]) + ref[1], 6)
                return Reply(f'"{args["name"]}" (a song’s own marker) is at {at:g} s.', {"at": at})
            at = M.at(None, args["name"], every)
            return Reply(f'"{args["name"]}" is at {at:g} s.', {"at": at})
        said = "; ".join(_line(m) for m in every) or "none yet (add one with edit_markers)"
        extra = {n: t for n, t in songs.items() if M.lookup({m["name"]: m["at"] for m in every}, n) is None}
        line = (f" Songs' own markers (read-only here; change them in RostrumSound): "
                + "; ".join(f'"{n}" at {t:g} s' for n, t in extra.items()) + ".") if extra else ""
        return Reply(f"{len(every)} marker{'s' * (len(every) != 1)}: {said}.{line}",
                     {"markers": every, **({"song_markers": [{"name": n, "at": t} for n, t in extra.items()]} if extra else {})})

    @tools.tool("edit_markers", {"required": ["ops"], "properties": {
        "ops": {"type": "array", "minItems": 1, "items": _CALL}, "label": {"type": "string"}}})
    def edit_markers(ctx, args):
        """Add, move, rename or delete the project's named markers, all or nothing, as one step in their history. marker.move is the one name for moving a marker; a target may be its id or its name (marker.move is also what edit_document takes for a marker that is only in one song; marker.set is read as it)."""
        folder = _folder(ctx)
        change = M.edit(folder, _by_id(folder, args["ops"]), ctx.who, args.get("label"))
        names = [c["op"] for c in args["ops"]]
        if change is None:
            return Reply(f"Nothing changed: {', '.join(names)} left every marker as it was.", {})
        every = M.listing(folder)
        return Reply(f"Applied {', '.join(names)} as marker change {change.seq}. Markers now: "
                     f"{'; '.join(_line(m) for m in every) or 'none'}.", {"markers": every},
                     changed={"seq": change.seq, "ops": names, "item": M.ITEM,
                              "edits": json.loads(json.dumps([vars(e) for e in change.edits], default=str))})
