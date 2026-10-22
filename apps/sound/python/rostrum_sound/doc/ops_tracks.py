"""Tracks and the document's own settings: track.add / set / remove / lock / unlock, doc.set. A locked track
(`locked`) refuses every change to it and its items (the core refuses a locked target; locks.py the rest)."""
from __future__ import annotations

from rostrum_core import Param, codes
from rostrum_core.edits import MISSING
from rostrum_core import ids as core_ids

from . import fields as FD
from .registry import REGISTRY, set_fields, taken

REGISTRY.operation("doc.set", "Change the tempo, length, beats per bar or sample rate.", target="doc",
                   params=FD.params("doc"), label="Edit song", fields=True)(set_fields)
REGISTRY.operation("track.set", "Change a track's instrument, level, pan, reverb, tone, mute or solo.",
                   target="track", params=FD.params("track"), label="Edit track", fields=True)(set_fields)


@REGISTRY.operation("track.add", "Add a track (choose its instrument in the same call).", label="Add track",
                    params=[Param.text("id", label="Id", help="Optional; counted when left out (track_1 …)."),
                            *FD.params("track")])
def track_add(ctx, targets, args):
    args = dict(args)
    id_ = args.pop("id", None) or core_ids.counted(taken(ctx), "track")
    if id_ in taken(ctx):
        ctx.fail(codes.BAD_ARGUMENT, f'id "{id_}"', "is already used in this document")
    ctx.insert("root", "tracks", {"id": id_, "type": "track", "name": args.pop("name", id_),
                                  **FD.DEFAULTS["track"], **args})


@REGISTRY.operation("track.remove", "Delete tracks and everything on them.", target="track", label="Delete track",
                    importance="secondary")
def track_remove(ctx, targets, args):
    for t in targets:
        ctx.remove(t)


@REGISTRY.operation("track.lock", "Lock tracks: nobody can change them or anything on them (people, agents, scripts) "
                    "until they are unlocked.", target="track", label="Lock track",
                    valid_when={"not": {"is": ["locked", True]}})
def track_lock(ctx, targets, args):
    for t in targets:
        ctx.set(t, "locked", True)


@REGISTRY.operation("track.unlock", "Unlock tracks so they can be changed again.", target="track",
                    label="Unlock track", valid_when={"is": ["locked", True]})
def track_unlock(ctx, targets, args):
    for t in targets:
        ctx.set(t, "locked", MISSING)
