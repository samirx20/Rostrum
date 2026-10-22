"""A group's members, by hand: `bus.add_track` (tracks play into a group) and `bus.remove_track` (they play where the
group played to). The screen's drag of a track header into or out of a group is exactly these; one call is one undo
step, and a track keeps every setting it had (only its `output` changes).
"""
from __future__ import annotations

from rostrum_core import Param, codes

from .. import names
from .ops_buses import need_bus
from .registry import REGISTRY

TRACKS = Param.list("tracks", "id", kind="track", min_items=1, required=True, label="Tracks", group="Group",
                    help="The ids of the tracks (not groups).")


def _tracks(ctx, ids):
    have = {t["id"] for t in ctx.doc.get("tracks", [])}
    for t in ids:
        if t not in have:
            ctx.fail(codes.NOT_FOUND, f'track "{t}"', "is not a track in this document", sorted(have))
    return ids


@REGISTRY.operation("bus.add_track", "Put tracks into a group: they play into this bus (leaving the group they were "
                    "in). Their faders, pans and effects stay as they were.", target="bus", params=[TRACKS],
                    label="Move tracks into a group")
def bus_add_track(ctx, targets, args):
    for bus in targets:
        need_bus(ctx, bus, "group")
        for t in _tracks(ctx, args["tracks"]):
            if ctx.item(t).get("output", names.MASTER_OUT) != bus:
                ctx.set(t, "output", bus)


@REGISTRY.operation("bus.remove_track", "Take tracks out of this group: they play where the group plays to. Tracks "
                    "that are not in it are left alone.", target="bus", params=[TRACKS],
                    label="Move tracks out of a group")
def bus_remove_track(ctx, targets, args):
    for bus in targets:
        need_bus(ctx, bus, "group")
        out = ctx.item(bus).get("output", names.MASTER_OUT)
        for t in _tracks(ctx, args["tracks"]):
            if ctx.item(t).get("output", names.MASTER_OUT) == bus:
                ctx.set(t, "output", out)
